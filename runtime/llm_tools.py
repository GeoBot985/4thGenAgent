from __future__ import annotations

import copy
import json
import re
from typing import Any

from .errors import LLMOutputParseError


class LLMToolInputError(Exception):
    pass


class LLMToolNotFoundError(Exception):
    pass


class LLMOutputSchemaError(Exception):
    pass


LLM_TOOLS: dict[str, dict[str, Any]] = {
    "extract_order_ref": {
        "action": "extract_order_ref",
        "description": "Extract an order reference from a customer message.",
        "required_inputs": ["message"],
        "output_schema": {"order_ref": "str", "confidence": "str", "reason": "str"},
        "allowed_values": {"confidence": ["low", "medium", "high"]},
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nDo not choose tools. Do not invent facts.\nMessage:\n{message}",
    },
    "classify_customer_message": {
        "action": "classify_customer_message",
        "description": "Classify customer message intent into a fixed label set.",
        "required_inputs": ["message"],
        "output_schema": {"label": "str", "confidence": "str", "reason": "str"},
        "allowed_values": {
            "label": ["order_status", "refund", "complaint", "product_question", "account_query", "unknown"],
            "confidence": ["low", "medium", "high"],
        },
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nDo not choose tools. Do not invent facts.\nAllowed labels: order_status, refund, complaint, product_question, account_query, unknown\nMessage:\n{message}",
    },
    "draft_customer_status_reply": {
        "action": "draft_customer_status_reply",
        "description": "Draft a customer-facing order-status reply from supplied facts only.",
        "required_inputs": ["facts", "customer", "order", "shipment"],
        "output_schema": {
            "reply": "str",
            "tone": "str",
            "included_order_ref": "bool",
            "included_status": "bool",
            "invented_compensation": "bool",
        },
        "allowed_values": {"tone": ["professional", "neutral", "friendly"]},
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input. Use only the provided facts. Do not offer refunds, compensation, vouchers, credits, discounts, or free items unless explicitly present in the facts.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nUse only the provided facts.\nDo not offer refunds, compensation, vouchers, credits, discounts, or free items unless explicitly present in the facts.\nFacts:\n{facts}\nCustomer:\n{customer}\nOrder:\n{order}\nShipment:\n{shipment}",
    },
    "compare_reply_to_facts": {
        "action": "compare_reply_to_facts",
        "description": "Fact-check the drafted reply against the supplied factual context.",
        "required_inputs": ["reply", "facts"],
        "output_schema": {
            "ok": "bool",
            "matches_facts": "bool",
            "unsupported_claims": "list",
            "missing_required_facts": "list",
            "reason": "str",
        },
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nReply:\n{reply}\nFacts:\n{facts}",
    },
    "summarize_business_context": {
        "action": "summarize_business_context",
        "description": "Summarize structured business context for operator-facing trace/report panels.",
        "required_inputs": ["facts"],
        "output_schema": {"summary": "str", "risk_flags": "list", "open_questions": "list"},
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nSummarize the following facts for an operator.\nFacts:\n{facts}",
    },
    "draft_supplier_reorder_message": {
        "action": "draft_supplier_reorder_message",
        "description": "Draft supplier message wording from a draft purchase order only.",
        "required_inputs": ["supplier", "draft_po"],
        "output_schema": {"subject": "str", "body": "str", "tone": "str", "included_po_id": "bool", "included_supplier_name": "bool", "included_sku_lines": "bool", "invented_terms": "bool"},
        "allowed_values": {"tone": ["professional", "neutral", "friendly"]},
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input. Do not invent discounts, payment terms, delivery promises, or pricing.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nUse only the supplied supplier and draft purchase order.\nSupplier:\n{supplier}\nDraft PO:\n{draft_po}",
    },
    "draft_reconciliation_exception_summary": {
        "action": "draft_reconciliation_exception_summary",
        "description": "Draft reconciliation exception summary from reconciliation result only.",
        "required_inputs": ["reconciliation_result"],
        "output_schema": {
            "summary": "str",
            "risk_level": "str",
            "key_exceptions": "list",
            "recommended_action": "str",
            "invented_facts": "bool",
        },
        "allowed_values": {"risk_level": ["low", "medium", "high", "critical"]},
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input. Summarize only the provided reconciliation result. Do not change counts or invent payment, invoice, ledger, or posting facts.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nUse only the supplied reconciliation result.\nDo not change counts or invent facts.\nReconciliation result:\n{reconciliation_result}",
    },
    "draft_supplier_invoice_exception_summary": {
        "action": "draft_supplier_invoice_exception_summary",
        "description": "Draft a bounded supplier invoice exception summary from the deterministic match result only.",
        "required_inputs": ["invoice", "purchase_order", "receipts", "match_result"],
        "output_schema": {
            "summary": "str",
            "risk_level": "str",
            "key_exceptions": "list",
            "recommended_action": "str",
            "invented_facts": "bool",
        },
        "allowed_values": {"risk_level": ["low", "medium", "high", "critical"]},
        "system": "You are a bounded extraction/drafting function inside a controlled automation runtime. Return only the requested output format. Do not choose tools. Do not perform actions. Do not approve anything. Do not invent facts. Use only the provided input. Summarize only the provided match result. Do not invent exception facts, totals, receipts, invoices, or ledger data.",
        "prompt": "Return JSON only. No markdown. No explanation outside JSON.\nUse only the supplied invoice, purchase order, receipts, and match result.\nDo not invent exception facts.\nInvoice:\n{invoice}\nPurchase order:\n{purchase_order}\nReceipts:\n{receipts}\nMatch result:\n{match_result}",
    },
}


