"""Spec 108 — Event Queue Inspector service.

Provides read-only inspection of the event queue, including queue listing,
event detail, and linked TaskFrame summaries.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .event_queue import list_queue_records, load_queue_record
from .event_failure_reason import derive_event_failure_reason
from .event_store import get_event, list_events
from .taskframe import utc_now


def list_event_queue(
    *,
    runtime_data_dir: str | Path = "runtime_data",
    status: str | None = None,
    source: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List events from the queue with optional filters.

    Returns:
        {
            "ok": bool,
            "count": int,
            "events": list[dict],
            "filters": dict,
        }
    """
    records = list_queue_records(
        runtime_data_dir=runtime_data_dir,
        status=status,
        source=source,
        event_type=event_type,
        limit=limit,
    )
    return {
        "ok": True,
        "count": len(records),
        "events": records,
        "filters": {
            "status": status,
            "source": source,
            "event_type": event_type,
            "limit": limit,
        },
    }


def get_event_detail(
    event_id: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Return full event detail including route, manifest, frame, and failure.

    Returns:
        {
            "ok": bool,
            "event_id": str,
            "event_record": dict | None,
            "queue_record": dict | None,
            "route_id": str | None,
            "manifest_id": str | None,
            "linked_frame_id": str | None,
            "frame_state": str | None,
            "completion_gate_result": dict | None,
            "failure_reason": dict,
            "errors": list[str],
            "replay_history": list,
        }
    """
    queue_record = load_queue_record(event_id, runtime_data_dir)
    event_record = get_event(event_id, runtime_data_dir)

    if queue_record is None and event_record is None:
        return {
            "ok": False,
            "event_id": event_id,
            "event_record": None,
            "queue_record": None,
            "route_id": None,
            "manifest_id": None,
            "linked_frame_id": None,
            "frame_state": None,
            "completion_gate_result": None,
            "failure_reason": {"failure_code": "NOT_FOUND", "failure_reason": f"Event not found: {event_id}", "source": "unknown"},
            "errors": [f"Event not found: {event_id}"],
            "replay_history": [],
        }

    source_record = queue_record or event_record or {}
    linked_frame_id = str(source_record.get("linked_frame_id", "") or "")
    route_id = str(source_record.get("route_id", "") or "")
    manifest_id = str(source_record.get("manifest_id", "") or "")
    errors = list(source_record.get("errors") or [])
    replay_history = list((source_record.get("metadata") or {}).get("replay_history") or [])

    frame_summary = _load_frame_summary(linked_frame_id, runtime_data_dir) if linked_frame_id else None
    frame_state = str(frame_summary.get("state", "") or "") if frame_summary else None
    completion_gate_result = frame_summary.get("completion_gate_result") if frame_summary else None

    failure_reason = derive_event_failure_reason(source_record, frame_summary)

    return {
        "ok": True,
        "event_id": event_id,
        "event_record": event_record,
        "queue_record": queue_record,
        "route_id": route_id or None,
        "manifest_id": manifest_id or None,
        "linked_frame_id": linked_frame_id or None,
        "frame_state": frame_state or None,
        "completion_gate_result": completion_gate_result,
        "failure_reason": failure_reason,
        "errors": errors,
        "replay_history": replay_history,
    }


def get_event_linked_frame_summary(
    event_id: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Return a compact summary of the TaskFrame linked to an event."""
    queue_record = load_queue_record(event_id, runtime_data_dir)
    event_record = get_event(event_id, runtime_data_dir)
    source_record = queue_record or event_record or {}
    linked_frame_id = str(source_record.get("linked_frame_id", "") or "")

    if not linked_frame_id:
        return {
            "ok": False,
            "event_id": event_id,
            "linked_frame_id": None,
            "frame_summary": None,
            "error": "No linked frame found for event.",
        }

    frame_summary = _load_frame_summary(linked_frame_id, runtime_data_dir)
    if frame_summary is None:
        return {
            "ok": False,
            "event_id": event_id,
            "linked_frame_id": linked_frame_id,
            "frame_summary": None,
            "error": f"TaskFrame artifact not found: {linked_frame_id}",
        }

    return {
        "ok": True,
        "event_id": event_id,
        "linked_frame_id": linked_frame_id,
        "frame_summary": frame_summary,
        "error": "",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_frame_summary(frame_id: str, runtime_data_dir: str | Path) -> dict[str, Any] | None:
    if not frame_id:
        return None
    try:
        from .taskframe_reload import load_taskframe
        from .taskframe import to_dict

        frame = load_taskframe(frame_id, runtime_data_dir)
        if frame is None:
            return None
        frame_dict = to_dict(frame)
        return {
            "frame_id": frame_dict.get("frame_id"),
            "state": frame_dict.get("state"),
            "manifest_id": frame_dict.get("manifest_id"),
            "created_at": frame_dict.get("created_at"),
            "updated_at": frame_dict.get("updated_at"),
            "completion_gate_result": frame_dict.get("completion_gate_result"),
            "errors": frame_dict.get("errors", []),
            "pending_actions": frame_dict.get("pending_actions", []),
            "executed_actions": frame_dict.get("executed_actions", []),
            "outputs": {k: "<present>" for k in (frame_dict.get("outputs") or {})},
        }
    except Exception:
        return None
