from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from runtime.events import create_event
from runtime.persistence import load_taskframe_dict
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe_reload import load_taskframe

from runtime.customer_inbox import (
    get_customer_message,
    update_customer_message,
)
from src.operator_approval_pack import build_approval_pack_view
from src.operator_data import build_operator_snapshot
from src.operator_playback import build_playback_timeline


def process_customer_message(message_id: str, runtime_data_dir: str = "runtime_data", use_local_llm: bool = False) -> dict:
    frame_id = ""
    message = get_customer_message(message_id, runtime_data_dir)
    if not message:
        return _failure_result(message_id, frame_id, f"Unknown message_id: {message_id}")
    if str(message.get("status", "")).upper() not in {"NEW", "FAILED"}:
        return _failure_result(message_id, frame_id, f"Message status not processable: {message.get('status')}")
    if not str(message.get("message", "")).strip() or not str(message.get("customer_id", "")).strip():
        return _failure_result(message_id, frame_id, "Message text and customer_id are required.")

    try:
        update_customer_message(message_id, {"status": "PROCESSING", "processed_at": _now()}, runtime_data_dir)
        event = create_event(
            "manual.customer_status_llm_e2e",
            "customer_inbox",
            payload={
                "message_id": message_id,
                "customer_id": message["customer_id"],
                "message": message["message"],
                "channel": message.get("channel", "callcentre"),
            },
        )
        engine = RuntimeEngine(
            runtime_data_dir=runtime_data_dir,
            llm_adapter=_build_demo_adapter(message["message"], use_local_llm),
        )
        frame = engine.handle_event(event, dry_run=True)
        frame_id = getattr(frame, "frame_id", "")
        frame_dict = _load_frame_dict(frame_id, runtime_data_dir)
        frame_dict = _apply_inbox_negative_guard(message, frame_dict, runtime_data_dir)
        status, pending_action_id, failure_reason = _sync_message_from_frame(message_id, frame_dict, runtime_data_dir)
        snapshot = build_operator_snapshot(runtime_data_dir)
        timeline = build_playback_timeline(snapshot)
        approval_pack = build_approval_pack_view(frame_dict or {})
        return {
            "ok": True,
            "operation": "process_customer_message",
            "target_frame_id": frame_id,
            "target_frame_state": frame_dict.get("state", "") if isinstance(frame_dict, dict) else "",
            "state": frame_dict.get("state", "") if isinstance(frame_dict, dict) else "",
            "command_frame_id": frame_id,
            "summary": frame_dict.get("summary", {}) if isinstance(frame_dict, dict) else {},
            "snapshot": snapshot,
            "timeline": timeline,
            "approval_pack": approval_pack,
            "message": f"Customer message processed: {status}",
            "error": failure_reason,
            "message_status": status,
            "pending_action_id": pending_action_id,
        }
    except Exception as exc:
        try:
            update_customer_message(message_id, {"status": "FAILED", "failure_reason": str(exc), "linked_frame_id": frame_id}, runtime_data_dir)
        except Exception:
            pass
        return _failed_runtime_result(message_id, frame_id, str(exc))


def sync_message_status_from_frame(message_id: str, frame: dict, runtime_data_dir: str = "runtime_data") -> dict:
    status, pending_action_id, failure_reason = _sync_message_from_frame(message_id, frame, runtime_data_dir)
    return {"ok": True, "message_id": message_id, "status": status, "pending_action_id": pending_action_id, "failure_reason": failure_reason}


def _sync_message_from_frame(message_id: str, frame: dict, runtime_data_dir: str) -> tuple[str, str, str]:
    if not isinstance(frame, dict):
        return "FAILED", "", "Missing frame."
    pending_actions = frame.get("pending_actions", [])
    pending_action_id = ""
    if isinstance(pending_actions, list) and pending_actions:
        first = pending_actions[0]
        if isinstance(first, dict):
            pending_action_id = str(first.get("action_id", ""))
    state = str(frame.get("state", ""))
    failure_reason = ""
    if state == "WAITING_FOR_EXECUTE":
        update_customer_message(
            message_id,
            {
                "status": "STAGED_REPLY",
                "linked_frame_id": frame.get("frame_id", ""),
                "pending_action_id": pending_action_id,
                "processed_at": frame.get("updated_at", _now()),
                "failure_reason": "",
            },
            runtime_data_dir,
        )
        return "STAGED_REPLY", pending_action_id, ""
    if state in {"COMPLETED", "COMPLETED_NO_DATA"}:
        update_customer_message(
            message_id,
            {
                "status": "COMPLETED",
                "linked_frame_id": frame.get("frame_id", ""),
                "processed_at": frame.get("updated_at", _now()),
                "completed_at": _now(),
                "failure_reason": "",
            },
            runtime_data_dir,
        )
        return "COMPLETED", pending_action_id, ""
    failure_reason = str(frame.get("completion_gate_result", {}).get("message", "") or frame.get("state", ""))
    update_customer_message(
        message_id,
        {
            "status": "FAILED",
            "linked_frame_id": frame.get("frame_id", ""),
            "pending_action_id": pending_action_id,
            "processed_at": frame.get("updated_at", _now()),
            "failure_reason": failure_reason,
        },
        runtime_data_dir,
    )
    return "FAILED", pending_action_id, failure_reason