def get_llm_tool(action: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(LLM_TOOLS[action])
    except KeyError as exc:
        raise LLMToolNotFoundError(f"LLM tool not found: {action}") from exc


def render_llm_prompt(action: str, inputs: dict[str, object]) -> tuple[str, str]:
    tool_spec = get_llm_tool(action)
    provided = _apply_input_aliases(action, dict(inputs or {}))
    missing = [key for key in tool_spec.get("required_inputs", []) if key not in provided or provided[key] is None]
    if missing:
        raise LLMToolInputError(f"LLM_INPUT_MISSING: {', '.join(missing)}")
    system = str(tool_spec.get("system", "")).strip()
    prompt_template = str(tool_spec.get("prompt", ""))
    rendered_inputs = {
        key: _stringify_for_prompt(provided.get(key))
        for key in tool_spec.get("required_inputs", [])
    }
    prompt = prompt_template.format(**rendered_inputs)
    return system, prompt


def validate_llm_output(action: str, raw_text: str) -> dict[str, Any]:
    try:
        tool_spec = get_llm_tool(action)
    except LLMToolNotFoundError as exc:
        return {
            "ok": False,
            "data": {},
            "error": str(exc),
            "error_type": "LLM_TOOL_NOT_FOUND",
            "raw_text": raw_text,
        }

    try:
        parsed = _parse_json_object(raw_text)
    except LLMOutputParseError as exc:
        return {
            "ok": False,
            "data": {},
            "error": str(exc),
            "error_type": "LLMOutputParseError",
            "raw_text": raw_text,
        }

    schema = tool_spec.get("output_schema", {})
    allowed = tool_spec.get("allowed_values", {}) or {}
    forbidden = tool_spec.get("forbidden_values", {}) or {}

    if not isinstance(parsed, dict):
        return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "LLM output must be a JSON object.", raw_text)

    normalized: dict[str, Any] = {}
    for field, field_type in schema.items():
        if field not in parsed:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", f"Missing required field: {field}", raw_text)
        value = parsed[field]
        if not _value_matches_type(value, field_type):
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", f"Field {field} must be of type {field_type}.", raw_text)
        normalized[field] = value

    for key, allowed_values in allowed.items():
        if key not in normalized:
            continue
        if normalized[key] not in allowed_values:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", f"Field {key} has unsupported value: {normalized[key]}", raw_text)

    for key, forbidden_values in forbidden.items():
        if key not in normalized:
            continue
        if normalized[key] in forbidden_values:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", f"Field {key} contains forbidden value: {normalized[key]}", raw_text)

    if action == "extract_order_ref":
        order_ref = str(normalized.get("order_ref", "")).strip()
        if order_ref and not re.fullmatch(r"ORD-[0-9]+", order_ref):
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "order_ref must match ORD-[0-9]+ when present.", raw_text)
        if not order_ref:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "order_ref missing.", raw_text)
    if action == "compare_reply_to_facts":
        if normalized.get("ok") is not True:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "ok must be true.", raw_text)
        if normalized.get("matches_facts") is not True:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "matches_facts must be true.", raw_text)
        if normalized.get("unsupported_claims"):
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "unsupported_claims must be empty.", raw_text)

    if action == "draft_customer_status_reply":
        if normalized.get("invented_compensation") is not False:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "invented_compensation must be false.", raw_text)
    if action == "draft_supplier_reorder_message":
        if normalized.get("invented_terms") is not False:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "invented_terms must be false.", raw_text)
    if action == "draft_supplier_invoice_exception_summary":
        if normalized.get("invented_facts") is not False:
            return _schema_failure("LLM_OUTPUT_SCHEMA_INVALID", "invented_facts must be false.", raw_text)

    return {"ok": True, "data": normalized, "error": "", "error_type": "", "raw_text": raw_text}


def _schema_failure(error_type: str, message: str, raw_text: str) -> dict[str, Any]:
    return {"ok": False, "data": {}, "error": message, "error_type": error_type, "raw_text": raw_text}


def _value_matches_type(value: Any, field_type: str) -> bool:
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


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise LLMOutputParseError("LLM output is empty.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMOutputParseError("LLM output is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise LLMOutputParseError("LLM output must be a JSON object.")
    return parsed


def _stringify_for_prompt(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _apply_input_aliases(action: str, inputs: dict[str, object]) -> dict[str, object]:
    data = dict(inputs)
    if action in {"extract_order_ref", "classify_customer_message", "summarize_business_context"}:
        if "message" not in data and "text" in data:
            data["message"] = data["text"]
    if action == "draft_customer_status_reply":
        if "facts" not in data and "context" in data:
            data["facts"] = data["context"]
    if action == "compare_reply_to_facts":
        if "reply" not in data and "draft_reply" in data:
            data["reply"] = data["draft_reply"]
    if action == "draft_supplier_reorder_message":
        return data
    return data
