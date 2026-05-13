from __future__ import annotations

from typing import Any

from runtime.events import create_event
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe_reload import load_taskframe
from runtime.taskframe import to_dict as taskframe_to_dict
from runtime.persistence import get_summary_path, read_json, persist_frame_update
from runtime.customer_inbox import load_customer_messages, update_customer_message
from runtime.approval import approve_all_pending_actions

from src.operator_approval_pack import build_approval_pack_view
from src.operator_data import build_operator_snapshot
from src.operator_playback import build_playback_timeline


def approve_pending_action(
    frame_id: str,
    action_id: str,
    approved_by: str = "operator_ui",
    reason: str = "",
    runtime_data_dir: str = "runtime_data",
) -> dict:
    return _run_command(
        "approve",
        frame_id,
        runtime_data_dir,
        payload={
            "frame_id": frame_id,
            "action_id": action_id,
            "approved_by": approved_by,
            "reason": reason or "Approved from operator UI dry-run control panel.",
        },
        event_type="manual.approve_pending_action",
    )


def approve_all_pending_actions_command(
    frame_id: str,
    approved_by: str = "operator_ui",
    reason: str = "",
    runtime_data_dir: str = "runtime_data",
) -> dict:
    try:
        frame = load_taskframe(frame_id, runtime_data_dir)
        approve_all_pending_actions(frame, approved_by=approved_by, reason=reason or "Approved all pending actions from operator UI dry-run control panel.")
        persist_frame_update(frame, runtime_data_dir)
        snapshot = build_operator_snapshot(runtime_data_dir)
        approval_pack = build_approval_pack_view(taskframe_to_dict(frame))
        timeline = build_playback_timeline(snapshot)
        summary = _summary_from_frame(taskframe_to_dict(frame))
        return {
            "ok": True,
            "operation": "approve_all",
            "target_frame_id": frame_id,
            "target_frame_state": str(frame.state),
            "command_frame_id": "",
            "summary": summary,
            "snapshot": snapshot,
            "timeline": timeline,
            "approval_pack": approval_pack,
            "message": "All pending actions approved.",
            "error": "",
            "approved_count": len([item for item in frame.pending_actions if item.get("status") == "APPROVED"]),
            "approved_action_ids": [item.get("action_id", "") for item in frame.pending_actions if item.get("status") == "APPROVED"],
        }
    except Exception as exc:
        return {
            "ok": False,
            "operation": "approve_all",
            "target_frame_id": frame_id,
            "target_frame_state": "",
            "command_frame_id": "",
            "summary": {},
            "snapshot": {},
            "timeline": [],
            "approval_pack": {},
            "message": "",
            "error": str(exc),
            "approved_count": 0,
            "approved_action_ids": [],
        }


def reject_pending_action(
    frame_id: str,
    action_id: str,
    rejected_by: str = "operator_ui",
    reason: str = "",
    runtime_data_dir: str = "runtime_data",
) -> dict:
    return _run_command(
        "reject",
        frame_id,
        runtime_data_dir,
        payload={
            "frame_id": frame_id,
            "action_id": action_id,
            "rejected_by": rejected_by,
            "reason": reason or "Rejected from operator UI dry-run control panel.",
        },
        event_type="manual.reject_pending_action",
    )


def execute_approved_pending_actions_dry_run(
    frame_id: str,
    runtime_data_dir: str = "runtime_data",
) -> dict:
    return _run_command(
        "execute_approved_dry_run",
        frame_id,
        runtime_data_dir,
        payload={"frame_id": frame_id},
        event_type="manual.execute_approved_pending_actions",
    )


def reload_operator_run(
    frame_id: str,
    runtime_data_dir: str = "runtime_data",
) -> dict:
    snapshot = build_operator_snapshot(runtime_data_dir)
    try:
        loaded = load_taskframe(frame_id, runtime_data_dir)
        target_frame = taskframe_to_dict(loaded)
    except Exception:
        target_frame = None
    if not isinstance(target_frame, dict):
        target_frame = snapshot.get("frames_by_id", {}).get(frame_id) if isinstance(snapshot, dict) else None
    approval_pack = build_approval_pack_view(target_frame or {}) if isinstance(target_frame, dict) else _empty_pack()
    timeline = build_playback_timeline(snapshot)
    summary = _load_summary(frame_id, runtime_data_dir) or _summary_from_frame(target_frame)
    return {
        "ok": True,
        "operation": "reload",
        "target_frame_id": frame_id,
        "target_frame_state": str(target_frame.get("state", "")) if isinstance(target_frame, dict) else "",
        "command_frame_id": "",
        "summary": summary,
        "snapshot": snapshot,
        "timeline": timeline,
        "approval_pack": approval_pack,
        "message": "Frame reloaded.",
        "error": "",
    }


