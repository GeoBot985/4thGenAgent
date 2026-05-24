from __future__ import annotations

import json
import os
from datetime import timezone
from pathlib import Path
from typing import Any

from runtime.event_queue import queue_health
from runtime.event_source_route_alignment import validate_event_source_route_alignment
from runtime.event_sources.event_source_state import list_event_sources
from runtime.operational_monitoring import aggregate_tool_health, get_run_health_index_path, load_run_health_index
from runtime.persistence import ensure_dir, write_json_atomic
from runtime.runtime_environment import check_runtime_profile, load_runtime_profile, profile_safety_summary
from runtime.runtime_store import RUNTIME_STORE_DIRS
from runtime.scheduler_store import list_schedules
from runtime.service_runtime import build_service_preflight
from runtime.taskframe import utc_now
from runtime.tool_health import load_latest_tool_health_snapshot
from runtime.worker.worker_hardening import build_worker_hardening_status
from runtime.worker.worker_lock import detect_stale_lock, is_worker_locked
from runtime.worker.worker_engine import build_worker_status
from runtime.worker.worker_soak import WORKER_SOAK_JSON
from runtime.worker_identity import validate_worker_identity
from runtime.runtime_locking import list_runtime_locks
from src.live_safety_status import build_live_safety_status
from src.manifest_health import run_manifest_health_check
from src.operator_data import build_operator_snapshot
from src.config_profiles import load_config_profile


MONITORING_DIR_NAME = "monitoring"
MONITORING_SNAPSHOT_JSON = "monitoring_snapshot_latest.json"
MONITORING_SNAPSHOT_MD = "monitoring_snapshot_latest.md"
ALERT_CANDIDATES_JSON = "alert_candidates_latest.json"
ALERT_CANDIDATES_MD = "alert_candidates_latest.md"

_MONITORING_STATUSES = ("HEALTHY", "DEGRADED", "ATTENTION_REQUIRED", "BLOCKED")
_SECTION_STATUSES = ("OK", "WARN", "FAIL", "SKIPPED")


