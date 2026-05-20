from __future__ import annotations

from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, write_json_atomic
from runtime.run_report import generate_operator_run_report
from runtime.runtime_store import ensure_runtime_store_layout
from runtime.taskframe import create_taskframe


def seed_operational_monitoring_runtime(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    runtime_root = tmp_path / "runtime_data"
    ensure_runtime_store_layout(runtime_root)
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    assert manifest is not None, "seed manifest must exist"

    frame_ids: dict[str, str] = {}

    def save_frame(frame, *, write_report: bool = False) -> str:
        PersistenceManager(runtime_root).save_snapshot(frame)
        if write_report:
            generate_operator_run_report(runtime_root, frame.frame_id, rebuild=True)
        return frame.frame_id

    completed = create_taskframe(manifest)
    completed.state = "COMPLETED"
    completed.updated_at = "2026-05-20T10:00:00Z"
    frame_ids["healthy"] = save_frame(completed, write_report=True)

    failed_validation = create_taskframe(manifest)
    failed_validation.state = "FAILED_VALIDATION"
    failed_validation.errors.append({"type": "validation", "message": "Business validation failed", "data": {}, "timestamp": failed_validation.updated_at})
    frame_ids["failed_validation"] = save_frame(failed_validation)

    failed_execution = create_taskframe(manifest)
    failed_execution.state = "FAILED_EXECUTION"
    failed_execution.errors.append({"type": "tool", "message": "Tool execution failure", "data": {}, "timestamp": failed_execution.updated_at})
    frame_ids["failed_execution"] = save_frame(failed_execution)

    waiting = create_taskframe(manifest)
    waiting.state = "WAITING_FOR_EXECUTE"
    waiting.pending_actions.append({"action_id": "pa_1", "tool": "wa/send", "status": "PENDING_APPROVAL"})
    frame_ids["waiting"] = save_frame(waiting, write_report=True)

    stale = create_taskframe(manifest)
    stale.state = "RUNNING"
    stale.updated_at = "2026-05-10T10:00:00Z"
    frame_ids["stale"] = save_frame(stale, write_report=True)

    blocked_auth = create_taskframe(manifest)
    blocked_auth.state = "FAILED_EXECUTION"
    blocked_auth.errors.append({"type": "tool", "message": "invalid_grant: authentication failed", "data": {}, "timestamp": blocked_auth.updated_at})
    frame_ids["blocked_auth"] = save_frame(blocked_auth)

    blocked_dep = create_taskframe(manifest)
    blocked_dep.state = "FAILED_EXECUTION"
    blocked_dep.errors.append({"type": "tool", "message": "Connection timeout: external dependency unavailable", "data": {}, "timestamp": blocked_dep.updated_at})
    frame_ids["blocked_dep"] = save_frame(blocked_dep)

    write_json_atomic(
        runtime_root / "tool_health" / "latest_tool_health.json",
        {
            "schema_version": 1,
            "generated_at": "2026-05-20T10:00:00Z",
            "include_optional": True,
            "live_rpa": False,
            "results": [
                {
                    "tool_id": "google_workspace_readonly",
                    "ok": True,
                    "status": "ready",
                    "severity": "info",
                    "message": "Read-only Google Workspace tools are ready.",
                    "can_auto_resolve": False,
                    "recommended_action": "",
                    "checked_at": "2026-05-20T10:00:00Z",
                    "details": {},
                },
                {
                    "tool_id": "gmail",
                    "ok": False,
                    "status": "needs_auth",
                    "severity": "warning",
                    "message": "Gmail requires authentication.",
                    "can_auto_resolve": False,
                    "recommended_action": "Refresh credentials before enabling live reads.",
                    "checked_at": "2026-05-20T10:00:00Z",
                    "details": {},
                },
            ],
            "by_tool": {},
            "summary": {"tool_count": 2, "ready_count": 1, "failed_count": 1},
        },
    )

    return runtime_root, frame_ids
