from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.event_queue import queue_health
from runtime.event_sources.event_source_state import list_event_sources
from runtime.manifest_loader import load_manifest_catalog
from runtime.persistence import ensure_dir, write_json_atomic
from runtime.runtime_environment import check_runtime_profile, load_runtime_profile
from runtime.scheduler_store import list_schedules
from runtime.taskframe import utc_now
from runtime.tool_registry import TOOL_REGISTRY
from runtime.worker.worker_contract import build_empty_worker_state
from runtime.worker.worker_lock import detect_stale_lock, is_worker_locked
from runtime.worker_identity import build_worker_identity, validate_worker_identity
from src.config_profiles import load_config_profile


ROOT = Path(__file__).resolve().parents[2]
WORKER_REPORTS_DIR = "reports"
WORKER_HARDENING_JSON = "worker_hardening_latest.json"
WORKER_HARDENING_MD = "worker_hardening_latest.md"
WORKER_SOAK_JSON = "worker_soak_latest.json"
WORKER_SOAK_MD = "worker_soak_latest.md"

_FAILED_CLASSIFICATIONS = {
    "PARTIAL_FAILURE",
    "FAILED_RECOVERABLE",
    "FAILED_MANUAL_REVIEW",
    "FAILED_POLICY_BLOCKED",
    "FAILED_STALE_LOCK",
    "FAILED_TIMEOUT",
}