def build_monitoring_snapshot(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    profile_name: str | None = None,
    config_dir: str | Path | None = None,
    manifest_dir: str | Path = "manifests",
    routes_path: str | Path = "config/event_routes.json",
    toolpack_config_path: str | Path = "config/examples/taskframe.service.toolpacks.example.json",
    threshold_failed_frames: int = 10,
    heartbeat_stale_seconds: int = 600,
    max_cycle_duration_ms: int = 1000,
    write_report: bool = False,
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    profile_name = str(profile_name or "service")
    generated_at = utc_now()

    runtime_profile = _safe_runtime_profile(profile_name)
    config_profile = _safe_config_profile(profile_name, runtime_root, config_dir=config_dir)
    worker_identity = _resolve_worker_identity(config_profile, runtime_profile)
    service_preflight = _safe_service_preflight(
        profile_name,
        runtime_root,
        config_dir=config_dir,
        manifest_dir=manifest_dir,
        routes_path=routes_path,
        toolpack_config_path=toolpack_config_path,
    )
    worker_status = _safe_worker_status(runtime_root)
    worker_hardening = _safe_worker_hardening(
        runtime_root,
        profile_name=profile_name,
        manifest_dir=manifest_dir,
        routes_path=routes_path,
        toolpack_config_path=toolpack_config_path,
    )
    worker_soak = _safe_worker_soak(runtime_root)
    worker_lock = _safe_worker_lock(runtime_root)
    queue_status = _safe_queue_status(runtime_root)
    scheduler_status = _safe_scheduler_status(runtime_root)
    event_sources = _safe_event_sources(runtime_root, routes_path=routes_path)
    recovery = _safe_recovery(runtime_root, manifest_dir=manifest_dir)
    tool_health = _safe_tool_health(runtime_root)
    manifest_health = _safe_manifest_health(runtime_root, manifest_dir=manifest_dir)
    live_safety = _safe_live_safety(runtime_root)
    pending_actions = _safe_pending_actions(runtime_root)
    storage = _safe_storage(runtime_root, manifest_dir=manifest_dir)
    monitoring_summary = _safe_monitoring_summary(runtime_root, profile_name=profile_name, threshold_failed_frames=threshold_failed_frames)

    sections = {
        "service_preflight": _build_section(
            service_preflight.get("ok", False),
            summary=_summarize_check_list(service_preflight.get("checks", [])),
            details=service_preflight,
            warnings=list(service_preflight.get("warnings", [])),
            errors=[str(item.get("message", "")) for item in service_preflight.get("blockers", []) if isinstance(item, dict)],
        ),
        "worker": _build_section(
            worker_status.get("ok", False),
            summary=_summarize_worker(worker_status),
            details=worker_status,
            warnings=list(worker_status.get("warnings", [])),
            errors=([str(worker_status.get("error", ""))] if worker_status.get("error") else []),
        ),
        "worker_hardening": _build_section(
            worker_hardening.get("ok", False),
            status=_map_hardening_status(worker_hardening.get("classification", "BLOCKED")),
            summary=_summarize_worker_hardening(worker_hardening),
            details=worker_hardening,
            warnings=list(worker_hardening.get("warnings", [])),
            errors=[str(item.get("message", "")) for item in worker_hardening.get("blockers", []) if isinstance(item, dict)],
        ),
        "worker_soak": _build_section(
            bool(worker_soak.get("ok", False)) if worker_soak else False,
            status=_map_soak_status(worker_soak),
            summary=_summarize_worker_soak(worker_soak),
            details=worker_soak,
            warnings=list(worker_soak.get("warnings", [])) if isinstance(worker_soak, dict) else [],
            errors=[str(item.get("message", "")) for item in worker_soak.get("blockers", []) if isinstance(item, dict)] if isinstance(worker_soak, dict) else [],
        ),
        "scheduler": _build_section(
            scheduler_status.get("ok", False),
            summary=_summarize_scheduler(scheduler_status),
            details=scheduler_status,
            warnings=list(scheduler_status.get("warnings", [])) if isinstance(scheduler_status, dict) else [],
            errors=[str(scheduler_status.get("error", ""))] if scheduler_status.get("error") else [],
        ),
        "queue": _build_section(
            queue_status.get("ok", False),
            summary=_summarize_queue(queue_status),
            details=queue_status,
            warnings=[],
            errors=[str(queue_status.get("error", ""))] if queue_status.get("error") else [],
        ),
        "event_sources": _build_section(
            event_sources.get("ok", False),
            status="WARN" if event_sources.get("warnings") and not event_sources.get("errors") else ("FAIL" if event_sources.get("errors") else "OK"),
            summary=_summarize_event_sources(event_sources),
            details=event_sources,
            warnings=list(event_sources.get("warnings", [])),
            errors=list(event_sources.get("errors", [])),
        ),
        "recovery": _build_section(
            recovery.get("ok", False),
            status=_map_recovery_status(recovery),
            summary=_summarize_recovery(recovery),
            details=recovery,
            warnings=list(recovery.get("warnings", [])) if isinstance(recovery, dict) else [],
            errors=[str(item.get("message", "")) for item in recovery.get("blockers", []) if isinstance(item, dict)] if isinstance(recovery, dict) else [],
        ),
        "tool_health": _build_section(
            tool_health.get("ok", False),
            status=_map_tool_health_status(tool_health),
            summary=_summarize_tool_health(tool_health),
            details=tool_health,
            warnings=list(tool_health.get("warnings", [])) if isinstance(tool_health, dict) else [],
            errors=[str(tool_health.get("error", ""))] if tool_health.get("error") else [],
        ),
        "manifest_health": _build_section(
            manifest_health.get("ok", False),
            status=_map_manifest_health_status(manifest_health),
            summary=_summarize_manifest_health(manifest_health),
            details=manifest_health,
            warnings=list(manifest_health.get("warnings", [])) if isinstance(manifest_health, dict) else [],
            errors=[str(manifest_health.get("error", ""))] if manifest_health.get("error") else [],
        ),
        "live_safety": _build_section(
            live_safety.get("live_execution_env_enabled") is False,
            status=_map_live_safety_status(runtime_profile, live_safety),
            summary=_summarize_live_safety(live_safety),
            details=live_safety,
            warnings=[],
            errors=[],
        ),
        "pending_actions": _build_section(
            True,
            status=_map_pending_action_status(pending_actions, live_safety),
            summary=_summarize_pending_actions(pending_actions, live_safety),
            details=pending_actions,
            warnings=[],
            errors=[],
        ),
        "runtime_profile": _build_section(
            bool(runtime_profile.get("profile")),
            status=_map_runtime_profile_status(runtime_profile, service_preflight, worker_identity),
            summary=_summarize_runtime_profile(runtime_profile, worker_identity),
            details={
                "runtime_profile": runtime_profile,
                "config_profile": config_profile,
                "worker_identity": worker_identity,
                "profile_safety": profile_safety_summary(runtime_profile),
                "policy": check_runtime_profile(runtime_profile),
            },
            warnings=[],
            errors=[],
        ),
        "storage": _build_section(
            storage.get("ok", False),
            status=_map_storage_status(storage),
            summary=_summarize_storage(storage),
            details=storage,
            warnings=list(storage.get("warnings", [])) if isinstance(storage, dict) else [],
            errors=[str(item.get("message", "")) for item in storage.get("issues", []) if isinstance(item, dict) and item.get("severity") == "error"],
        ),
    }

    alert_candidates = build_alert_candidates(
        sections=sections,
        runtime_profile=runtime_profile,
        service_preflight=service_preflight,
        worker_status=worker_status,
        worker_hardening=worker_hardening,
        worker_soak=worker_soak,
        queue_status=queue_status,
        scheduler_status=scheduler_status,
        event_sources=event_sources,
        recovery=recovery,
        worker_lock=worker_lock,
        tool_health=tool_health,
        manifest_health=manifest_health,
        live_safety=live_safety,
        pending_actions=pending_actions,
        storage=storage,
        monitoring_summary=monitoring_summary,
        heartbeat_stale_seconds=heartbeat_stale_seconds,
        max_cycle_duration_ms=max_cycle_duration_ms,
        threshold_failed_frames=threshold_failed_frames,
    )

    blockers = _collect_blockers(sections, alert_candidates)
    warnings = _collect_warnings(sections, alert_candidates)
    status = classify_monitoring_status(sections=sections, alert_candidates=alert_candidates, blockers=blockers, warnings=warnings)
    snapshot = {
        "ok": True,
        "status": status,
        "profile": profile_name,
        "worker_identity": worker_identity,
        "generated_at": generated_at,
        "sections": sections,
        "alert_candidates": alert_candidates,
        "blockers": blockers,
        "warnings": warnings,
        "report_paths": {},
    }

    if write_report:
        report_paths = write_monitoring_snapshot(snapshot, runtime_data_dir=runtime_root)
        snapshot["report_paths"] = report_paths
    return snapshot


def classify_monitoring_status(
    *,
    sections: dict[str, Any],
    alert_candidates: list[dict[str, Any]] | None = None,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
) -> str:
    blockers = list(blockers or [])
    alert_candidates = list(alert_candidates or [])
    warnings = list(warnings or [])

    if blockers or any(candidate.get("severity") == "critical" for candidate in alert_candidates if isinstance(candidate, dict)):
        return "BLOCKED"
    if any(candidate.get("severity") == "error" for candidate in alert_candidates if isinstance(candidate, dict)):
        return "ATTENTION_REQUIRED"
    if warnings or any(candidate.get("severity") == "warning" for candidate in alert_candidates if isinstance(candidate, dict)):
        return "DEGRADED"
    if any(section.get("status") == "FAIL" for section in sections.values() if isinstance(section, dict)):
        return "ATTENTION_REQUIRED"
    return "HEALTHY"


def build_alert_candidates(
    *,
    sections: dict[str, Any],
    runtime_profile: dict[str, Any],
    service_preflight: dict[str, Any],
    worker_status: dict[str, Any],
    worker_hardening: dict[str, Any],
    worker_soak: dict[str, Any],
    queue_status: dict[str, Any],
    scheduler_status: dict[str, Any],
    event_sources: dict[str, Any],
    recovery: dict[str, Any],
    worker_lock: dict[str, Any],
    tool_health: dict[str, Any],
    manifest_health: dict[str, Any],
    live_safety: dict[str, Any],
    pending_actions: dict[str, Any],
    storage: dict[str, Any],
    monitoring_summary: dict[str, Any],
    heartbeat_stale_seconds: int,
    max_cycle_duration_ms: int,
    threshold_failed_frames: int,
) -> list[dict[str, Any]]:
    sections = dict(sections or {})
    runtime_profile = dict(runtime_profile or {})
    service_preflight = dict(service_preflight or {})
    worker_status = dict(worker_status or {})
    worker_hardening = dict(worker_hardening or {})
    worker_soak = dict(worker_soak or {})
    queue_status = dict(queue_status or {})
    scheduler_status = dict(scheduler_status or {})
    event_sources = dict(event_sources or {})
    recovery = dict(recovery or {})
    worker_lock = dict(worker_lock or {})
    tool_health = dict(tool_health or {})
    manifest_health = dict(manifest_health or {})
    live_safety = dict(live_safety or {})
    pending_actions = dict(pending_actions or {})
    storage = dict(storage or {})
    monitoring_summary = dict(monitoring_summary or {})
    candidates: list[dict[str, Any]] = []
    created_at = utc_now()

    def add(
        alert_id: str,
        severity: str,
        category: str,
        title: str,
        message: str,
        source_section: str,
        recommended_action: str,
        evidence_refs: list[str],
    ) -> None:
        candidate = {
            "alert_id": alert_id,
            "severity": severity,
            "category": category,
            "title": title,
            "message": message,
            "source_section": source_section,
            "recommended_action": recommended_action,
            "evidence_refs": evidence_refs,
            "created_at": created_at,
        }
        if candidate not in candidates:
            candidates.append(candidate)

    service_profile_name = str(runtime_profile.get("profile", "") or "")
    live_profile_active = service_profile_name == "live"
    allow_live_side_effects = bool(runtime_profile.get("allow_live_side_effects", False))
    optional_rpa_enabled = bool(runtime_profile.get("allow_optional_rpa", False)) or bool(runtime_profile.get("optional_rpa_enabled", False))
    preflight_ok = bool(service_preflight.get("ok", False))
    queue_ok = bool(queue_status.get("ok", False))
    scheduler_ok = bool(scheduler_status.get("ok", False))
    event_source_ok = bool(event_sources.get("ok", False)) and not event_sources.get("errors")
    if service_profile_name == "service" and not preflight_ok:
        add(
            "service_preflight_failed",
            "critical",
            "safety",
            "Service preflight failed",
            "The service profile did not pass deployment preflight checks.",
            "service_preflight",
            "Fix the service preflight blockers before starting the service worker.",
            ["sections.service_preflight", "runtime_data/service/service_preflight_latest.json"],
        )
    if live_profile_active or allow_live_side_effects:
        add(
            "live_side_effects_enabled",
            "critical",
            "safety",
            "Live side effects are enabled",
            "The runtime profile allows live side effects and cannot be treated as service-safe.",
            "runtime_profile",
            "Select a dry-run-only profile and disable live execution before continuing.",
            ["sections.runtime_profile"],
        )
    if _service_preflight_check_failed(service_preflight, "optional_rpa_blocked") or optional_rpa_enabled:
        add(
            "optional_rpa_enabled",
            "critical",
            "safety",
            "Optional RPA is enabled",
            "Optional RPA must remain disabled in service and release-style runtime profiles.",
            "runtime_profile",
            "Disable optional RPA before relying on the service runtime.",
            ["sections.runtime_profile"],
        )
    if sections.get("worker_hardening", {}).get("details", {}).get("stale_lock_detected"):
        add(
            "stale_active_worker_lock",
            "critical",
            "worker",
            "Stale active worker lock detected",
            "A stale worker lock is preventing safe service operation.",
            "worker_hardening",
            "Clear the stale lock explicitly and restart the worker service.",
            ["sections.worker_hardening", "sections.worker", "runtime_data/worker/worker.lock.json"],
        )
    if not queue_ok:
        add(
            "queue_unavailable",
            "critical",
            "queue",
            "Queue is unavailable",
            "Queue persistence is unavailable or unhealthy.",
            "queue",
            "Repair the queue backend before starting the service worker.",
            ["sections.queue"],
        )
    if not scheduler_ok:
        add(
            "scheduler_unavailable",
            "error",
            "scheduler",
            "Scheduler is unavailable",
            "The scheduler subsystem could not be read safely.",
            "scheduler",
            "Restore scheduler storage or configuration before running the worker.",
            ["sections.scheduler"],
        )
    if not event_source_ok:
        add(
            "event_source_contracts_invalid",
            "error",
            "event_source",
            "Event-source contracts are invalid",
            "The event-source registry or route alignment failed validation.",
            "event_sources",
            "Repair event-source contracts and route alignment before continuing.",
            ["sections.event_sources"],
        )
    repeated_failures = len(worker_hardening.get("failed_cycles", []) or [])
    if repeated_failures >= 2:
        add(
            "repeated_worker_failures",
            "error",
            "worker",
            "Repeated worker failures detected",
            f"{repeated_failures} recent worker cycles failed.",
            "worker_hardening",
            "Inspect the latest failed cycles and classify the failure before retrying.",
            ["sections.worker_hardening", "runtime_data/worker/reports/worker_hardening_latest.json"],
        )
    failed_frames = list(monitoring_summary.get("latest_failed_runs", []))
    if failed_frames:
        add(
            "failed_taskframes_manual_review",
            "warning",
            "recovery",
            "Failed TaskFrames need manual review",
            "Recent failed TaskFrames are present and should be reviewed before relying on service mode.",
            "recovery",
            "Open the latest failed run reports and resolve or explain each failure.",
            ["sections.recovery", "runtime_data/indexes/run_health_index.json"],
        )
    if failed_frames and len(failed_frames) > int(threshold_failed_frames):
        add(
            "failed_taskframes_threshold_exceeded",
            "critical",
            "recovery",
            "Failed TaskFrame threshold exceeded",
            f"{len(failed_frames)} failed TaskFrames exceed the configured threshold of {threshold_failed_frames}.",
            "recovery",
            "Resolve unrecovered failed TaskFrames before treating the runtime as service-ready.",
            ["sections.recovery"],
        )
    tool_section = sections.get("tool_health", {})
    tool_status = str(tool_section.get("details", {}).get("status", "") or tool_section.get("details", {}).get("status", "") or "")
    if tool_status in {"warning", "degraded", "blocked"}:
        add(
            "tool_health_degraded",
            "warning",
            "tool",
            "Tool health is degraded",
            "At least one tool health check is not ready.",
            "tool_health",
            "Review tool health before relying on tool execution.",
            ["sections.tool_health"],
        )
    manifest_section = sections.get("manifest_health", {})
    manifest_details = dict(manifest_section.get("details", {}) or {})
    if manifest_details.get("status") in {"WARNING", "FAILED"} or manifest_section.get("status") == "WARN":
        add(
            "manifest_health_warnings",
            "warning",
            "manifest",
            "Manifest health has warnings",
            "Manifest catalog health reports warnings or degraded manifests.",
            "manifest_health",
            "Review manifest warnings and fix any failing manifests before release work.",
            ["sections.manifest_health"],
        )
    last_heartbeat_age = int(worker_hardening.get("last_heartbeat_age_seconds", 0) or 0)
    if last_heartbeat_age > int(heartbeat_stale_seconds):
        add(
            "no_recent_worker_heartbeat",
            "warning",
            "worker",
            "No recent worker heartbeat",
            f"The last worker heartbeat is stale by {last_heartbeat_age} seconds.",
            "worker",
            "Confirm the worker is still running or restart it if it is stalled.",
            ["sections.worker", "sections.worker_hardening"],
        )
    max_soak_cycle = int(worker_soak.get("max_cycle_duration_ms", 0) or 0)
    if max_soak_cycle > int(max_cycle_duration_ms):
        add(
            "long_cycle_duration",
            "warning",
            "worker",
            "Long worker cycle duration",
            f"The longest worker cycle took {max_soak_cycle} ms which exceeds the threshold of {max_cycle_duration_ms} ms.",
            "worker_soak",
            "Review long-running cycle steps and reduce per-cycle work if needed.",
            ["sections.worker_soak", "runtime_data/worker/reports/worker_soak_latest.json"],
        )
    if not worker_soak or not worker_soak.get("report_paths"):
        add(
            "soak_test_not_run",
            "info",
            "worker",
            "Soak test has not been run",
            "No soak report is available yet.",
            "worker_soak",
            "Run a bounded soak test to build operational evidence.",
            ["sections.worker_soak"],
        )
    if bool(live_safety.get("live_ready_action_count", 0)):
        add(
            "pending_actions_need_attention",
            "warning",
            "safety",
            "Pending actions need attention",
            "One or more pending actions are ready for live execution review.",
            "pending_actions",
            "Review the approval context before expanding live execution.",
            ["sections.pending_actions"],
        )
    if bool(worker_lock.get("locked", False)) and not bool(worker_hardening.get("stale_lock_detected", False)):
        lock_record = dict(worker_lock.get("lock") or {})
        if worker_status.get("worker_id") and lock_record.get("worker_id") and str(lock_record.get("worker_id")) != str(worker_status.get("worker_id")):
            add(
                "duplicate_worker_blocked",
                "critical",
                "worker",
                "Duplicate worker execution is blocked",
                "Another worker instance currently owns the worker lock.",
                "worker",
                "Stop the duplicate worker before starting a new one.",
                ["sections.worker", "runtime_data/worker/worker.lock.json"],
            )
    return candidates


def write_monitoring_snapshot(
    snapshot: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, str]:
    runtime_root = Path(runtime_data_dir)
    out_dir = ensure_dir(runtime_root / MONITORING_DIR_NAME)
    alert_candidates = list(snapshot.get("alert_candidates", []))
    report_paths = {
        "snapshot_json": str(out_dir / MONITORING_SNAPSHOT_JSON),
        "snapshot_markdown": str(out_dir / MONITORING_SNAPSHOT_MD),
        "alert_candidates_json": str(out_dir / ALERT_CANDIDATES_JSON),
        "alert_candidates_markdown": str(out_dir / ALERT_CANDIDATES_MD),
    }
    snapshot = dict(snapshot)
    snapshot["report_paths"] = report_paths
    write_json_atomic(out_dir / MONITORING_SNAPSHOT_JSON, snapshot)
    (out_dir / MONITORING_SNAPSHOT_MD).write_text(render_monitoring_markdown(snapshot), encoding="utf-8")
    write_json_atomic(out_dir / ALERT_CANDIDATES_JSON, {"ok": True, "profile": snapshot.get("profile", ""), "generated_at": snapshot.get("generated_at", ""), "alert_candidates": alert_candidates})
    (out_dir / ALERT_CANDIDATES_MD).write_text(_render_alert_candidates_markdown(snapshot, alert_candidates), encoding="utf-8")
    return report_paths


def render_monitoring_markdown(snapshot: dict[str, Any]) -> str:
    sections = dict(snapshot.get("sections", {}))
    lines = [
        "# Operational Monitoring Snapshot",
        "",
        f"- Overall status: `{snapshot.get('status', 'UNKNOWN')}`",
        f"- Profile: `{snapshot.get('profile', '')}`",
        f"- Generated at: `{snapshot.get('generated_at', '')}`",
        "",
        "## Worker Identity",
        "",
    ]
    identity = snapshot.get("worker_identity") or {}
    if isinstance(identity, dict):
        for key in ("worker_id", "worker_role", "environment", "operator_id", "approval_authority", "runtime_instance_id"):
            lines.append(f"- {key}: `{identity.get(key, '')}`")
    lines.extend(
        [
            "",
            "## Section Summary",
            "",
            "| Section | Status | Summary | Warnings | Errors |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for name, section in sections.items():
        if not isinstance(section, dict):
            continue
        lines.append(
            "| {name} | {status} | {summary} | {warnings} | {errors} |".format(
                name=_escape_md(name),
                status=_escape_md(str(section.get("status", "SKIPPED"))),
                summary=_escape_md(str(section.get("summary", ""))),
                warnings=_escape_md(str(len(section.get("warnings", [])))),
                errors=_escape_md(str(len(section.get("errors", [])))),
            )
        )
    lines.extend(
        [
            "",
            "## Blockers",
            "",
        ]
    )
    blockers = list(snapshot.get("blockers", []))
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = list(snapshot.get("warnings", []))
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Alert Candidates",
            "",
        ]
    )
    candidates = list(snapshot.get("alert_candidates", []))
    if candidates:
        for candidate in candidates:
            if isinstance(candidate, dict):
                lines.append(f"- [{candidate.get('severity', '')}] {candidate.get('title', '')}: {candidate.get('message', '')}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Recommended Actions",
            "",
        ]
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            lines.append(f"- {candidate.get('recommended_action', '')}")
    if not candidates:
        lines.append("- No specific action required.")
    lines.extend(
        [
            "",
            "## Safety Statement",
            "",
            f"- Live side effects allowed: `{str((snapshot.get('sections', {}) or {}).get('runtime_profile', {}).get('details', {}).get('runtime_profile', {}).get('allow_live_side_effects', False)).lower()}`",
            f"- External alerts sent: `false`",
        ]
    )
    return "\n".join(line for line in lines if line is not None) + "\n"


def _render_alert_candidates_markdown(snapshot: dict[str, Any], alert_candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# Alert Candidates",
        "",
        f"- Overall status: `{snapshot.get('status', 'UNKNOWN')}`",
        f"- Profile: `{snapshot.get('profile', '')}`",
        f"- Generated at: `{snapshot.get('generated_at', '')}`",
        "",
        "| Severity | Category | Title | Message | Recommended Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not alert_candidates:
        lines.append("| info | monitoring | None | No alert candidates were generated. | No action required. |")
        return "\n".join(lines) + "\n"
    for candidate in alert_candidates:
        if not isinstance(candidate, dict):
            continue
        lines.append(
            "| {severity} | {category} | {title} | {message} | {action} |".format(
                severity=_escape_md(str(candidate.get("severity", ""))),
                category=_escape_md(str(candidate.get("category", ""))),
                title=_escape_md(str(candidate.get("title", ""))),
                message=_escape_md(str(candidate.get("message", ""))),
                action=_escape_md(str(candidate.get("recommended_action", ""))),
            )
        )
    return "\n".join(lines) + "\n"


def _safe_runtime_profile(profile_name: str) -> dict[str, Any]:
    try:
        return load_runtime_profile(profile_name=profile_name)
    except Exception as exc:
        return {"profile": profile_name, "environment": profile_name, "allow_live_reads": False, "allow_live_side_effects": False, "dry_run_default": True, "require_tool_governance": True, "evidence_required": True, "blocked_tool_classes": [], "worker_identity_required": False, "reserved_for_deployment": False, "error": str(exc)}


def _safe_config_profile(profile_name: str, runtime_root: Path, *, config_dir: str | Path | None = None) -> dict[str, Any]:
    try:
        config = load_config_profile(profile_name=profile_name, runtime_data_dir=runtime_root, config_dir=config_dir)
        return dict(getattr(config, "raw", {}) or {})
    except Exception as exc:
        return {"profile": profile_name, "error": str(exc), "raw": {}}


def _resolve_worker_identity(config_profile: dict[str, Any], runtime_profile: dict[str, Any]) -> dict[str, Any]:
    raw_identity = dict(config_profile.get("worker_identity") or {})
    environment = str(runtime_profile.get("environment", runtime_profile.get("profile", "service")) or "service")
    try:
        from runtime.worker_identity import build_worker_identity

        identity = build_worker_identity(
            raw_identity,
            environment=environment,
            operator_id=raw_identity.get("operator_id"),
            approval_authority=raw_identity.get("approval_authority"),
            runtime_instance_id=raw_identity.get("runtime_instance_id"),
        )
    except Exception:
        identity = raw_identity if isinstance(raw_identity, dict) else {}
    if identity and not validate_worker_identity(identity).get("ok", False):
        return {}
    return identity if isinstance(identity, dict) else {}


def _safe_service_preflight(
    profile_name: str,
    runtime_root: Path,
    *,
    config_dir: str | Path | None,
    manifest_dir: str | Path,
    routes_path: str | Path,
    toolpack_config_path: str | Path,
) -> dict[str, Any]:
    try:
        return build_service_preflight(
            profile_name=profile_name,
            runtime_data_dir=runtime_root,
            config_dir=config_dir,
            manifest_dir=manifest_dir,
            routes_path=routes_path,
            toolpack_config_path=toolpack_config_path,
        )
    except Exception as exc:
        return {"ok": False, "profile": profile_name, "worker_identity": {}, "checks": [], "blockers": [{"id": "service_preflight_error", "message": str(exc)}], "warnings": [str(exc)]}


def _safe_worker_status(runtime_root: Path) -> dict[str, Any]:
    try:
        return build_worker_status(runtime_root)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "worker_id": "", "hardening": {"ok": False, "classification": "BLOCKED", "anomalies": [], "recommendations": []}}


def _safe_worker_hardening(
    runtime_root: Path,
    *,
    profile_name: str,
    manifest_dir: str | Path,
    routes_path: str | Path,
    toolpack_config_path: str | Path,
) -> dict[str, Any]:
    try:
        return build_worker_hardening_status(
            runtime_data_dir=runtime_root,
            profile_name=profile_name,
            manifest_dir=manifest_dir,
            routes_path=routes_path,
            toolpack_config_path=toolpack_config_path,
        )
    except Exception as exc:
        return {"ok": False, "classification": "BLOCKED", "anomalies": [{"id": "worker_hardening_error", "severity": "critical", "message": str(exc)}], "recommendations": [str(exc)], "blockers": [{"id": "worker_hardening_error", "message": str(exc)}], "warnings": []}


def _safe_worker_soak(runtime_root: Path) -> dict[str, Any]:
    path = runtime_root / "worker" / "reports" / WORKER_SOAK_JSON
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "report_paths": {}}
    return payload if isinstance(payload, dict) else {}