def _run_command(operation: str, frame_id: str, runtime_data_dir: str, payload: dict[str, Any], event_type: str) -> dict:
    try:
        engine = RuntimeEngine(runtime_data_dir=runtime_data_dir, persist_runs=True)
        event = create_event(event_type, "operator_ui", payload=payload)
        result = engine.handle_event(event, dry_run=True)
        command_state = getattr(result, "state", "") if not isinstance(result, dict) else str(result.get("state", ""))
        command_frame_id = getattr(result, "frame_id", "") if not isinstance(result, dict) else str(result.get("frame_id", ""))
        target_snapshot = build_operator_snapshot(runtime_data_dir)
        try:
            loaded = load_taskframe(frame_id, runtime_data_dir)
            target_frame = taskframe_to_dict(loaded)
        except Exception:
            target_frame = None
        if not isinstance(target_frame, dict):
            target_frame = target_snapshot.get("frames_by_id", {}).get(frame_id) if isinstance(target_snapshot, dict) else None
        approval_pack = build_approval_pack_view(target_frame or {}) if isinstance(target_frame, dict) else _empty_pack()
        timeline = build_playback_timeline(target_snapshot)
        summary = _load_summary(frame_id, runtime_data_dir) or _summary_from_frame(target_frame)
        _sync_customer_inbox_from_frame(frame_id, target_frame, runtime_data_dir)
        return {
            "ok": command_state not in {"FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION", "INVALID_EVENT", "NO_ROUTE", "ROUTE_MAPPING_FAILED", "MANIFEST_NOT_FOUND"},
            "operation": operation,
            "target_frame_id": frame_id,
            "target_frame_state": str(target_frame.get("state", "")) if isinstance(target_frame, dict) else "",
            "command_frame_id": command_frame_id,
            "summary": summary,
            "snapshot": target_snapshot,
            "timeline": timeline,
            "approval_pack": approval_pack,
            "message": _message_for(operation),
            "error": "" if command_state not in {"FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION", "INVALID_EVENT", "NO_ROUTE", "ROUTE_MAPPING_FAILED", "MANIFEST_NOT_FOUND"} else f"Approval command failed: {command_state}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "operation": operation,
            "target_frame_id": frame_id,
            "target_frame_state": "",
            "command_frame_id": "",
            "summary": {},
            "snapshot": {},
            "timeline": [],
            "approval_pack": {},
            "message": "",
            "error": str(exc),
        }


def _message_for(operation: str) -> str:
    return {
        "approve": "Pending action approved.",
        "approve_all": "All pending actions approved.",
        "reject": "Pending action rejected.",
        "execute_approved_dry_run": "Approved pending actions executed in dry-run mode.",
        "reload": "Frame reloaded.",
    }.get(operation, "Operation completed.")


def _empty_pack() -> dict:
    return {
        "ok": False,
        "frame_id": "",
        "manifest_id": "",
        "state": "",
        "pending_action_count": 0,
        "approval_packs": [],
        "error": "",
    }


def _load_summary(frame_id: str, runtime_data_dir: str) -> dict[str, Any]:
    if not frame_id:
        return {}
    path = get_summary_path(frame_id, runtime_data_dir)
    if not path.is_file():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _summary_from_frame(frame: dict | None) -> dict[str, Any]:
    if not isinstance(frame, dict):
        return {}
    executed_actions = frame.get("executed_actions", [])
    pending_actions = frame.get("pending_actions", [])
    return {
        "frame_id": frame.get("frame_id", ""),
        "manifest_id": frame.get("manifest_id", ""),
        "state": frame.get("state", ""),
        "executed_action_count": len(executed_actions) if isinstance(executed_actions, list) else 0,
        "pending_action_count": len(pending_actions) if isinstance(pending_actions, list) else 0,
    }


def _sync_customer_inbox_from_frame(frame_id: str, target_frame: dict | None, runtime_data_dir: str) -> None:
    if not frame_id or not isinstance(target_frame, dict):
        return
    message_id = str(target_frame.get("trigger", {}).get("message_id", "") if isinstance(target_frame.get("trigger", {}), dict) else "")
    if not message_id:
        for message in load_customer_messages(runtime_data_dir):
            if str(message.get("linked_frame_id", "")) == frame_id:
                message_id = str(message.get("message_id", ""))
                break
    if not message_id:
        return
    status = str(target_frame.get("state", ""))
    pending_actions = target_frame.get("pending_actions", [])
    pending_action_id = ""
    if isinstance(pending_actions, list) and pending_actions:
        first = pending_actions[0]
        if isinstance(first, dict):
            pending_action_id = str(first.get("action_id", ""))
    if status == "WAITING_FOR_EXECUTE":
        current = "APPROVED" if any(isinstance(item, dict) and item.get("status") == "APPROVED" for item in pending_actions) else "STAGED_REPLY"
        update_customer_message(message_id, {"status": current, "linked_frame_id": frame_id, "pending_action_id": pending_action_id}, runtime_data_dir)
    elif status in {"COMPLETED", "COMPLETED_NO_DATA"}:
        update_customer_message(message_id, {"status": "EXECUTED_DRY_RUN", "linked_frame_id": frame_id, "pending_action_id": pending_action_id, "completed_at": _now()}, runtime_data_dir)
    elif status == "FAILED_COMPLETION":
        current = "REJECTED" if any(isinstance(item, dict) and item.get("status") == "REJECTED" for item in pending_actions) else "FAILED"
        update_customer_message(message_id, {"status": current, "linked_frame_id": frame_id, "pending_action_id": pending_action_id, "failure_reason": str(target_frame.get("completion_gate_result", {}).get("message", ""))}, runtime_data_dir)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
