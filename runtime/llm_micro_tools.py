from __future__ import annotations

from typing import Any

from .llm_tools import (
    LLM_TOOLS,
    get_llm_tool,
    render_llm_prompt,
)


MICRO_TOOL_ACTIONS = set(LLM_TOOLS)


def is_llm_micro_tool(action: str) -> bool:
    return action in MICRO_TOOL_ACTIONS


def build_micro_tool_prompt(action: str, args: dict[str, object]) -> tuple[str, str]:
    return render_llm_prompt(action, _rename_legacy_args(action, args))


def normalize_micro_tool_output(action: str, raw_text: str, args: dict[str, object]) -> object:
    from .llm_tools import _parse_json_object  # type: ignore[attr-defined]

    if action == "summarize_customer_message":
        return raw_text.strip()
    try:
        parsed = _parse_json_object(raw_text)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    if action == "extract_order_ref":
        return {
            "order_ref": str(parsed.get("order_ref", "")),
            "confidence": str(parsed.get("confidence", "")),
            "reason": str(parsed.get("reason", "")),
        }
    if action == "classify_customer_message":
        return {
            "label": str(parsed.get("label", "")),
            "confidence": str(parsed.get("confidence", "")),
            "reason": str(parsed.get("reason", "")),
        }
    if action == "draft_customer_status_reply":
        return {
            "reply": str(parsed.get("reply", "")),
            "tone": str(parsed.get("tone", "professional")),
            "included_order_ref": bool(parsed.get("included_order_ref", False)),
            "included_status": bool(parsed.get("included_status", False)),
            "invented_compensation": bool(parsed.get("invented_compensation", False)),
        }
    if action == "draft_reconciliation_exception_summary":
        return {
            "summary": str(parsed.get("summary", "")),
            "risk_level": str(parsed.get("risk_level", "medium")),
            "key_exceptions": list(parsed.get("key_exceptions", [])) if isinstance(parsed.get("key_exceptions", []), list) else [],
            "recommended_action": str(parsed.get("recommended_action", "")),
            "invented_facts": bool(parsed.get("invented_facts", False)),
        }
    if action == "compare_reply_to_facts":
        return {
            "ok": parsed.get("ok", False),
            "matches_facts": parsed.get("matches_facts", False),
            "unsupported_claims": list(parsed.get("unsupported_claims", [])) if isinstance(parsed.get("unsupported_claims", []), list) else [],
            "missing_required_facts": list(parsed.get("missing_required_facts", [])) if isinstance(parsed.get("missing_required_facts", []), list) else [],
            "reason": str(parsed.get("reason", "")),
        }
    return parsed


def validate_micro_tool_output(action: str, output: object, args: dict[str, object]) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []
    tool_spec = get_llm_tool(action)
    schema = tool_spec.get("output_schema", {})
    allowed = tool_spec.get("allowed_values", {}) or {}
    legacy_classify_labels = {"order_status", "refund", "complaint", "stock_query", "supplier_query", "other"}
    if not isinstance(output, dict):
        return [_validation(f"{action}_schema", False, "Output must be a JSON object.", {})]
    for field, field_type in schema.items():
        ok = field in output and _matches_type(output.get(field), field_type)
        validations.append(_validation(f"{action}_{field}", ok, "" if ok else f"Missing or invalid field: {field}", {field: output.get(field)}))
    for key, allowed_values in allowed.items():
        if key in output:
            ok = output.get(key) in allowed_values
            validations.append(_validation(f"{action}_{key}_allowed", ok, "" if ok else f"{key} must be allowed.", {key: output.get(key)}))
    if action == "extract_order_ref":
        order_ref = str(output.get("order_ref", "")).strip()
        ok = bool(order_ref) and order_ref.startswith("ORD-")
        validations.append(_validation(f"{action}_format", ok, "" if ok else "order_ref must match ORD-[0-9]+.", {"order_ref": order_ref}))
    if action == "classify_customer_message":
        label = str(output.get("label", "")).strip()
        ok = label in legacy_classify_labels
        validations.append(_validation(f"{action}_label_legacy_allowed", ok, "" if ok else "label must be allowed.", {"label": label}))
    if action == "compare_reply_to_facts":
        ok = output.get("ok") is True and output.get("matches_facts") is True and not output.get("unsupported_claims")
        validations.append(_validation(f"{action}_fact_check", ok, "" if ok else "Reply does not match facts.", dict(output)))
    if action == "draft_customer_status_reply":
        invented_compensation = bool(output.get("invented_compensation", False))
        validations.append(_validation(f"{action}_compensation", not invented_compensation, "" if not invented_compensation else "invented_compensation must be false.", {"invented_compensation": invented_compensation}))
        reply = str(output.get("reply", "")).lower()
        forbidden = any(token in reply for token in ("refund", "compensation", "voucher", "credit", "discount", "free"))
        validations.append(_validation(f"{action}_forbidden_claims", not forbidden, "" if not forbidden else "reply contains forbidden compensation claims.", {"reply": output.get("reply", "")}))
    if action == "draft_reconciliation_exception_summary":
        invented_facts = bool(output.get("invented_facts", False))
        validations.append(_validation(f"{action}_invented_facts", not invented_facts, "" if not invented_facts else "invented_facts must be false.", {"invented_facts": invented_facts}))
        risk_level = str(output.get("risk_level", ""))
        validations.append(_validation(f"{action}_risk_level", risk_level in {"low", "medium", "high", "critical"}, "" if risk_level in {"low", "medium", "high", "critical"} else "risk_level must be allowed.", {"risk_level": risk_level}))
    return validations


def _validation(validation_id: str, ok: bool, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"validation_id": validation_id, "type": "llm_micro_tool_schema", "ok": ok, "message": message, "data": dict(data or {})}


def _matches_type(value: Any, field_type: str) -> bool:
    if field_type == "str":
        return isinstance(value, str)
    if field_type == "bool":
        return isinstance(value, bool)
    if field_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "list":
        return isinstance(value, list)
    if field_type == "dict":
        return isinstance(value, dict)
    return False


def _rename_legacy_args(action: str, args: dict[str, object]) -> dict[str, object]:
    if action == "extract_order_ref" and "text" in args and "message" not in args:
        updated = dict(args)
        updated["message"] = updated.pop("text")
        return updated
    if action == "summarize_customer_message" and "text" in args and "message" not in args:
        updated = dict(args)
        updated["message"] = updated.pop("text")
        return updated
    if action == "draft_customer_status_reply":
        updated = dict(args)
        if "facts" in updated and not isinstance(updated["facts"], str):
            updated["facts"] = updated["facts"]
        return updated
    return dict(args)