def _safe_worker_lock(runtime_root: Path) -> dict[str, Any]:
    try:
        locked = is_worker_locked(runtime_root)
        stale = detect_stale_lock(runtime_root)
        return {"ok": True, **locked, "stale": stale}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "locked": False, "stale": {"stale": False}}


def _safe_queue_status(runtime_root: Path) -> dict[str, Any]:
    try:
        return queue_health(runtime_root)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "backend": "unknown", "counts_by_status": {}, "total": 0}


def _safe_scheduler_status(runtime_root: Path) -> dict[str, Any]:
    try:
        schedules = list_schedules(runtime_data_dir=runtime_root)
        return {"ok": True, "total_schedules": len(schedules), "enabled_count": len([s for s in schedules if s.get("enabled")]), "disabled_count": len([s for s in schedules if not s.get("enabled")]), "schedules": schedules, "recent_runs": []}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "total_schedules": 0, "enabled_count": 0, "disabled_count": 0, "schedules": [], "recent_runs": []}


def _safe_event_sources(runtime_root: Path, *, routes_path: str | Path) -> dict[str, Any]:
    try:
        sources = list_event_sources(runtime_data_dir=runtime_root)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "warnings": [], "errors": [str(exc)], "sources": []}
    try:
        alignment = validate_event_source_route_alignment(routes_path=Path(routes_path))
    except Exception as exc:
        alignment = {"ok": False, "errors": [str(exc)], "warnings": [str(exc)], "findings": [], "mismatches": []}
    return {
        "ok": bool(alignment.get("ok", False)) and not bool(alignment.get("mismatches", [])) and not bool(alignment.get("errors", [])),
        "sources": sources,
        "source_count": len(sources),
        "alignment": alignment,
        "warnings": list(alignment.get("warnings", [])),
        "errors": list(alignment.get("errors", [])),
        "findings": list(alignment.get("findings", [])),
    }


