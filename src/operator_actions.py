from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.events import intake_and_run_event
from runtime.persistence import load_taskframe_dict


def load_demo_event(demo_event_path: str = "demo/customer_message_event.json", make_unique_event_id: bool = True) -> dict[str, Any]:
    path = Path(demo_event_path)
    event_data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(event_data, dict):
        raise ValueError("Demo event payload must be a JSON object.")

    event = dict(event_data)
    if make_unique_event_id:
        event["event_id"] = f"evt-ui-demo-{uuid4().hex[:8]}"
    return event


def run_demo_customer_message(
    demo_event_path: str = "demo/customer_message_event.json",
    make_unique_event_id: bool = True,
) -> dict:
    try:
        event_data = load_demo_event(demo_event_path, make_unique_event_id=make_unique_event_id)
        result = intake_and_run_event(event_data)
    except Exception as exc:
        result = {
            "ok": False,
            "status": "FAILED",
            "event_id": None,
            "route_id": None,
            "manifest_id": None,
            "frame_id": None,
            "outputs": {},
            "errors": [str(exc)],
        }

    normalized = _normalize_result(result, event_data.get("event_id"))
    if normalized.get("frame_id") and not normalized.get("pending_actions"):
        frame = _load_frame_dict(str(normalized["frame_id"]))
        if isinstance(frame, dict):
            normalized["pending_actions"] = list(frame.get("pending_actions", [])) if isinstance(frame.get("pending_actions", []), list) else []
            if not normalized.get("outputs"):
                normalized["outputs"] = dict(frame.get("outputs", {})) if isinstance(frame.get("outputs", {}), dict) else {}
    return normalized


def _load_frame_dict(frame_id: str) -> dict[str, Any] | None:
    try:
        return load_taskframe_dict(frame_id)
    except Exception:
        return None


def _normalize_result(result: Any, fallback_event_id: Any) -> dict:
    payload = dict(result) if isinstance(result, dict) else {}
    payload.setdefault("ok", False)
    payload.setdefault("status", "FAILED")
    payload.setdefault("event_id", fallback_event_id if isinstance(fallback_event_id, str) else None)
    payload.setdefault("route_id", None)
    payload.setdefault("manifest_id", None)
    payload.setdefault("frame_id", None)
    payload.setdefault("outputs", {})
    payload.setdefault("pending_actions", [])
    payload.setdefault("errors", [])

    payload["ok"] = bool(payload.get("ok"))
    payload["status"] = str(payload.get("status", "FAILED"))
    payload["event_id"] = payload.get("event_id") if isinstance(payload.get("event_id"), str) and payload.get("event_id") else None
    payload["route_id"] = payload.get("route_id") if isinstance(payload.get("route_id"), str) and payload.get("route_id") else None
    payload["manifest_id"] = payload.get("manifest_id") if isinstance(payload.get("manifest_id"), str) and payload.get("manifest_id") else None
    payload["frame_id"] = payload.get("frame_id") if isinstance(payload.get("frame_id"), str) and payload.get("frame_id") else None
    payload["outputs"] = dict(payload.get("outputs", {})) if isinstance(payload.get("outputs", {}), dict) else {}
    payload["pending_actions"] = list(payload.get("pending_actions", [])) if isinstance(payload.get("pending_actions", []), list) else []
    payload["errors"] = [str(item) for item in payload.get("errors", [])] if isinstance(payload.get("errors", []), list) else []
    return payload