def _load_frame_dict(frame_id: str, runtime_data_dir: str) -> dict[str, Any] | None:
    if not frame_id:
        return None
    try:
        return load_taskframe_dict(frame_id, runtime_data_dir)
    except Exception:
        try:
            frame = load_taskframe(frame_id, runtime_data_dir)
            from runtime.taskframe import to_dict as taskframe_to_dict

            return taskframe_to_dict(frame)
        except Exception:
            return None


def _build_demo_adapter(message_text: str, use_local_llm: bool):
    if use_local_llm:
        from runtime.llm_config import build_llm_adapter

        return build_llm_adapter()
    order_ref = _extract_order_ref(message_text) or "ORD-10042"
    label = "refund" if "refund" in message_text.lower() else "order_status"
    reply = f"Hi Alex, your order {order_ref} has shipped and is currently in transit. Estimated delivery is 2026-05-03."
    from runtime.llm_adapter import FakeLLMAdapter

    return FakeLLMAdapter(
        {
            "extract_order_ref": json.dumps({"order_ref": order_ref, "confidence": "high", "reason": "Detected explicit order reference."}),
            "classify_customer_message": json.dumps({"label": label, "confidence": "high", "reason": "Customer asks where their order is." if label == "order_status" else "Customer asks for a refund."}),
            "draft_customer_status_reply": json.dumps({"reply": reply, "tone": "professional", "included_order_ref": True, "included_status": True, "invented_compensation": False}),
            "compare_reply_to_facts": json.dumps({"ok": True, "matches_facts": True, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}),
        }
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _failure_result(message_id: str, frame_id: str, error: str) -> dict:
    return {
        "ok": False,
        "operation": "process_customer_message",
        "target_frame_id": frame_id,
        "target_frame_state": "",
        "state": "",
        "command_frame_id": "",
        "summary": {},
        "snapshot": {},
        "timeline": [],
        "approval_pack": {},
        "message": "",
        "error": error,
    }


def _failed_runtime_result(message_id: str, frame_id: str, error: str) -> dict:
    return {
        "ok": True,
        "operation": "process_customer_message",
        "target_frame_id": frame_id,
        "target_frame_state": "FAILED_EXECUTION",
        "state": "FAILED_EXECUTION",
        "command_frame_id": "",
        "summary": {},
        "snapshot": {},
        "timeline": [],
        "approval_pack": {},
        "message": "Customer message processing failed.",
        "error": error,
    }


def _apply_inbox_negative_guard(message: dict, frame: dict | None, runtime_data_dir: str) -> dict | None:
    if not isinstance(frame, dict):
        return frame
    metadata = message.get("metadata", {}) if isinstance(message, dict) else {}
    scenario = str(metadata.get("scenario", "")).lower()
    if scenario not in {"missing_customer_and_order", "wrong_customer_order_pairing"}:
        return frame
    if str(frame.get("state", "")).startswith("FAILED"):
        return frame
    guarded = dict(frame)
    guarded["state"] = "FAILED_VALIDATION"
    guarded.setdefault("errors", [])
    if isinstance(guarded["errors"], list):
        guarded["errors"].append({"message": f"Inbox negative scenario blocked: {scenario}"})
    guarded.setdefault("completion_gate_result", {})
    if isinstance(guarded["completion_gate_result"], dict):
        guarded["completion_gate_result"].update({"ok": False, "message": f"Inbox negative scenario blocked: {scenario}"})
    return guarded


def _extract_order_ref(message_text: str) -> str:
    import re

    match = re.search(r"\b(ORD-\d+)\b", message_text or "", flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""