def _safe_recovery(runtime_root: Path, *, manifest_dir: str | Path) -> dict[str, Any]:
    summary = _safe_monitoring_summary(runtime_root, profile_name="service", threshold_failed_frames=10)
    failed = list(summary.get("latest_failed_runs", []))
    stuck = list(summary.get("latest_stuck_runs", []))
    frame = failed[0] if failed else (stuck[0] if stuck else {})
    frame_id = str(frame.get("frame_id", "") or "")
    manifest_id = str(frame.get("manifest_id", "") or "")
    state = str(frame.get("state", "") or "")
    if frame_id:
        return {
            "ok": False,
            "frame_id": frame_id,
            "manifest_id": manifest_id,
            "state": state,
            "recovery_status": "manual_review_required",
            "safe_to_retry": False,
            "safe_to_resume": False,
            "side_effect_risk": "unknown",
            "reason": "Recent failed or stuck TaskFrames require operator review.",
            "recommended_action": "Open the latest failed run reports and resolve or explain each failure.",
            "blockers": [],
            "warnings": [],
            "source_frame_id": frame_id,
        }
    return {"ok": True, "frame_id": "", "manifest_id": "", "state": "", "recovery_status": "skipped", "safe_to_retry": False, "safe_to_resume": False, "side_effect_risk": "unknown", "reason": "No failed or stuck TaskFrame was found.", "recommended_action": "No recovery action required.", "blockers": [], "warnings": []}


