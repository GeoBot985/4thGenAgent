from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any

from runtime.persistence import write_json_atomic
from runtime.worker.worker_contract import DEFAULT_WORKER_CONFIG
from runtime.worker.worker_hardening import (
    build_worker_hardening_status,
    classify_worker_cycle_failure,
    write_worker_hardening_report,
)
from runtime.worker.worker_engine import run_worker_once
from src.config_profiles import load_config_profile


WORKER_SOAK_JSON = "worker_soak_latest.json"
WORKER_SOAK_MD = "worker_soak_latest.md"


def run_worker_soak(
    *,
    profile_name: str = "service",
    cycles: int = 20,
    sleep_seconds: float = 0.1,
    max_runtime_seconds: float = 300.0,
    queue_limit: int = 10,
    runtime_data_dir: str | Path = "runtime_data",
    fail_fast: bool = False,
    write_report: bool = True,
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    started = time.monotonic()
    config_profile = load_config_profile(profile_name=profile_name, runtime_data_dir=runtime_root)
    worker_identity = dict(config_profile.raw.get("worker_identity") or {}) if isinstance(config_profile.raw, dict) else {}
    worker_id = str(worker_identity.get("worker_id") or config_profile.name or DEFAULT_WORKER_CONFIG.get("worker_id", "worker"))

    preflight = _service_preflight(profile_name, runtime_root)
    if profile_name == "service" and not preflight.get("ok", False):
        result = {
            "ok": False,
            "profile": profile_name,
            "worker_id": worker_id,
            "worker_identity": worker_identity,
            "cycles_requested": int(cycles),
            "cycles_completed": 0,
            "cycles_failed": 0,
            "cycles_no_work": 0,
            "duration_ms": 0,
            "max_cycle_duration_ms": 0,
            "average_cycle_duration_ms": 0.0,
            "stale_lock_detected": bool(_stale_lock_detected(runtime_root)),
            "live_side_effects_performed": False,
            "classifications": {name: 0 for name in _classification_names()},
            "blockers": list(preflight.get("blockers", [])),
            "warnings": list(preflight.get("warnings", [])),
            "preflight": preflight,
            "cycle_results": [],
            "report_paths": {},
        }
        if write_report:
            result["report_paths"] = write_worker_soak_report(result, runtime_data_dir=runtime_root)
        return result

    config = {
        **DEFAULT_WORKER_CONFIG,
        "worker_id": worker_id,
        "mode": "bounded_loop",
        "features": {
            "recover_stale_queue": True,
            "run_scheduler_tick": True,
            "poll_event_sources": True,
            "process_queue": True,
        },
        "limits": {
            **DEFAULT_WORKER_CONFIG.get("limits", {}),
            "max_queue_items_per_cycle": int(queue_limit),
        },
        "safety": {
            **DEFAULT_WORKER_CONFIG.get("safety", {}),
            "dry_run_only": True,
            "allow_live_side_effects": False,
        },
        "frame_metadata": {"worker_identity": worker_identity},
    }

    classifications = Counter({name: 0 for name in _classification_names()})
    cycle_results: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[str] = []
    stale_lock_detected = bool(_stale_lock_detected(runtime_root))
    max_cycle_duration_ms = 0
    total_cycle_duration_ms = 0.0
    cycles_completed = 0
    cycles_failed = 0
    cycles_no_work = 0
    live_side_effects_performed = False
    last_hardening = {}

    for _ in range(int(cycles)):
        if (time.monotonic() - started) >= float(max_runtime_seconds):
            warnings.append("max_runtime_seconds reached before starting the next cycle")
            break
        if _stale_lock_detected(runtime_root):
            stale_lock_detected = True

        cycle_result = run_worker_once(config, runtime_data_dir=runtime_root)
        classification = classify_worker_cycle_failure(cycle_result)
        cycle_result["classification"] = classification
        cycle_results.append(cycle_result)
        classifications[classification] += 1
        cycles_completed += 1
        duration_ms = int(cycle_result.get("duration_ms", 0) or 0)
        total_cycle_duration_ms += float(duration_ms)
        max_cycle_duration_ms = max(max_cycle_duration_ms, duration_ms)
        if classification == "NO_WORK":
            cycles_no_work += 1
        if classification not in {"OK", "NO_WORK"}:
            cycles_failed += 1
            blockers.append({"id": f"cycle_{cycles_completed}_failed", "classification": classification, "message": cycle_result.get("errors", [])[-1] if cycle_result.get("errors") else "cycle failed"})
            if fail_fast:
                break
        if (time.monotonic() - started) >= float(max_runtime_seconds):
            warnings.append("max_runtime_seconds reached after a cycle completed")
            break
        if cycles_completed < int(cycles) and float(sleep_seconds) > 0:
            remaining = float(max_runtime_seconds) - (time.monotonic() - started)
            if remaining <= 0:
                warnings.append("no time remaining for sleep between cycles")
                break
            time.sleep(min(float(sleep_seconds), max(0.0, remaining)))

    duration_ms = int((time.monotonic() - started) * 1000)
    avg_cycle_duration_ms = round(total_cycle_duration_ms / cycles_completed, 1) if cycles_completed else 0.0
    hardening = build_worker_hardening_status(runtime_data_dir=runtime_root, profile_name=profile_name)
    last_hardening = hardening
    result = {
        "ok": cycles_failed == 0 and not blockers and bool(cycles_completed or not cycles),
        "profile": profile_name,
        "worker_id": worker_id,
        "worker_identity": worker_identity,
        "cycles_requested": int(cycles),
        "cycles_completed": cycles_completed,
        "cycles_failed": cycles_failed,
        "cycles_no_work": cycles_no_work,
        "duration_ms": duration_ms,
        "max_cycle_duration_ms": max_cycle_duration_ms,
        "average_cycle_duration_ms": avg_cycle_duration_ms,
        "stale_lock_detected": stale_lock_detected,
        "live_side_effects_performed": live_side_effects_performed,
        "classifications": dict(classifications),
        "blockers": blockers,
        "warnings": warnings,
        "cycle_results": cycle_results,
        "hardening": {
            "ok": bool(hardening.get("ok", False)),
            "classification": hardening.get("classification", "BLOCKED"),
            "anomalies": list(hardening.get("anomalies", [])),
            "recommendations": list(hardening.get("recommendations", [])),
        },
        "preflight": preflight,
        "report_paths": {},
    }
    result["ok"] = bool(result["ok"]) and result["hardening"]["classification"] in {"READY", "DEGRADED"} and not any(
        item.get("classification") in {"FAILED_POLICY_BLOCKED", "FAILED_STALE_LOCK", "FAILED_TIMEOUT"} for item in blockers if isinstance(item, dict)
    )
    if write_report:
        result["report_paths"] = write_worker_soak_report(result, runtime_data_dir=runtime_root, hardening=last_hardening)
    return result


def write_worker_soak_report(
    result: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
    hardening: dict[str, Any] | None = None,
) -> dict[str, str]:
    reports_dir = Path(runtime_data_dir) / "worker" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / WORKER_SOAK_JSON
    md_path = reports_dir / WORKER_SOAK_MD
    write_json_atomic(json_path, result)
    md_path.write_text(_render_soak_markdown(result, hardening=hardening or result.get("hardening") or {}), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _service_preflight(profile_name: str, runtime_root: Path) -> dict[str, Any]:
    if profile_name != "service":
        return {"ok": True, "skipped": True}
    try:
        from runtime.service_runtime import build_service_preflight

        return build_service_preflight(profile_name=profile_name, runtime_data_dir=runtime_root)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "blockers": [{"id": "service_preflight_failed", "message": str(exc)}], "warnings": []}


def _stale_lock_detected(runtime_root: Path) -> bool:
    try:
        from runtime.worker.worker_lock import detect_stale_lock

        return bool(detect_stale_lock(runtime_root).get("stale", False))
    except Exception:
        return False


def _classification_names() -> list[str]:
    return ["OK", "NO_WORK", "PARTIAL_FAILURE", "FAILED_RECOVERABLE", "FAILED_MANUAL_REVIEW", "FAILED_POLICY_BLOCKED", "FAILED_STALE_LOCK", "FAILED_TIMEOUT"]


def _render_soak_markdown(result: dict[str, Any], *, hardening: dict[str, Any]) -> str:
    lines = [
        "# Worker Soak Report",
        "",
        f"- Profile: `{result.get('profile', '')}`",
        f"- Worker ID: `{result.get('worker_id', '')}`",
        f"- Cycles requested: `{result.get('cycles_requested', 0)}`",
        f"- Cycles completed: `{result.get('cycles_completed', 0)}`",
        f"- Cycles failed: `{result.get('cycles_failed', 0)}`",
        f"- Cycles with no work: `{result.get('cycles_no_work', 0)}`",
        f"- Duration (ms): `{result.get('duration_ms', 0)}`",
        f"- Max cycle duration (ms): `{result.get('max_cycle_duration_ms', 0)}`",
        f"- Average cycle duration (ms): `{result.get('average_cycle_duration_ms', 0)}`",
        f"- Stale lock detected: `{str(result.get('stale_lock_detected', False)).lower()}`",
        f"- Live side effects performed: `{str(result.get('live_side_effects_performed', False)).lower()}`",
        "",
        "## Cycle Classifications",
        "",
    ]
    for name in _classification_names():
        lines.append(f"- {name}: `{result.get('classifications', {}).get(name, 0)}`")
    lines.extend(
        [
            "",
            "## Hardening",
            "",
            f"- Hardening classification: `{hardening.get('classification', '')}`",
            f"- Hardening ok: `{str(hardening.get('ok', False)).lower()}`",
            f"- Soak ready: `{str(hardening.get('soak_ready', False)).lower()}`",
            "",
            "## Recommendations",
            "",
        ]
    )
    for item in hardening.get("recommendations", []) or []:
        lines.append(f"- {item}")
    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in result.get("warnings", []):
            lines.append(f"- {warning}")
    if result.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for blocker in result.get("blockers", []):
            if isinstance(blocker, dict):
                lines.append(f"- [{blocker.get('classification', '')}] {blocker.get('message', '')}")
    return "\n".join(lines) + "\n"
