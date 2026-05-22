from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from src.backend.schemas import EventIntakeRequest

router = APIRouter()


def make_event_id(source: str, event_type: str, idempotency_key: str | None) -> str:
    if idempotency_key:
        key_str = f"{source}:{event_type}:{idempotency_key}"
        h = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]
        return f"evt_{h}"
    return f"evt_{uuid4().hex}"


def _event_error(event: dict[str, Any]) -> str:
    errors = event.get("errors") or []
    if isinstance(errors, list) and errors:
        return str(errors[0])
    error = event.get("error")
    return str(error) if isinstance(error, str) else ""


def _enrich_event_record(event: dict[str, Any], runtime_data_dir: str) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}

    enriched = dict(event)
    try:
        from runtime.event_store import get_indexed_event

        indexed = get_indexed_event(str(enriched.get("event_id", "")), runtime_data_dir=runtime_data_dir)
        if isinstance(indexed, dict):
            for key in ("route_id", "manifest_id", "linked_frame_id", "status"):
                if not enriched.get(key) and indexed.get(key) is not None:
                    enriched[key] = indexed.get(key)
    except Exception:
        pass
    return enriched


def _load_linked_frame(linked_frame_id: str, runtime_data_dir: str) -> dict[str, Any]:
    if not linked_frame_id:
        return {}

    try:
        from runtime.persistence import load_taskframe_dict, taskframe_exists

        if not taskframe_exists(linked_frame_id, runtime_data_dir):
            return {}
        frame = load_taskframe_dict(linked_frame_id, runtime_data_dir)
    except Exception:
        return {}

    if not isinstance(frame, dict):
        return {}

    return {
        "frame_id": linked_frame_id,
        "manifest_id": frame.get("manifest_id", ""),
        "state": frame.get("state", ""),
        "summary": frame.get("summary", {}),
        "pending_action_count": len(frame.get("pending_actions") or []),
        "executed_action_count": len(frame.get("executed_actions") or []),
        "error_count": len(frame.get("errors") or []),
    }


@router.post("")
async def create_event(body: EventIntakeRequest, request: Request) -> dict[str, Any]:
    """Intake an event into the TaskFrame runtime."""
    source = body.source.strip()
    event_type = body.event_type.strip()
    if not source:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "source is required."})
    if not event_type:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "event_type is required."})
    if not body.dry_run:
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "error": "live execution (dry_run=false) is rejected for now."},
        )

    event_id = make_event_id(source, event_type, body.idempotency_key)
    event_data = {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": body.payload,
        "metadata": {},
    }
    if body.idempotency_key:
        event_data["metadata"]["idempotency_key"] = body.idempotency_key

    rd = request.app.state.runtime_data_dir

    try:
        from runtime.event_store import intake_and_run_event

        result = intake_and_run_event(
            event_data,
            runtime_data_dir=rd,
            strict_source_contracts=True,
            strict_manifest_preflight=True,
        )

        status = result.get("status")
        is_duplicate = status == "DUPLICATE_EVENT"
        frame_id = result.get("frame_id")

        if is_duplicate:
            return {
                "ok": True,
                "duplicate": True,
                "event_id": result.get("event_id"),
                "linked_frame_id": frame_id,
                "error": "",
            }

        if not result.get("ok"):
            errors = result.get("errors") or []
            error_msg = errors[0] if errors else "Event intake failed."
            return {
                "ok": False,
                "event_id": result.get("event_id"),
                "route_id": result.get("route_id"),
                "manifest_id": result.get("manifest_id"),
                "linked_frame_id": result.get("frame_id"),
                "error": error_msg,
            }

        summary = {}
        pending_count = 0
        executed_count = 0
        frame_state = "WAITING_FOR_EXECUTE"

        linked_frame = _load_linked_frame(str(frame_id or ""), rd)
        if linked_frame:
            summary = linked_frame.get("summary", {})
            frame_state = linked_frame.get("state", "WAITING_FOR_EXECUTE")
            pending_count = int(linked_frame.get("pending_action_count", 0) or 0)
            executed_count = int(linked_frame.get("executed_action_count", 0) or 0)

        return {
            "ok": True,
            "event_id": result.get("event_id"),
            "source": source,
            "event_type": event_type,
            "route_id": result.get("route_id"),
            "manifest_id": result.get("manifest_id"),
            "linked_frame_id": frame_id,
            "frame_state": frame_state,
            "summary": summary,
            "pending_action_count": pending_count,
            "executed_action_count": executed_count,
            "error": "",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": str(exc)},
        )


@router.get("")
async def list_events(
    request: Request,
    limit: int = 50,
    source: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List recent events."""
    rd = request.app.state.runtime_data_dir
    try:
        from runtime.event_store import list_events as _list_events

        events = [_enrich_event_record(ev, rd) for ev in _list_events(limit=10_000, runtime_data_dir=rd)]

        filtered = []
        for e in events:
            if source and e.get("source") != source:
                continue
            if event_type and e.get("event_type") != event_type:
                continue
            if status and e.get("status") != status:
                continue
            filtered.append(e)

        filtered.reverse()
        result_events = filtered[:max(1, limit)]

        out_events = []
        for ev in result_events:
            out_events.append(
                {
                    "event_id": ev.get("event_id"),
                    "source": ev.get("source"),
                    "event_type": ev.get("event_type"),
                    "received_at": ev.get("received_at"),
                    "status": ev.get("status"),
                    "route_id": ev.get("route_id"),
                    "manifest_id": ev.get("manifest_id"),
                    "linked_frame_id": ev.get("linked_frame_id"),
                    "error": _event_error(ev),
                }
            )

        return {"ok": True, "events": out_events, "count": len(out_events), "error": ""}
    except Exception as exc:
        return {"ok": False, "events": [], "count": 0, "error": str(exc)}


@router.get("/{event_id}")
async def get_event(event_id: str, request: Request) -> dict[str, Any]:
    """Get a single event and its linked frame metadata."""
    from src.production_backend import _validate_id

    _validate_id(event_id, "event_id")

    rd = request.app.state.runtime_data_dir
    try:
        from runtime.event_store import get_event as _get_event

        event = _enrich_event_record(_get_event(event_id, runtime_data_dir=rd) or {}, rd)
        if not event:
            return {"ok": False, "error": f"Event not found: {event_id}"}

        linked_frame = _load_linked_frame(str(event.get("linked_frame_id") or ""), rd)

        return {
            "ok": True,
            "event": event,
            "linked_frame": linked_frame,
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