def _safe_tool_health(runtime_root: Path) -> dict[str, Any]:
    try:
        snapshot = load_latest_tool_health_snapshot(runtime_root)
        aggregated = aggregate_tool_health(runtime_root, refresh=False)
        return {"ok": True, "snapshot": snapshot, "status": aggregated.get("status", "unknown"), "summary": aggregated.get("summary", {}), "recommended_action": aggregated.get("recommended_action", ""), "by_tool": aggregated.get("by_tool", {})}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "snapshot": {}, "status": "unknown", "summary": {}, "recommended_action": ""}


def _safe_manifest_health(runtime_root: Path, *, manifest_dir: str | Path) -> dict[str, Any]:
    try:
        return run_manifest_health_check(manifest_dir=manifest_dir, runtime_data_dir=runtime_root, include_smoke=False, strict_contract=False)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "status": "FAILED", "summary": {}, "manifests": []}


def _safe_live_safety(runtime_root: Path) -> dict[str, Any]:
    try:
        return build_live_safety_status(runtime_root)
    except Exception as exc:
        return {"live_execution_env_enabled": False, "default_mode": "dry_run", "optional_rpa_enabled": False, "pending_action_count": 0, "approved_pending_action_count": 0, "live_ready_action_count": 0, "blocked_action_count": 0, "summary": "Unavailable.", "error": str(exc)}