def build_worker_hardening_status(
    *,
    runtime_data_dir: str | Path = "runtime_data",
    profile_name: str | None = None,
    manifest_dir: str | Path = "manifests",
    routes_path: str | Path = "config/event_routes.json",
    toolpack_config_path: str | Path = "config/examples/taskframe.service.toolpacks.example.json",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    config = load_config_profile(profile_name=profile_name, runtime_data_dir=runtime_root)
    active_profile = profile_name or str(config.name or "") or load_runtime_profile()["profile"]
    runtime_profile = load_runtime_profile(profile_name=active_profile)
    runtime_profile_policy = check_runtime_profile(runtime_profile)
    worker_state = _read_worker_state(runtime_root)
    lock_info = is_worker_locked(runtime_root)
    stale_lock = detect_stale_lock(runtime_root)
    stop_request = _read_stop_request(runtime_root)
    recent_cycles = _read_recent_cycles(runtime_root, limit=20)
    cycle_history = [
        {**dict(item), "classification": classify_worker_cycle_failure(item)} for item in recent_cycles
    ]
    failed_cycles = [item for item in cycle_history if item["classification"] in _FAILED_CLASSIFICATIONS]
    durations = [int(item.get("duration_ms", 0) or 0) for item in recent_cycles if isinstance(item, dict)]
    average_cycle_duration_ms = round(sum(durations) / len(durations), 1) if durations else 0.0
    longest_cycle_duration_ms = max(durations) if durations else 0
    last_heartbeat_age_seconds = _age_seconds(worker_state.get("last_heartbeat_at") or _first_lock_heartbeat(lock_info))
    worker_identity = _resolve_worker_identity(config.raw.get("worker_identity") if isinstance(config.raw, dict) else {}, active_profile)
    worker_identity_present = bool(worker_identity.get("worker_id"))
    worker_identity_valid = validate_worker_identity(worker_identity)["ok"] if worker_identity_present else False

    queue_summary = _safe_queue_health(runtime_root)
    scheduler_summary = _safe_scheduler_health(runtime_root)
    event_source_summary = _safe_event_source_health(runtime_root)
    service_preflight = _safe_service_preflight(
        active_profile,
        runtime_root,
        manifest_dir=manifest_dir,
        routes_path=routes_path,
        toolpack_config_path=toolpack_config_path,
    )

    service_ready = bool(service_preflight.get("ok", True)) if active_profile == "service" else True
    profile_ok = bool(runtime_profile_policy.get("ok", False))
    stale_lock_detected = bool(stale_lock.get("stale", False))
    duplicate_worker_blocked = bool(lock_info.get("locked", False)) and str((lock_info.get("lock") or {}).get("worker_id", "")) not in {"", str(worker_state.get("worker_id", ""))}
    queue_ok = bool(queue_summary.get("ok", False))
    scheduler_ok = bool(scheduler_summary.get("ok", False))
    event_source_ok = bool(event_source_summary.get("ok", False))
    stop_requested = bool(stop_request)
    worker_present = bool(worker_state.get("worker_id"))

    hardening_checks = {
        "worker_state_present": worker_present,
        "current_lock_ok": not stale_lock_detected and not duplicate_worker_blocked,
        "stale_lock_detected": stale_lock_detected,
        "stop_request_present": stop_requested,
        "queue_health_ok": queue_ok,
        "scheduler_health_ok": scheduler_ok,
        "event_source_health_ok": event_source_ok,
        "runtime_profile_safe": profile_ok,
        "worker_identity_present": worker_identity_present,
        "worker_identity_valid": worker_identity_valid,
        "service_preflight_ok": service_ready,
    }
    status_context = {
        "profile": active_profile,
        "runtime_data_dir": str(runtime_root),
        "worker_id": str(worker_state.get("worker_id", "") or worker_identity.get("worker_id", "") or ""),
        "worker_state": worker_state,
        "current_lock": lock_info.get("lock") if isinstance(lock_info, dict) else {},
        "stale_lock": stale_lock,
        "stop_request": stop_request,
        "recent_cycles": cycle_history,
        "failed_cycles": failed_cycles,
        "average_cycle_duration_ms": average_cycle_duration_ms,
        "longest_cycle_duration_ms": longest_cycle_duration_ms,
        "last_heartbeat_age_seconds": last_heartbeat_age_seconds,
        "queue_health": queue_summary,
        "scheduler_health": scheduler_summary,
        "event_source_health": event_source_summary,
        "runtime_profile": runtime_profile,
        "runtime_profile_policy": runtime_profile_policy,
        "worker_identity": worker_identity,
        "worker_identity_present": worker_identity_present,
        "service_preflight": service_preflight,
        "service_ready": service_ready,
        "soak_ready": bool(
            profile_ok
            and service_ready
            and not stale_lock_detected
            and not duplicate_worker_blocked
            and queue_ok
            and scheduler_ok
            and event_source_ok
            and not stop_requested
            and (worker_identity_present if active_profile == "service" else True)
        ),
        "hardening_checks": hardening_checks,
    }
    anomalies = detect_worker_anomalies(status_context)
    recommendations = build_worker_recovery_recommendation(status_context)
    blocker_ids = [item["id"] for item in anomalies if item.get("severity") in {"error", "critical"}]
    warnings = [item["message"] for item in anomalies if item.get("severity") == "warning"]
    classification = "READY" if not anomalies else ("BLOCKED" if blocker_ids else "DEGRADED")

    result = {
        "ok": not blocker_ids and not warnings,
        "classification": classification,
        "profile": active_profile,
        "runtime_data_dir": str(runtime_root),
        "worker_id": str(worker_state.get("worker_id", "") or worker_identity.get("worker_id", "") or ""),
        "worker_state": worker_state,
        "current_lock": lock_info.get("lock") if isinstance(lock_info, dict) else {},
        "stale_lock_detected": stale_lock_detected,
        "stop_request": stop_request,
        "recent_cycles": cycle_history,
        "failed_cycles": failed_cycles,
        "average_cycle_duration_ms": average_cycle_duration_ms,
        "longest_cycle_duration_ms": longest_cycle_duration_ms,
        "last_heartbeat_age_seconds": last_heartbeat_age_seconds,
        "queue_health": queue_summary,
        "scheduler_health": scheduler_summary,
        "event_source_health": event_source_summary,
        "runtime_profile": runtime_profile,
        "runtime_profile_policy": runtime_profile_policy,
        "worker_identity": worker_identity,
        "worker_identity_present": worker_identity_present,
        "service_preflight": service_preflight,
        "service_ready": service_ready,
        "soak_ready": status_context["soak_ready"],
        "hardening_checks": hardening_checks,
        "anomalies": anomalies,
        "recommendations": recommendations,
        "blockers": [item for item in anomalies if item.get("severity") in {"error", "critical"}],
        "warnings": warnings,
        "classification_counts": dict(Counter(item["classification"] for item in cycle_history)),
        "cycle_classifications": cycle_history,
    }
    return result


def detect_worker_anomalies(status: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []

    def add(anomaly_id: str, message: str, *, severity: str = "warning") -> None:
        anomalies.append({"id": anomaly_id, "severity": severity, "message": message})

    worker_state = dict(status.get("worker_state") or {})
    current_lock = dict(status.get("current_lock") or {})
    stale_lock = dict(status.get("stale_lock") or {})
    stop_request = dict(status.get("stop_request") or {})
    queue_health_result = dict(status.get("queue_health") or {})
    scheduler_health_result = dict(status.get("scheduler_health") or {})
    event_source_health_result = dict(status.get("event_source_health") or {})
    runtime_profile_policy = dict(status.get("runtime_profile_policy") or {})

    if stale_lock.get("stale"):
        add("stale_lock_detected", "A stale worker lock is present.", severity="critical")
    if current_lock and worker_state.get("worker_id") and current_lock.get("worker_id") not in {"", worker_state.get("worker_id")}:
        add("duplicate_worker_blocked", "Another worker instance currently owns the lock.", severity="critical")
    if stop_request:
        add("stop_request_pending", "A stop request is pending and should be honored.", severity="warning")
    if not worker_state.get("worker_id"):
        add("worker_state_missing", "Worker state does not record a worker_id yet.", severity="warning")
    if status.get("last_heartbeat_age_seconds", 0) and int(status.get("last_heartbeat_age_seconds", 0) or 0) > 600:
        add("heartbeat_stale", "The last worker heartbeat is stale.", severity="warning")
    if not bool(queue_health_result.get("ok", False)):
        add("queue_unhealthy", "Queue health reported a failure.", severity="error")
    if not bool(scheduler_health_result.get("ok", False)):
        add("scheduler_unhealthy", "Scheduler health reported a failure.", severity="error")
    if not bool(event_source_health_result.get("ok", False)):
        add("event_sources_unhealthy", "Event-source health reported a failure.", severity="error")
    if not bool(runtime_profile_policy.get("ok", False)):
        add("runtime_profile_blocked", "Active runtime profile is not policy-safe.", severity="critical")
    if status.get("profile") == "service":
        if not bool(status.get("worker_identity_present", False)):
            add("service_worker_identity_missing", "Service mode requires worker identity metadata.", severity="critical")
        if not bool(status.get("service_ready", False)):
            add("service_preflight_failed", "Service preflight did not pass.", severity="critical")
    failed_cycles = list(status.get("failed_cycles") or [])
    if failed_cycles:
        add("failed_cycles_present", f"{len(failed_cycles)} recent cycle(s) failed.", severity="warning")
    long_cycle = int(status.get("longest_cycle_duration_ms", 0) or 0)
    avg_cycle = float(status.get("average_cycle_duration_ms", 0.0) or 0.0)
    if long_cycle >= 2 * max(avg_cycle, 1.0) + 5000:
        add("slow_cycle_detected", "A cycle duration exceeded the normal envelope.", severity="warning")
    return anomalies


def classify_worker_cycle_failure(cycle: dict[str, Any]) -> str:
    if not isinstance(cycle, dict):
        return "FAILED_RECOVERABLE"

    ok = bool(cycle.get("ok", False))
    errors = " ".join(str(item) for item in cycle.get("errors", []) if item)
    warnings = " ".join(str(item) for item in cycle.get("warnings", []) if item)
    blob = f"{errors} {warnings} {json_safe(cycle)}".lower()
    queue_processed = int(cycle.get("queue_items_processed", 0) or 0)
    schedule_events = int(cycle.get("schedule_events_enqueued", 0) or 0)
    event_sources = int(cycle.get("event_sources_polled", 0) or 0)
    source_events = int(cycle.get("source_events_enqueued", 0) or 0)

    if ok:
        if queue_processed == 0 and schedule_events == 0 and event_sources == 0 and source_events == 0:
            return "NO_WORK"
        return "OK"

    if "lock" in blob and "stale" in blob:
        return "FAILED_STALE_LOCK"
    if "lock" in blob and "conflict" in blob:
        return "FAILED_STALE_LOCK"
    if "timeout" in blob:
        return "FAILED_TIMEOUT"
    if any(term in blob for term in ("policy", "approval", "governance", "blocked", "credential", "credentials")):
        return "FAILED_POLICY_BLOCKED"
    if any(term in blob for term in ("validation", "business rule", "required", "invariant", "expected", "mismatch")):
        return "FAILED_MANUAL_REVIEW"
    if any(term in blob for term in ("persistence", "queue", "scheduler", "event_source", "network", "io", "transient", "retry")):
        return "FAILED_RECOVERABLE"
    if queue_processed > 0 or schedule_events > 0 or event_sources > 0 or source_events > 0:
        return "PARTIAL_FAILURE"
    return "FAILED_RECOVERABLE"


def build_worker_recovery_recommendation(status: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    anomalies = list(status.get("anomalies") or [])
    anomaly_ids = {str(item.get("id", "")) for item in anomalies if isinstance(item, dict)}

    if "stale_lock_detected" in anomaly_ids:
        recommendations.append("Clear the stale lock explicitly, then rerun the worker.")
    if "duplicate_worker_blocked" in anomaly_ids:
        recommendations.append("Stop the duplicate worker before starting a new one.")
    if "service_worker_identity_missing" in anomaly_ids:
        recommendations.append("Restore the service worker identity in config before running soak or status.")
    if "service_preflight_failed" in anomaly_ids:
        recommendations.append("Fix the service profile preflight blockers before starting the worker.")
    if "queue_unhealthy" in anomaly_ids or "scheduler_unhealthy" in anomaly_ids or "event_sources_unhealthy" in anomaly_ids:
        recommendations.append("Repair the failing subsystem before continuing soak testing.")
    if "failed_cycles_present" in anomaly_ids:
        recommendations.append("Review the latest failed cycles and classify the failure before retrying.")
    if "heartbeat_stale" in anomaly_ids:
        recommendations.append("Confirm the worker is still running or restart it if it is stalled.")
    if "runtime_profile_blocked" in anomaly_ids:
        recommendations.append("Select a safe runtime profile before continuing.")
    if not recommendations:
        recommendations.append("No recovery action is required.")
    return recommendations


def write_worker_hardening_report(
    result: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, str]:
    reports_dir = _reports_dir(runtime_data_dir)
    json_path = reports_dir / WORKER_HARDENING_JSON
    md_path = reports_dir / WORKER_HARDENING_MD
    write_json_atomic(json_path, result)
    md_path.write_text(_render_hardening_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _safe_queue_health(runtime_data_dir: str | Path) -> dict[str, Any]:
    try:
        return queue_health(runtime_data_dir)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _safe_scheduler_health(runtime_data_dir: str | Path) -> dict[str, Any]:
    try:
        schedules = list_schedules(runtime_data_dir=runtime_data_dir)
        return {"ok": True, "count": len(schedules)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _safe_event_source_health(runtime_data_dir: str | Path) -> dict[str, Any]:
    try:
        sources = list_event_sources(runtime_data_dir=runtime_data_dir)
        return {"ok": True, "count": len(sources)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _safe_service_preflight(
    profile_name: str,
    runtime_data_dir: Path,
    *,
    manifest_dir: str | Path,
    routes_path: str | Path,
    toolpack_config_path: str | Path,
) -> dict[str, Any]:
    if profile_name != "service":
        return {"ok": True, "skipped": True}
    try:
        from runtime.service_runtime import build_service_preflight

        return build_service_preflight(
            profile_name=profile_name,
            runtime_data_dir=runtime_data_dir,
            manifest_dir=manifest_dir,
            routes_path=routes_path,
            toolpack_config_path=toolpack_config_path,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _resolve_worker_identity(raw_identity: dict[str, Any], environment: str) -> dict[str, Any]:
    if not isinstance(raw_identity, dict):
        raw_identity = {}
    try:
        return build_worker_identity(
            raw_identity,
            environment=environment,
            operator_id=raw_identity.get("operator_id"),
            approval_authority=raw_identity.get("approval_authority"),
            runtime_instance_id=raw_identity.get("runtime_instance_id"),
        )
    except Exception:
        return {}


def _read_worker_state(runtime_data_dir: str | Path) -> dict[str, Any]:
    path = Path(runtime_data_dir) / "worker" / "state.json"
    if not path.is_file():
        return build_empty_worker_state("")
    try:
        payload = path.read_text(encoding="utf-8")
        data = json.loads(payload)
    except Exception:
        return build_empty_worker_state("")
    return data if isinstance(data, dict) else build_empty_worker_state("")


def _read_recent_cycles(runtime_data_dir: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    path = Path(runtime_data_dir) / "worker" / "cycles.jsonl"
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []
    cycles: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except Exception:
            continue
        if isinstance(record, dict):
            cycles.append(record)
            if len(cycles) >= limit:
                break
    return cycles


def _read_stop_request(runtime_data_dir: str | Path) -> dict[str, Any]:
    path = Path(runtime_data_dir) / "worker" / "stop.request.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_lock_heartbeat(lock_info: dict[str, Any]) -> str:
    lock = lock_info.get("lock") if isinstance(lock_info, dict) else {}
    if isinstance(lock, dict):
        return str(lock.get("last_heartbeat_at", "") or lock.get("acquired_at", "") or "")
    return ""


def _age_seconds(timestamp: str) -> int:
    if not timestamp:
        return 0
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    except Exception:
        return 0


def _reports_dir(runtime_data_dir: str | Path) -> Path:
    path = Path(runtime_data_dir) / "worker" / WORKER_REPORTS_DIR
    ensure_dir(path)
    return path


def _render_hardening_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Worker Hardening Report",
        "",
        f"- Profile: `{result.get('profile', '')}`",
        f"- Worker ID: `{result.get('worker_id', '')}`",
        f"- Classification: `{result.get('classification', '')}`",
        f"- Ok: `{str(result.get('ok', False)).lower()}`",
        f"- Runtime data dir: `{result.get('runtime_data_dir', '')}`",
        f"- Dry-run default: `{str((result.get('runtime_profile') or {}).get('dry_run_default', True)).lower()}`",
        f"- Live side effects allowed: `{str((result.get('runtime_profile') or {}).get('allow_live_side_effects', False)).lower()}`",
        "",
        "## Worker Identity",
        "",
    ]
    identity = result.get("worker_identity") or {}
    if isinstance(identity, dict):
        for key in ("worker_id", "worker_role", "environment", "operator_id", "approval_authority", "runtime_instance_id"):
            lines.append(f"- {key}: `{identity.get(key, '')}`")
    lines.extend(
        [
            "",
            "## Cycle Summary",
            "",
            f"- Cycles inspected: `{len(result.get('recent_cycles', []))}`",
            f"- Failed cycles: `{len(result.get('failed_cycles', []))}`",
            f"- Average duration (ms): `{result.get('average_cycle_duration_ms', 0)}`",
            f"- Longest duration (ms): `{result.get('longest_cycle_duration_ms', 0)}`",
            f"- Last heartbeat age (seconds): `{result.get('last_heartbeat_age_seconds', 0)}`",
            f"- Stale lock detected: `{str(result.get('stale_lock_detected', False)).lower()}`",
            "",
            "## Health",
            "",
            f"- Queue health: `{str((result.get('queue_health') or {}).get('ok', False)).lower()}`",
            f"- Scheduler health: `{str((result.get('scheduler_health') or {}).get('ok', False)).lower()}`",
            f"- Event-source health: `{str((result.get('event_source_health') or {}).get('ok', False)).lower()}`",
            f"- Service ready: `{str(result.get('service_ready', False)).lower()}`",
            f"- Soak ready: `{str(result.get('soak_ready', False)).lower()}`",
            "",
            "## Recommendations",
            "",
        ]
    )
    for item in result.get("recommendations", []) or []:
        lines.append(f"- {item}")
    if result.get("anomalies"):
        lines.extend(["", "## Anomalies", ""])
        for anomaly in result.get("anomalies", []):
            if isinstance(anomaly, dict):
                lines.append(f"- [{anomaly.get('severity', '')}] {anomaly.get('id', '')}: {anomaly.get('message', '')}")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            f"- Live side effects performed: `{str(result.get('live_side_effects_performed', False)).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, dict):
            return {str(k): json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [json_safe(v) for v in value]
        return str(value)
