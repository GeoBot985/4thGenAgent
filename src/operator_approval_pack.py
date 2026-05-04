from __future__ import annotations

from typing import Any


RISK_BY_TOOL = {
    "wa/send": "external_communication",
    "g/send": "external_communication",
    "gb/book": "external_booking",
    "gb/cancel": "external_booking_change",
    "db/write": "data_mutation",
    "db/update": "data_mutation",
    "db/delete": "destructive_data_mutation",
}


def build_approval_pack_view(frame: dict) -> dict:
    if not isinstance(frame, dict):
        return _failure_view("Invalid TaskFrame payload.")

    pending_actions = frame.get("pending_actions", [])
    if not isinstance(pending_actions, list) or not pending_actions:
        return {
            "ok": True,
            "frame_id": _string(frame.get("frame_id")),
            "manifest_id": _string(frame.get("manifest_id")),
            "state": _string(frame.get("state")),
            "pending_action_count": 0,
            "approval_packs": [],
            "error": "",
            "message": "No pending approval actions for this TaskFrame.",
        }

    packs = [build_pending_action_pack(frame, action) for action in pending_actions if isinstance(action, dict)]
    return {
        "ok": True,
        "frame_id": _string(frame.get("frame_id")),
        "manifest_id": _string(frame.get("manifest_id")),
        "state": _string(frame.get("state")),
        "pending_action_count": len(packs),
        "approval_packs": packs,
        "error": "",
        "message": "",
    }


def build_pending_action_pack(frame: dict, action: dict) -> dict:
    action = action if isinstance(action, dict) else {}
    args = _collect_args(frame, action)
    tool = _tool_name(action)
    side_effect = bool(action.get("side_effect", True))
    pack = {
        "action_id": _string(action.get("action_id")),
        "status": _string(action.get("status")),
        "step_id": _string(action.get("step_id") or action.get("output_alias")),
        "tool": tool,
        "namespace": _string(action.get("namespace")),
        "action": _string(action.get("action") or action.get("tool_action")),
        "output_alias": _string(action.get("output_alias")),
        "side_effect": side_effect,
        "requires_approval": bool(action.get("requires_approval", side_effect)),
        "risk_class": classify_action_risk(action),
        "args": args,
        "human_summary": build_human_execute_summary(action),
        "validations": collect_action_validations(frame, action),
        "evidence": collect_action_evidence(frame, action),
        "related_outputs": collect_related_outputs(frame, action),
        "errors": collect_action_errors(frame, action),
        "guardrails": [
            "Requires explicit approval before execution.",
            "UI live execution is disabled in this spec.",
            "Dry-run mode only.",
        ],
        "related_to_selected_step": False,
    }
    return pack


def build_human_execute_summary(action: dict) -> str:
    action = action if isinstance(action, dict) else {}
    tool = _tool_name(action)
    args = _collect_args({}, action)
    if tool == "wa/send":
        chat = _string(args.get("chat") or args.get("customer") or args.get("recipient"))
        message = _string(args.get("message"))
        return f'This action would send a WhatsApp message to "{chat}" with message "{message}".'
    if tool == "g/send":
        to = _string(args.get("to") or args.get("recipient"))
        subject = _string(args.get("subject"))
        return f'This action would send an email to "{to}" with subject "{subject}".'
    if tool == "gb/book":
        court = _string(args.get("court"))
        date = _string(args.get("date"))
        time_value = _string(args.get("time_value") or args.get("time"))
        return f'This action would book "{court}" on "{date}" at "{time_value}".'
    if tool == "gb/cancel":
        court = _string(args.get("court"))
        date = _string(args.get("date"))
        time_value = _string(args.get("time_value") or args.get("time"))
        return f'This action would cancel booking "{court}" on "{date}" at "{time_value}".'
    return f'This action would execute tool "{tool}" with the listed arguments.'


def classify_action_risk(action: dict) -> str:
    action = action if isinstance(action, dict) else {}
    tool = _tool_name(action)
    if tool in RISK_BY_TOOL:
        return RISK_BY_TOOL[tool]
    if bool(action.get("side_effect", True)):
        return "side_effect_unknown"
    return "read_only_or_unknown"


def collect_action_validations(frame: dict, action: dict) -> list[dict]:
    return _collect_step_related(frame, action, "validations")


def collect_action_evidence(frame: dict, action: dict) -> list[dict]:
    return _collect_step_related(frame, action, "evidence")


def collect_related_outputs(frame: dict, action: dict) -> dict:
    if not isinstance(frame, dict):
        return {}
    outputs = frame.get("outputs", {})
    if not isinstance(outputs, dict):
        return {}
    keys = []
    for key in ("output_alias", "result_alias", "output"):
        value = action.get(key) if isinstance(action, dict) else None
        if isinstance(value, str) and value:
            keys.append(value)
    if not keys and _tool_name(action) == "wa/send":
        keys = ["draft_reply"]
    return {key: outputs[key] for key in keys if key in outputs}


def collect_action_errors(frame: dict, action: dict) -> list[dict]:
    return _collect_step_related(frame, action, "errors")


def _collect_step_related(frame: dict, action: dict, key: str) -> list[dict]:
    if not isinstance(frame, dict):
        return []
    step_id = _string(action.get("step_id") if isinstance(action, dict) else "")
    collected: list[dict] = []
    for item in _list_value(frame.get(key)):
        if not isinstance(item, dict):
            continue
        if step_id and _string(item.get("step_id") or item.get("validation_id") or item.get("id")) != step_id:
            continue
        collected.append(dict(item))
    return collected


def _collect_args(frame: dict, action: dict) -> dict:
    args = action.get("args") if isinstance(action, dict) else {}
    if isinstance(args, dict) and args:
        return dict(args)
    synthesized: dict[str, Any] = {}
    if isinstance(frame, dict):
        outputs = frame.get("outputs", {})
        if isinstance(outputs, dict):
            customer = outputs.get("customer", {})
            draft_reply = outputs.get("draft_reply", {})
            order = outputs.get("order", {})
            if isinstance(customer, dict):
                synthesized["chat"] = customer.get("name") or customer.get("customer_id") or action.get("customer_id", "")
                synthesized["customer_id"] = customer.get("customer_id") or action.get("customer_id", "")
            if isinstance(draft_reply, dict):
                synthesized["message"] = draft_reply.get("body", "")
            if isinstance(order, dict):
                synthesized["order_id"] = order.get("order_id", "")
    if synthesized:
        return synthesized
    if isinstance(action, dict):
        for key in ("arguments", "params", "parameters"):
            value = action.get(key)
            if isinstance(value, dict) and value:
                return dict(value)
    return {}


def _tool_name(action: dict) -> str:
    tool = action.get("tool") if isinstance(action, dict) else ""
    if isinstance(tool, str) and tool:
        return tool
    action_type = _string(action.get("action_type") if isinstance(action, dict) else "")
    if action_type == "send_customer_message":
        return "wa/send"
    if action_type == "send_email":
        return "g/send"
    if action_type == "book_court":
        return "gb/book"
    if action_type == "cancel_booking":
        return "gb/cancel"
    namespace = _string(action.get("namespace") if isinstance(action, dict) else "")
    action_name = _string(action.get("action") if isinstance(action, dict) else "")
    if namespace and action_name:
        return f"{namespace}/{action_name}"
    return action_name or namespace or "unknown"


def _failure_view(message: str) -> dict:
    return {
        "ok": False,
        "frame_id": "",
        "manifest_id": "",
        "state": "",
        "pending_action_count": 0,
        "approval_packs": [],
        "error": message,
    }


def _list_value(value: Any) -> list:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