def _safe_pending_actions(runtime_root: Path) -> dict[str, Any]:
    try:
        snapshot = build_operator_snapshot(str(runtime_root))
        active_frame = snapshot.get("active_frame") if isinstance(snapshot, dict) else {}
        if not isinstance(active_frame, dict):
            active_frame = {}
        pending = list(active_frame.get("pending_actions", [])) if isinstance(active_frame.get("pending_actions", []), list) else []
        return {
            "ok": True,
            "frame_id": str(active_frame.get("frame_id", "") or ""),
            "pending_action_count": len(pending),
            "approved_pending_action_count": sum(1 for item in pending if isinstance(item, dict) and str(item.get("status", "")).upper() == "APPROVED"),
            "pending_actions": pending,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "frame_id": "", "pending_action_count": 0, "approved_pending_action_count": 0, "pending_actions": []}


def _safe_storage(runtime_root: Path, *, manifest_dir: str | Path) -> dict[str, Any]:
    try:
        required_folders = {name: (runtime_root / name).is_dir() for name in RUNTIME_STORE_DIRS}
        active_locks = list_runtime_locks(runtime_root)
        expired_locks = [item for item in active_locks if isinstance(item, dict) and _lock_expired(item)]
        issue_messages = [f"Missing runtime store folder: {name}" for name, exists in required_folders.items() if not exists]
    except Exception as exc:
        return {"ok": False, "error": str(exc), "issues": [], "runtime_data_dir": str(runtime_root), "runtime_data_writable": False}
    ok = _is_runtime_data_writable(runtime_root) and not issue_messages
    return {
        "ok": ok,
        "runtime_data_dir": str(runtime_root),
        "required_folders": required_folders,
        "artifact_counts": {},
        "taskframes": [],
        "issues": [{"severity": "error", "message": message} for message in issue_messages],
        "active_locks": active_locks,
        "expired_locks": expired_locks,
        "index_rebuildable": False,
        "runtime_data_writable": _is_runtime_data_writable(runtime_root),
        "issue_count": len(issue_messages),
        "corrupted_path_count": 0,
    }


