from __future__ import annotations

import html as html_module
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .failure_summary import build_failure_summary, classify_workbench_failure
from .persistence import ensure_dir, read_json, write_json_atomic
from .runtime_environment import load_runtime_profile, profile_safety_summary
from .runtime_store import load_runtime_store_index, validate_runtime_store
from .taskframe import utc_now
from .tool_capabilities import ToolHealthResult
from .tool_health import check_all_tool_health, load_latest_tool_health_snapshot


DEFAULT_MONITORING_THRESHOLDS: dict[str, int] = {
    "running_stale_minutes": 10,
    "waiting_for_input_stale_hours": 24,
    "waiting_for_execute_stale_days": 7,
    "external_dependency_retry_window_minutes": 30,
}

RUN_HEALTH_INDEX_NAME = "run_health_index.json"


@dataclass(slots=True)
class RunHealthSummary:
    frame_id: str
    manifest_id: str
    state: str
    health: str
    profile: str
    created_at: str
    updated_at: str
    age_seconds: int
    current_step_id: str
    completed_steps: int
    failed_steps: int
    pending_action_count: int
    validation_failed_count: int
    tool_error_count: int
    external_error_count: int
    auth_error_count: int
    recommended_action: str
    failure_category: str = ""
    failure_title: str = ""
    failure_explanation: str = ""
    safe_to_retry: bool = True
    affected_step_id: str = ""
    stale_warning: str = ""
    report_path: str = ""
    runtime_store_issue_count: int = 0
    runtime_store_status: str = "ok"
    live_read_readiness: str = "blocked"
    live_read_reason: str = ""
    tool_health_status: str = "unknown"
    tool_health_recommended_action: str = ""
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_run_health_index_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "indexes" / RUN_HEALTH_INDEX_NAME