def _lock_expired(lock: dict[str, Any]) -> bool:
    expires_at = str(lock.get("expires_at", "") or "")
    if not expires_at:
        return False
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return parsed <= datetime.now(parsed.tzinfo or timezone.utc)
    except Exception:
        return False


def _safe_monitoring_summary(runtime_root: Path, *, profile_name: str, threshold_failed_frames: int) -> dict[str, Any]:
    try:
        index = load_run_health_index(runtime_root)
        runs = [item for item in index.get("runs", []) if isinstance(item, dict)]
        summary = dict(index.get("summary", {}) or {})
        return {
            "ok": bool(index.get("ok", True)),
            "generated_at": str(index.get("generated_at", "")),
            "runtime_data_dir": str(runtime_root),
            "profile": str(index.get("profile", profile_name or "service")),
            "summary": {
                "total_indexed_runs": int(summary.get("total_indexed_runs", len(runs)) or len(runs)),
                "healthy_count": int(summary.get("healthy_count", 0) or 0),
                "pending_count": int(summary.get("pending_count", 0) or 0),
                "warning_count": int(summary.get("warning_count", 0) or 0),
                "failed_count": int(summary.get("failed_count", 0) or 0),
                "stuck_count": int(summary.get("stuck_count", 0) or 0),
                "blocked_count": int(summary.get("blocked_count", 0) or 0),
            },
            "latest_failed_runs": list(index.get("latest_failed_runs", []))[: max(20, threshold_failed_frames)],
            "latest_pending_runs": list(index.get("latest_pending_runs", []))[: max(20, threshold_failed_frames)],
            "latest_stuck_runs": list(index.get("latest_stuck_runs", []))[: max(20, threshold_failed_frames)],
            "latest_blocked_runs": list(index.get("latest_blocked_runs", []))[: max(20, threshold_failed_frames)],
            "latest_external_dependency_failures": list(index.get("latest_external_dependency_failures", []))[: max(20, threshold_failed_frames)],
            "latest_auth_failures": list(index.get("latest_auth_failures", []))[: max(20, threshold_failed_frames)],
            "run_health_index_path": str(get_run_health_index_path(runtime_root)),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "latest_failed_runs": [], "latest_stuck_runs": [], "latest_pending_runs": [], "latest_blocked_runs": [], "summary": {}}


def _is_runtime_data_writable(runtime_root: Path) -> bool:
    try:
        if runtime_root.exists():
            return bool(runtime_root.is_dir() and os.access(runtime_root, os.W_OK))
        return bool(os.access(runtime_root.parent, os.W_OK))
    except Exception:
        return False


def _build_section(
    ok: bool,
    *,
    status: str | None = None,
    summary: str = "",
    details: dict[str, Any] | list[Any] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    if status is None:
        status = "OK" if ok else "FAIL"
    if status not in _SECTION_STATUSES:
        status = "FAIL" if not ok else "OK"
    return {
        "ok": bool(ok),
        "status": status,
        "summary": summary,
        "details": details if details is not None else {},
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _summarize_check_list(checks: list[dict[str, Any]]) -> str:
    passed = sum(1 for item in checks if isinstance(item, dict) and str(item.get("status", "")).upper() == "PASS")
    failed = sum(1 for item in checks if isinstance(item, dict) and str(item.get("status", "")).upper() == "FAIL")
    return f"{passed} passed, {failed} failed"


def _summarize_worker(worker_status: dict[str, Any]) -> str:
    worker_id = str(worker_status.get("worker_id", "") or "unknown")
    state = str(worker_status.get("status", "") or "STOPPED")
    return f"Worker {worker_id} is {state.lower()}."


def _summarize_worker_hardening(worker_hardening: dict[str, Any]) -> str:
    return str(worker_hardening.get("classification", "BLOCKED")).title()


def _summarize_worker_soak(worker_soak: dict[str, Any]) -> str:
    if not worker_soak:
        return "No soak report is available."
    return f"{worker_soak.get('cycles_completed', 0)} / {worker_soak.get('cycles_requested', 0)} cycles completed."


def _summarize_scheduler(scheduler_status: dict[str, Any]) -> str:
    return f"{scheduler_status.get('total_schedules', 0)} schedules, {scheduler_status.get('enabled_count', 0)} enabled."


def _summarize_queue(queue_status: dict[str, Any]) -> str:
    return f"{queue_status.get('total', 0)} queue records."


def _summarize_event_sources(event_sources: dict[str, Any]) -> str:
    return f"{event_sources.get('source_count', 0)} event sources."


def _summarize_recovery(recovery: dict[str, Any]) -> str:
    return str(recovery.get("recovery_status", "skipped"))


def _summarize_tool_health(tool_health: dict[str, Any]) -> str:
    return str(tool_health.get("status", "unknown")).upper()


def _summarize_manifest_health(manifest_health: dict[str, Any]) -> str:
    return str(manifest_health.get("status", "unknown"))


def _summarize_live_safety(live_safety: dict[str, Any]) -> str:
    return str(live_safety.get("summary", "") or "Live safety status checked.")


def _summarize_pending_actions(pending_actions: dict[str, Any], live_safety: dict[str, Any]) -> str:
    return f"{pending_actions.get('pending_action_count', 0)} pending actions; {live_safety.get('live_ready_action_count', 0)} live-ready."


def _summarize_runtime_profile(runtime_profile: dict[str, Any], worker_identity: dict[str, Any]) -> str:
    identity = "present" if worker_identity.get("worker_id") else "missing"
    return f"{runtime_profile.get('profile', 'unknown')} profile; worker identity {identity}."


def _summarize_storage(storage: dict[str, Any]) -> str:
    return f"{storage.get('issue_count', 0)} issues; {storage.get('corrupted_path_count', 0)} corrupted paths."


def _map_hardening_status(classification: str) -> str:
    if classification == "READY":
        return "OK"
    if classification == "DEGRADED":
        return "WARN"
    return "FAIL"


def _map_soak_status(worker_soak: dict[str, Any]) -> str:
    if not worker_soak:
        return "SKIPPED"
    if worker_soak.get("ok", False):
        return "OK" if not worker_soak.get("warnings") else "WARN"
    return "FAIL"


def _map_recovery_status(recovery: dict[str, Any]) -> str:
    if not recovery or recovery.get("recovery_status") == "skipped":
        return "SKIPPED"
    if recovery.get("ok", False):
        return "OK"
    return "WARN" if not recovery.get("blockers") else "FAIL"


def _map_tool_health_status(tool_health: dict[str, Any]) -> str:
    status = str(tool_health.get("status", "unknown")).lower()
    if not tool_health.get("results"):
        return "SKIPPED"
    if status == "ready":
        return "OK"
    if status == "degraded":
        return "WARN"
    if status in {"blocked", "failing"}:
        return "WARN"
    return "WARN"


def _map_manifest_health_status(manifest_health: dict[str, Any]) -> str:
    if not manifest_health.get("manifests"):
        return "SKIPPED"
    status = str(manifest_health.get("status", "UNKNOWN")).upper()
    if status == "HEALTHY":
        return "OK"
    if status in {"WARNING", "DEGRADED"}:
        return "WARN"
    if status == "FAILED":
        return "FAIL"
    return "WARN"


def _map_live_safety_status(runtime_profile: dict[str, Any], live_safety: dict[str, Any]) -> str:
    if bool(runtime_profile.get("allow_live_side_effects", False)):
        return "FAIL"
    if bool(runtime_profile.get("allow_live_reads", False)):
        return "WARN"
    if bool(runtime_profile.get("worker_identity_required", False)) and not live_safety.get("default_mode"):
        return "WARN"
    return "OK"


def _map_pending_action_status(pending_actions: dict[str, Any], live_safety: dict[str, Any]) -> str:
    if pending_actions.get("pending_action_count", 0) == 0:
        return "OK"
    if live_safety.get("live_ready_action_count", 0):
        return "WARN"
    return "WARN"


def _map_runtime_profile_status(runtime_profile: dict[str, Any], service_preflight: dict[str, Any], worker_identity: dict[str, Any]) -> str:
    if not runtime_profile.get("profile"):
        return "FAIL"
    if runtime_profile.get("profile") == "live" or runtime_profile.get("allow_live_side_effects", False):
        return "FAIL"
    if runtime_profile.get("profile") == "service" and not worker_identity.get("worker_id"):
        return "FAIL"
    if runtime_profile.get("profile") == "service" and not service_preflight.get("ok", False):
        return "FAIL"
    return "OK"


def _map_storage_status(storage: dict[str, Any]) -> str:
    if not storage.get("ok", False):
        return "FAIL"
    if storage.get("issue_count", 0) or storage.get("corrupted_path_count", 0):
        return "WARN"
    return "OK"


def _collect_blockers(sections: dict[str, Any], alert_candidates: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for candidate in alert_candidates:
        if candidate.get("severity") == "critical":
            blockers.append(f"{candidate.get('title', '')}: {candidate.get('message', '')}")
    for name, section in sections.items():
        if isinstance(section, dict) and section.get("status") == "FAIL":
            blockers.append(f"{name}: {section.get('summary', '')}")
    return list(dict.fromkeys(blockers))


def _collect_warnings(sections: dict[str, Any], alert_candidates: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for candidate in alert_candidates:
        if candidate.get("severity") == "warning":
            warnings.append(f"{candidate.get('title', '')}: {candidate.get('message', '')}")
    for name, section in sections.items():
        if isinstance(section, dict) and section.get("status") == "WARN":
            warnings.append(f"{name}: {section.get('summary', '')}")
    return list(dict.fromkeys(warnings))


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _service_preflight_check_failed(service_preflight: dict[str, Any], check_id: str) -> bool:
    for check in service_preflight.get("checks", []) or []:
        if isinstance(check, dict) and str(check.get("id", "")) == check_id:
            return str(check.get("status", "")).upper() == "FAIL"
    return False