def load_run_health_index(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    path = get_run_health_index_path(runtime_data_dir)
    if not path.is_file():
        return _empty_run_health_index(runtime_data_dir)
    payload = read_json(path)
    return payload if isinstance(payload, dict) else _empty_run_health_index(runtime_data_dir)


def rebuild_run_health_index(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    profile_name: str | None = None,
    manifest_dir: str | Path = "manifests",
    persist: bool = True,
    thresholds: dict[str, Any] | None = None,
    refresh_tool_health: bool = False,
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    runtime_root.mkdir(parents=True, exist_ok=True)
    profile = load_runtime_profile(profile_name=profile_name)
    runtime_store_validation = validate_runtime_store(runtime_root, manifest_dir=manifest_dir)
    runtime_store_index = load_runtime_store_index(runtime_root)
    threshold_values = _normalize_thresholds(thresholds)
    tool_health_snapshot = _load_tool_health_snapshot(runtime_data_dir=runtime_root, refresh=refresh_tool_health)

    taskframes = [item for item in runtime_store_validation.get("taskframes", []) if isinstance(item, dict)]
    if not taskframes:
        taskframes = []
        for record in _taskframes_from_ledger(runtime_root):
            taskframes.append(record)

    runs: list[dict[str, Any]] = []
    for frame in taskframes:
        runs.append(
            build_run_health_summary(
                frame,
                profile=profile,
                runtime_store_validation=runtime_store_validation,
                runtime_store_index=runtime_store_index,
                tool_health_snapshot=tool_health_snapshot,
                thresholds=threshold_values,
                runtime_data_dir=runtime_root,
                manifest_dir=manifest_dir,
            ).to_dict()
        )

    runs = sorted(runs, key=lambda item: item.get("updated_at", ""), reverse=True)
    summary = _build_run_health_summary_counts(runs)
    payload = {
        "ok": True,
        "schema_version": 1,
        "generated_at": utc_now(),
        "runtime_data_dir": str(runtime_root),
        "profile": str(profile.get("profile", "demo")),
        "thresholds": threshold_values,
        "summary": summary,
        "runs": runs,
        "latest_failed_runs": _latest_by_health(runs, "failed"),
        "latest_pending_runs": _latest_by_health(runs, "pending"),
        "latest_stuck_runs": _latest_by_health(runs, "stuck"),
        "latest_blocked_runs": _latest_by_health(runs, "blocked"),
        "latest_external_dependency_failures": _latest_failure_category(runs, {"external_dependency_unavailable"}),
        "latest_auth_failures": _latest_failure_category(runs, {"external_auth_failure"}),
        "runtime_store_validation": runtime_store_validation,
        "runtime_store_index": runtime_store_index,
        "runtime_store_status": _runtime_store_status(runtime_store_validation),
        "profile_safety": profile_safety_summary(profile),
        "tool_health": tool_health_snapshot,
        "tool_health_status": _aggregate_tool_health_status(tool_health_snapshot, runtime_data_dir=runtime_root),
        "live_read_readiness": _dict_live_read_readiness(_live_read_readiness(profile, tool_health_snapshot, runtime_data_dir=runtime_root)),
    }
    if persist:
        ensure_dir(get_run_health_index_path(runtime_root).parent)
        write_json_atomic(get_run_health_index_path(runtime_root), payload)
    return payload


def build_run_health_summary(
    frame: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    runtime_store_validation: dict[str, Any] | None = None,
    runtime_store_index: dict[str, Any] | None = None,
    tool_health_snapshot: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
) -> RunHealthSummary:
    profile = dict(profile or load_runtime_profile())
    frame = dict(frame or {})
    threshold_values = _normalize_thresholds(thresholds)
    runtime_root = Path(runtime_data_dir)
    now = datetime.now(timezone.utc)
    updated_at = _parse_timestamp(frame.get("updated_at")) or _parse_timestamp(frame.get("created_at")) or now
    created_at = _parse_timestamp(frame.get("created_at")) or updated_at
    age_seconds = max(0, int((now - updated_at).total_seconds()))

    state = str(frame.get("state", "") or "")
    frame_id = str(frame.get("frame_id", "") or "")
    manifest_id = str(frame.get("manifest_id", "") or "")
    current_step_id = str(frame.get("current_step_id", "") or "")
    completed_steps = _count_status(frame, "COMPLETED")
    failed_steps = _count_failed_steps(frame)
    pending_action_count = _count_list(frame.get("pending_actions"))
    validation_failed_count = _count_validation_failures(frame)
    runtime_store_issue_count = _count_frame_runtime_store_issues(frame, runtime_store_validation)
    runtime_store_status = _runtime_store_status(runtime_store_validation or {})
    failure_summary = build_failure_summary(frame)
    failure_category = str(failure_summary.get("failure_category", "") or "")
    failure_title = str(failure_summary.get("failure_title", "") or "")
    recommended_action = str(failure_summary.get("recommended_action", "") or "")
    failure_explanation = str(failure_summary.get("operator_explanation", "") or "")
    affected_step_id = str(failure_summary.get("failed_step_id", "") or current_step_id)
    safe_to_retry = bool(failure_summary.get("safe_to_retry", True))

    tool_health_status, tool_health_recommended_action = _resolve_tool_health_for_frame(frame, tool_health_snapshot, runtime_data_dir=runtime_root)
    external_error_count, auth_error_count, tool_error_count, frame_failure_category = _count_frame_errors(frame)
    if not failure_category:
        failure_category = frame_failure_category

    stale_warning = ""
    health = "healthy"
    if profile.get("activation_blocked"):
        health = "blocked"
        recommended_action = str(profile.get("activation_block_reason", "") or "Select a safe profile before running.")
        failure_explanation = recommended_action
    elif state in {"FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION"}:
        health = "blocked" if failure_category in {"external_auth_failure", "external_dependency_unavailable", "profile_policy_block", "runtime_store_integrity_issue"} else "failed"
    elif state == "WAITING_FOR_EXECUTE":
        health = "pending"
        if age_seconds >= int(threshold_values["waiting_for_execute_stale_days"]) * 86400:
            stale_warning = "Stale approval threshold reached."
    elif state == "WAITING_FOR_INPUT":
        health = "pending"
        if age_seconds >= int(threshold_values["waiting_for_input_stale_hours"]) * 3600:
            stale_warning = "Waiting for input has gone stale."
    elif state == "RUNNING":
        if age_seconds >= int(threshold_values["running_stale_minutes"]) * 60:
            health = "stuck"
            stale_warning = "Run has not advanced within the stale threshold."
        else:
            health = "pending"
    elif state in {"READY", "CREATED", "VALIDATING", "EXECUTING_PENDING", "VERIFYING"}:
        health = "pending"
    elif state.startswith("COMPLETED"):
        health = "warning" if (validation_failed_count or runtime_store_issue_count or tool_error_count or external_error_count or auth_error_count) else "healthy"
    elif state == "CANCELLED":
        health = "warning"
        recommended_action = recommended_action or "Review why the run was cancelled."
    elif state == "EXPIRED":
        health = "blocked"

    if health in {"failed", "blocked"} and failure_category in {"external_auth_failure", "external_dependency_unavailable"}:
        health = "blocked"
    if runtime_store_issue_count and health == "healthy":
        health = "warning"
        stale_warning = stale_warning or "Runtime store integrity issues were detected."
    if external_error_count and health in {"healthy", "pending"}:
        health = "blocked" if state.startswith("FAILED") else "warning"
    if auth_error_count and health in {"healthy", "pending"}:
        health = "blocked" if state.startswith("FAILED") else "warning"
    if validation_failed_count and health == "healthy":
        health = "warning"

    live_read_status, live_read_reason = _live_read_readiness(profile, tool_health_snapshot, runtime_data_dir=runtime_root)
    report_path = _resolve_report_path(frame_id, runtime_root)

    return RunHealthSummary(
        frame_id=frame_id,
        manifest_id=manifest_id,
        state=state,
        health=health,
        profile=str(profile.get("profile", "demo")),
        created_at=_format_timestamp(created_at),
        updated_at=_format_timestamp(updated_at),
        age_seconds=age_seconds,
        current_step_id=current_step_id,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        pending_action_count=pending_action_count,
        validation_failed_count=validation_failed_count,
        tool_error_count=tool_error_count,
        external_error_count=external_error_count,
        auth_error_count=auth_error_count,
        recommended_action=recommended_action or _recommended_action_for_state(state, stale_warning),
        failure_category=failure_category,
        failure_title=failure_title,
        failure_explanation=failure_explanation or recommended_action,
        safe_to_retry=safe_to_retry,
        affected_step_id=affected_step_id,
        stale_warning=stale_warning,
        report_path=report_path,
        runtime_store_issue_count=runtime_store_issue_count,
        runtime_store_status=runtime_store_status,
        live_read_readiness=live_read_status,
        live_read_reason=live_read_reason,
        tool_health_status=tool_health_status,
        tool_health_recommended_action=tool_health_recommended_action,
        source_path=str(frame.get("artifact_dir", "")),
    )


def build_monitoring_summary(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    profile_name: str | None = None,
    manifest_dir: str | Path = "manifests",
    limit: int = 20,
    rebuild: bool = False,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = rebuild_run_health_index(
        runtime_data_dir,
        profile_name=profile_name,
        manifest_dir=manifest_dir,
        persist=True,
        thresholds=thresholds,
        refresh_tool_health=rebuild,
    ) if rebuild or not get_run_health_index_path(runtime_data_dir).is_file() else load_run_health_index(runtime_data_dir)
    runs = [item for item in index.get("runs", []) if isinstance(item, dict)]
    summary = dict(index.get("summary", {}) or {})
    newest_failure = _first_item(index.get("latest_failed_runs", []))
    oldest_pending = _oldest_pending(index.get("latest_pending_runs", []))
    payload = {
        "ok": bool(index.get("ok", True)),
        "generated_at": str(index.get("generated_at", "")),
        "runtime_data_dir": str(Path(runtime_data_dir)),
        "profile": str(index.get("profile", profile_name or "demo")),
        "summary": {
            "total_indexed_runs": int(summary.get("total_indexed_runs", len(runs)) or len(runs)),
            "healthy_count": int(summary.get("healthy_count", 0) or 0),
            "pending_count": int(summary.get("pending_count", 0) or 0),
            "warning_count": int(summary.get("warning_count", 0) or 0),
            "failed_count": int(summary.get("failed_count", 0) or 0),
            "stuck_count": int(summary.get("stuck_count", 0) or 0),
            "blocked_count": int(summary.get("blocked_count", 0) or 0),
        },
        "tool_health_status": dict(index.get("tool_health_status", {})),
        "runtime_store_validation": dict(index.get("runtime_store_validation", {})),
        "runtime_store_status": dict(index.get("runtime_store_status", {})),
        "profile_safety": dict(index.get("profile_safety", {})),
        "live_read_readiness": _coerce_mapping(index.get("live_read_readiness", {})),
        "newest_failure": newest_failure,
        "oldest_pending_approval": oldest_pending,
        "latest_failed_runs": list(index.get("latest_failed_runs", []))[:limit],
        "latest_pending_runs": list(index.get("latest_pending_runs", []))[:limit],
        "latest_stuck_runs": list(index.get("latest_stuck_runs", []))[:limit],
        "latest_blocked_runs": list(index.get("latest_blocked_runs", []))[:limit],
        "latest_external_dependency_failures": list(index.get("latest_external_dependency_failures", []))[:limit],
        "latest_auth_failures": list(index.get("latest_auth_failures", []))[:limit],
        "run_health_index_path": str(get_run_health_index_path(runtime_data_dir)),
    }
    return payload


def build_operational_monitoring_report(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    profile_name: str | None = None,
    manifest_dir: str | Path = "manifests",
    limit: int = 20,
    rebuild: bool = False,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = build_monitoring_summary(
        runtime_data_dir,
        profile_name=profile_name,
        manifest_dir=manifest_dir,
        limit=limit,
        rebuild=rebuild,
        thresholds=thresholds,
    )
    runtime_root = Path(runtime_data_dir)
    out_dir = ensure_dir(runtime_root / "monitoring")
    timestamp = _safe_timestamp(utc_now())
    json_path = out_dir / f"operational_health_{timestamp}.json"
    md_path = out_dir / f"operational_health_{timestamp}.md"
    html_path = out_dir / f"operational_health_{timestamp}.html"

    report = {
        "ok": True,
        "report_type": "operational_monitoring",
        "schema_version": 1,
        "generated_at": utc_now(),
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "html_path": str(html_path),
        "summary": summary,
        "recommended_actions": _recommended_operator_actions(summary),
    }
    write_json_atomic(json_path, report)
    md_path.write_text(_render_operational_monitoring_markdown(report), encoding="utf-8")
    html_path.write_text(_render_operational_monitoring_html(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["markdown_path"] = str(md_path)
    report["html_path"] = str(html_path)
    return report


def aggregate_tool_health(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    snapshot = _load_tool_health_snapshot(runtime_data_dir=runtime_data_dir, refresh=refresh)
    results = [item for item in snapshot.get("results", []) if isinstance(item, dict)]
    counts: dict[str, int] = {}
    for item in results:
        status = str(item.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    status = "ready"
    recommended_action = ""
    if counts.get("failing") or counts.get("missing_dependency") or counts.get("needs_auth"):
        status = "blocked" if counts.get("missing_dependency") or counts.get("needs_auth") else "degraded"
        recommended_action = "Resolve tool health blockers before relying on live-read operations."
    elif counts.get("disabled_optional"):
        status = "degraded"
        recommended_action = "Optional tools are disabled; this is safe for demo and release."
    return {
        "ok": True,
        "generated_at": str(snapshot.get("generated_at", "")),
        "results": results,
        "summary": {
            "total": len(results),
            "ready": counts.get("ready", 0),
            "needs_auth": counts.get("needs_auth", 0),
            "missing_dependency": counts.get("missing_dependency", 0),
            "misconfigured": counts.get("misconfigured", 0),
            "failing": counts.get("failing", 0),
            "disabled_optional": counts.get("disabled_optional", 0),
            "unknown": counts.get("unknown", 0),
        },
        "status": status,
        "recommended_action": recommended_action,
        "by_tool": dict(snapshot.get("by_tool", {}) or {}),
    }


def _render_operational_monitoring_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    counts = summary.get("summary", {}) if isinstance(summary.get("summary", {}), dict) else {}
    lines = [
        "# Operational Health",
        "",
        "## Summary",
        "",
        f"- Total indexed runs: {counts.get('total_indexed_runs', 0)}",
        f"- Healthy: {counts.get('healthy_count', 0)}",
        f"- Pending: {counts.get('pending_count', 0)}",
        f"- Warning: {counts.get('warning_count', 0)}",
        f"- Failed: {counts.get('failed_count', 0)}",
        f"- Stuck: {counts.get('stuck_count', 0)}",
        f"- Blocked: {counts.get('blocked_count', 0)}",
        "",
        "## Runtime Store",
        "",
        f"- Validation ok: {str(summary.get('runtime_store_validation', {}).get('ok', False)).lower()}",
        f"- Runtime store status: {summary.get('runtime_store_status', {}).get('status', 'unknown')}",
        f"- Live-read readiness: {summary.get('live_read_readiness', {}).get('status', 'blocked')}",
        "",
        "## Profile Safety",
        "",
        f"- Profile: {summary.get('profile_safety', {}).get('profile', '')}",
        f"- Safe for demo: {str(summary.get('profile_safety', {}).get('safe_for_demo', False)).lower()}",
        f"- Safe for pilot: {str(summary.get('profile_safety', {}).get('safe_for_pilot', False)).lower()}",
        f"- Safe for release: {str(summary.get('profile_safety', {}).get('safe_for_release', False)).lower()}",
        "",
        "## Failed Runs",
        "",
        _render_markdown_table(summary.get("latest_failed_runs", []), ["frame_id", "manifest_id", "state", "health", "failure_category", "recommended_action", "report_path"]),
        "",
        "## Pending Approvals",
        "",
        _render_markdown_table(summary.get("latest_pending_runs", []), ["frame_id", "manifest_id", "state", "health", "stale_warning", "recommended_action", "report_path"]),
        "",
        "## Stuck Runs",
        "",
        _render_markdown_table(summary.get("latest_stuck_runs", []), ["frame_id", "manifest_id", "state", "health", "stale_warning", "recommended_action", "report_path"]),
        "",
        "## Blocked Dependencies",
        "",
        _render_markdown_table(summary.get("latest_blocked_runs", []), ["frame_id", "manifest_id", "state", "health", "failure_category", "recommended_action", "report_path"]),
        "",
        "## Tool Health",
        "",
        _render_tool_health_markdown(summary.get("tool_health_status", {})),
        "",
        "## Recommended Operator Actions",
        "",
    ]
    for action in report.get("recommended_actions", []):
        lines.append(f"- {action}")
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def _render_operational_monitoring_html(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    counts = summary.get("summary", {}) if isinstance(summary.get("summary", {}), dict) else {}
    body = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Operational Health</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #d1d5db;padding:8px;vertical-align:top;text-align:left}th{background:#f3f4f6}</style>",
        "</head><body>",
        "<h1>Operational Health</h1>",
        "<h2>Summary</h2>",
        "<ul>",
        *[f"<li>{html_module.escape(label)}: {html_module.escape(str(value))}</li>" for label, value in (
            ("Total indexed runs", counts.get("total_indexed_runs", 0)),
            ("Healthy", counts.get("healthy_count", 0)),
            ("Pending", counts.get("pending_count", 0)),
            ("Warning", counts.get("warning_count", 0)),
            ("Failed", counts.get("failed_count", 0)),
            ("Stuck", counts.get("stuck_count", 0)),
            ("Blocked", counts.get("blocked_count", 0)),
        )],
        "</ul>",
        "<h2>Failed Runs</h2>",
        _render_html_table(summary.get("latest_failed_runs", []), ["frame_id", "manifest_id", "state", "health", "failure_category", "recommended_action", "report_path"]),
        "<h2>Pending Approvals</h2>",
        _render_html_table(summary.get("latest_pending_runs", []), ["frame_id", "manifest_id", "state", "health", "stale_warning", "recommended_action", "report_path"]),
        "<h2>Stuck Runs</h2>",
        _render_html_table(summary.get("latest_stuck_runs", []), ["frame_id", "manifest_id", "state", "health", "stale_warning", "recommended_action", "report_path"]),
        "<h2>Blocked Dependencies</h2>",
        _render_html_table(summary.get("latest_blocked_runs", []), ["frame_id", "manifest_id", "state", "health", "failure_category", "recommended_action", "report_path"]),
        "<h2>Tool Health</h2>",
        _render_tool_health_html(summary.get("tool_health_status", {})),
        "<h2>Recommended Operator Actions</h2>",
        "<ul>",
        *[f"<li>{html_module.escape(str(action))}</li>" for action in report.get("recommended_actions", [])],
        "</ul>",
        "</body></html>",
    ]
    return "".join(body)


def _render_markdown_table(items: list[dict[str, Any]], columns: list[str]) -> str:
    rows = [item for item in items if isinstance(item, dict)]
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, divider]
    if not rows:
        lines.append("| " + " | ".join(["(none)"] * len(columns)) + " |")
        return "\n".join(lines)
    for item in rows:
        values = [str(item.get(column, "")) for column in columns]
        lines.append("| " + " | ".join(_escape_markdown(value) for value in values) + " |")
    return "\n".join(lines)


def _render_html_table(items: list[dict[str, Any]], columns: list[str]) -> str:
    rows = [item for item in items if isinstance(item, dict)]
    if not rows:
        return "<p>(none)</p>"
    parts = ["<table><thead><tr>"]
    for column in columns:
        parts.append(f"<th>{html_module.escape(column)}</th>")
    parts.append("</tr></thead><tbody>")
    for item in rows:
        parts.append("<tr>")
        for column in columns:
            parts.append(f"<td>{html_module.escape(str(item.get(column, '')))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _render_tool_health_markdown(tool_health: dict[str, Any]) -> str:
    summary = dict(tool_health.get("summary", {}) or {})
    lines = [
        f"- Status: {tool_health.get('status', 'unknown')}",
        f"- Total checks: {summary.get('total', 0)}",
        f"- Ready: {summary.get('ready', 0)}",
        f"- Needs auth: {summary.get('needs_auth', 0)}",
        f"- Missing dependency: {summary.get('missing_dependency', 0)}",
        f"- Misconfigured: {summary.get('misconfigured', 0)}",
        f"- Failing: {summary.get('failing', 0)}",
        f"- Disabled optional: {summary.get('disabled_optional', 0)}",
        f"- Unknown: {summary.get('unknown', 0)}",
    ]
    if tool_health.get("recommended_action"):
        lines.append(f"- Recommended action: {tool_health.get('recommended_action')}")
    return "\n".join(lines)


def _render_tool_health_html(tool_health: dict[str, Any]) -> str:
    summary = dict(tool_health.get("summary", {}) or {})
    rows = [
        ("Status", tool_health.get("status", "unknown")),
        ("Total checks", summary.get("total", 0)),
        ("Ready", summary.get("ready", 0)),
        ("Needs auth", summary.get("needs_auth", 0)),
        ("Missing dependency", summary.get("missing_dependency", 0)),
        ("Misconfigured", summary.get("misconfigured", 0)),
        ("Failing", summary.get("failing", 0)),
        ("Disabled optional", summary.get("disabled_optional", 0)),
        ("Unknown", summary.get("unknown", 0)),
    ]
    html_lines = ["<table><tbody>"]
    for label, value in rows:
        html_lines.append(f"<tr><th>{html_module.escape(str(label))}</th><td>{html_module.escape(str(value))}</td></tr>")
    html_lines.append("</tbody></table>")
    if tool_health.get("recommended_action"):
        html_lines.append(f"<p>{html_module.escape(str(tool_health.get('recommended_action')))}</p>")
    return "".join(html_lines)


def _recommended_operator_actions(summary: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if summary.get("runtime_store_validation", {}).get("ok") is False:
        actions.append("Repair the runtime store before relying on the monitoring index.")
    if summary.get("live_read_readiness", {}).get("status") == "blocked":
        actions.append("Resolve live-read readiness blockers before pilot live-read checks.")
    if int(summary.get("failed_count", 0) or 0) > 0:
        actions.append("Review the newest failed runs and inspect their reports.")
    if int(summary.get("pending_count", 0) or 0) > 0:
        actions.append("Check waiting approvals and stale pending runs.")
    if int(summary.get("blocked_count", 0) or 0) > 0:
        actions.append("Review external auth and dependency failures first.")
    if int(summary.get("stuck_count", 0) or 0) > 0:
        actions.append("Investigate stale RUNNING frames before re-running anything.")
    if not actions:
        actions.append("No immediate operator action is required.")
    return actions


def _taskframes_from_ledger(runtime_root: Path) -> list[dict[str, Any]]:
    from .run_ledger import read_ledger_records

    latest: dict[str, dict[str, Any]] = {}
    for record in read_ledger_records(runtime_root):
        if isinstance(record, dict) and str(record.get("frame_id", "")).strip():
            latest[str(record["frame_id"])] = dict(record)
    return sorted(latest.values(), key=lambda item: str(item.get("updated_at", "")), reverse=True)


def _build_run_health_summary_counts(runs: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "total_indexed_runs": len(runs),
        "healthy_count": 0,
        "pending_count": 0,
        "warning_count": 0,
        "failed_count": 0,
        "stuck_count": 0,
        "blocked_count": 0,
    }
    for item in runs:
        health = str(item.get("health", "")).lower()
        if health == "healthy":
            counts["healthy_count"] += 1
        elif health == "pending":
            counts["pending_count"] += 1
        elif health == "warning":
            counts["warning_count"] += 1
        elif health == "failed":
            counts["failed_count"] += 1
        elif health == "stuck":
            counts["stuck_count"] += 1
        elif health == "blocked":
            counts["blocked_count"] += 1
    return counts


def _latest_by_health(runs: list[dict[str, Any]], health: str) -> list[dict[str, Any]]:
    filtered = [item for item in runs if str(item.get("health", "")).lower() == health.lower()]
    return filtered[:20]


def _latest_failure_category(runs: list[dict[str, Any]], categories: set[str]) -> list[dict[str, Any]]:
    filtered = [item for item in runs if str(item.get("failure_category", "")) in categories]
    return filtered[:20]


def _first_item(items: list[dict[str, Any]] | Any) -> dict[str, Any]:
    if isinstance(items, list) and items:
        first = items[0]
        return dict(first) if isinstance(first, dict) else {}
    return {}


def _oldest_pending(items: list[dict[str, Any]] | Any) -> dict[str, Any]:
    if not isinstance(items, list) or not items:
        return {}
    ordered = [item for item in items if isinstance(item, dict)]
    ordered.sort(key=lambda item: str(item.get("updated_at", "")))
    return dict(ordered[0]) if ordered else {}


def _runtime_store_status(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(validation.get("ok", False)),
        "index_rebuildable": bool(validation.get("index_rebuildable", False)),
        "issue_count": len([item for item in validation.get("issues", []) if isinstance(item, dict)]),
        "corrupted_path_count": len(validation.get("corrupted_paths", []) if isinstance(validation.get("corrupted_paths", []), list) else []),
    }


def _count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _count_status(frame: dict[str, Any], status: str) -> int:
    steps = frame.get("steps", [])
    if not isinstance(steps, list):
        return 0
    return sum(1 for item in steps if isinstance(item, dict) and str(item.get("status", "")).upper() == status.upper())


def _count_failed_steps(frame: dict[str, Any]) -> int:
    steps = frame.get("steps", [])
    if not isinstance(steps, list):
        return 0
    return sum(1 for item in steps if isinstance(item, dict) and str(item.get("status", "")).upper().startswith("FAILED"))


def _count_validation_failures(frame: dict[str, Any]) -> int:
    validations = frame.get("validations", [])
    if not isinstance(validations, list):
        return 0
    return sum(1 for item in validations if isinstance(item, dict) and item.get("ok") is False)


def _count_frame_runtime_store_issues(frame: dict[str, Any], runtime_store_validation: dict[str, Any] | None) -> int:
    if not isinstance(runtime_store_validation, dict):
        return 0
    frame_path = str(frame.get("artifact_dir", "")).strip()
    if not frame_path:
        return 0
    count = 0
    for issue in runtime_store_validation.get("issues", []):
        if not isinstance(issue, dict):
            continue
        if str(issue.get("path", "")).startswith(frame_path):
            count += 1
    return count


def _count_frame_errors(frame: dict[str, Any]) -> tuple[int, int, int, str]:
    errors = frame.get("errors", [])
    if not isinstance(errors, list):
        return 0, 0, 0, ""
    external_error_count = 0
    auth_error_count = 0
    tool_error_count = 0
    failure_category = ""
    for error in errors:
        classification = classify_workbench_failure(error, _find_error_step(frame, error))
        category = str(classification.get("category", "") or "")
        if not failure_category:
            failure_category = category
        if category == "external_auth_failure":
            auth_error_count += 1
            external_error_count += 1
        elif category == "external_dependency_unavailable":
            external_error_count += 1
        elif category == "tool_execution_failure":
            tool_error_count += 1
    return external_error_count, auth_error_count, tool_error_count, failure_category


def _find_error_step(frame: dict[str, Any], error: Any) -> dict[str, Any]:
    step_id = ""
    if isinstance(error, dict):
        step_id = str(error.get("step_id", "") or "")
    if not step_id:
        return {}
    for step in frame.get("steps", []):
        if isinstance(step, dict) and str(step.get("step_id", "") or step.get("id", "")) == step_id:
            return dict(step)
    return {}


def _resolve_tool_health_for_frame(
    frame: dict[str, Any],
    tool_health_snapshot: dict[str, Any] | None,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> tuple[str, str]:
    snapshot = tool_health_snapshot if isinstance(tool_health_snapshot, dict) else load_latest_tool_health_snapshot(runtime_data_dir)
    results = snapshot.get("results", []) if isinstance(snapshot.get("results", []), list) else []
    tool_candidates: list[str] = []
    for pending in frame.get("pending_actions", []):
        if not isinstance(pending, dict):
            continue
        tool = str(pending.get("tool", "") or "").strip()
        if tool:
            tool_candidates.append(tool)
    for call in frame.get("tool_calls", []):
        if not isinstance(call, dict):
            continue
        tool = str(call.get("tool", "") or "").strip()
        if tool:
            tool_candidates.append(tool)
    for tool_id in tool_candidates:
        for item in results:
            if isinstance(item, dict) and str(item.get("tool_id", "")) == tool_id:
                status = str(item.get("status", "unknown"))
                recommended_action = str(item.get("recommended_action", "") or "")
                if status in {"needs_auth", "missing_dependency", "misconfigured", "failing"}:
                    return "blocked", recommended_action
                if status == "disabled_optional":
                    return "warning", recommended_action
                return "ready", recommended_action
    if results:
        summary = aggregate_tool_health(runtime_data_dir)
        return str(summary.get("status", "unknown")), str(summary.get("recommended_action", "") or "")
    return "unknown", ""


def _aggregate_tool_health_status(tool_health_snapshot: dict[str, Any] | None, runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    snapshot = tool_health_snapshot if isinstance(tool_health_snapshot, dict) else load_latest_tool_health_snapshot(runtime_data_dir)
    results = [item for item in snapshot.get("results", []) if isinstance(item, dict)]
    counts: dict[str, int] = {}
    for item in results:
        status = str(item.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    overall = "ready"
    if counts.get("needs_auth") or counts.get("missing_dependency") or counts.get("failing"):
        overall = "blocked" if counts.get("needs_auth") or counts.get("missing_dependency") else "warning"
    elif counts.get("disabled_optional"):
        overall = "warning"
    recommended_action = ""
    if overall == "blocked":
        recommended_action = "Resolve missing dependencies and authentication before pilot live-read use."
    elif overall == "warning":
        recommended_action = "Review optional or failing tool health before expanding live-read scope."
    return {
        "status": overall,
        "summary": {
            "total": len(results),
            "ready": counts.get("ready", 0),
            "needs_auth": counts.get("needs_auth", 0),
            "missing_dependency": counts.get("missing_dependency", 0),
            "misconfigured": counts.get("misconfigured", 0),
            "failing": counts.get("failing", 0),
            "disabled_optional": counts.get("disabled_optional", 0),
            "unknown": counts.get("unknown", 0),
        },
        "recommended_action": recommended_action,
    }


def _live_read_readiness(profile: dict[str, Any], tool_health_snapshot: dict[str, Any] | None, runtime_data_dir: str | Path = "runtime_data") -> tuple[str, str]:
    if not profile.get("allow_live_reads", False):
        return "blocked", "Active profile does not allow live reads."
    if profile.get("activation_blocked"):
        return "blocked", str(profile.get("activation_block_reason", "") or "Profile activation is blocked.")
    tool_status = _aggregate_tool_health_status(tool_health_snapshot, runtime_data_dir=runtime_data_dir)
    if tool_status["status"] == "blocked":
        return "blocked", str(tool_status.get("recommended_action", "") or "Tool health blockers must be resolved first.")
    if tool_status["status"] == "warning":
        return "warning", str(tool_status.get("recommended_action", "") or "Tool health is degraded.")
    return "ready", "Live reads are allowed for the active profile and tool health is ready."


def _resolve_report_path(frame_id: str, runtime_root: Path) -> str:
    if not frame_id:
        return ""
    html = runtime_root / "runs" / frame_id / "reports" / "run_report.html"
    md = runtime_root / "runs" / frame_id / "reports" / "run_report.md"
    if html.is_file():
        return str(html)
    if md.is_file():
        return str(md)
    return ""


def _recommended_action_for_state(state: str, stale_warning: str) -> str:
    if stale_warning:
        return stale_warning
    if state == "WAITING_FOR_EXECUTE":
        return "Review the pending approval pack and advance the approval workflow."
    if state == "WAITING_FOR_INPUT":
        return "Provide the missing input before rerunning the frame."
    if state == "RUNNING":
        return "Check whether the worker is still making progress or is blocked."
    if state == "COMPLETED":
        return "No immediate operator action is needed."
    return "Inspect the frame and run report for next steps."


def _dict_live_read_readiness(value: tuple[str, str] | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, tuple) and len(value) >= 2:
        return {"status": str(value[0]), "reason": str(value[1])}
    return {"status": "blocked", "reason": "Unavailable."}


def _normalize_thresholds(thresholds: dict[str, Any] | None) -> dict[str, int]:
    normalized = dict(DEFAULT_MONITORING_THRESHOLDS)
    if isinstance(thresholds, dict):
        for key in normalized:
            value = thresholds.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                normalized[key] = int(value)
    return normalized


def _load_tool_health_snapshot(*, runtime_data_dir: str | Path = "runtime_data", refresh: bool = False) -> dict[str, Any]:
    snapshot = load_latest_tool_health_snapshot(runtime_data_dir)
    if refresh or not snapshot.get("results"):
        check_all_tool_health(include_optional=True, live_rpa=False, runtime_data_dir=runtime_data_dir)
        snapshot = load_latest_tool_health_snapshot(runtime_data_dir)
    return snapshot


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, tuple) and len(value) >= 2:
        return {"status": str(value[0]), "reason": str(value[1])}
    return {}


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_timestamp(value: str) -> str:
    return value.replace(":", "-").replace("Z", "Z")


def _escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _empty_run_health_index(runtime_data_dir: str | Path) -> dict[str, Any]:
    return {
        "ok": False,
        "schema_version": 1,
        "generated_at": "",
        "runtime_data_dir": str(Path(runtime_data_dir)),
        "profile": "demo",
        "thresholds": dict(DEFAULT_MONITORING_THRESHOLDS),
        "summary": _build_run_health_summary_counts([]),
        "runs": [],
        "latest_failed_runs": [],
        "latest_pending_runs": [],
        "latest_stuck_runs": [],
        "latest_blocked_runs": [],
        "latest_external_dependency_failures": [],
        "latest_auth_failures": [],
        "runtime_store_validation": {},
        "runtime_store_index": {},
        "runtime_store_status": {"ok": False, "index_rebuildable": False, "issue_count": 0, "corrupted_path_count": 0},
        "profile_safety": {},
        "tool_health": {},
        "tool_health_status": {"status": "unknown", "summary": {}, "recommended_action": ""},
        "live_read_readiness": {"status": "blocked", "reason": "No monitoring data available."},
    }
