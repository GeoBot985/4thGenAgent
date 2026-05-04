from __future__ import annotations

import json
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .errors import (
    LLMAdapterResponseError,
    LLMConnectionError,
    LLMHTTPError,
    LLMOutputParseError,
    LLMProviderError,
    LLMTimeoutError,
)


class BaseLLMAdapter:
    provider = "base"
    model = ""

    def generate(self, prompt: str, system: str = "", metadata: dict[str, Any] | None = None) -> str:
        raise NotImplementedError


class FakeLLMAdapter(BaseLLMAdapter):
    provider = "fake"
    model = "fake"

    def __init__(self, responses: dict[str, str] | None = None, default_response: str = "fake response"):
        self.responses = dict(responses or {})
        self.default_response = default_response

    def generate(self, prompt: str, system: str = "", metadata: dict[str, Any] | None = None) -> str:
        metadata = dict(metadata or {})
        action = metadata.get("action")
        if action in self.responses:
            response = self.responses[action]
            if action == "draft_supplier_reorder_message":
                args = metadata.get("args", {}) if isinstance(metadata.get("args", {}), dict) else {}
                draft_po = args.get("draft_po", {}) if isinstance(args, dict) else {}
                supplier = args.get("supplier", {}) if isinstance(args, dict) else {}
                po_id = str(draft_po.get("po_id", "PO-DRAFT-TEST"))
                supplier_name = str(supplier.get("name", "Supplier"))
                sku_lines = draft_po.get("lines", []) if isinstance(draft_po, dict) else []
                skus = ", ".join(str(line.get("sku", "")) for line in sku_lines if isinstance(line, dict))
                return response.replace("{po_id}", po_id).replace("{supplier_name}", supplier_name).replace("{skus}", skus)
            return response
        if prompt in self.responses:
            return self.responses[prompt]
        if action == "extract_order_ref":
            order_ref = _extract_order_ref_from_text(prompt)
            if not order_ref:
                return json.dumps({"order_ref": "", "confidence": "none", "reason": "No order reference found."})
            return json.dumps({"order_ref": order_ref, "confidence": "high", "reason": "Detected explicit order reference."})
        if action == "classify_customer_message":
            label = _classify_message_text(_extract_message_from_prompt(prompt))
            reason = {
                "refund": "Customer asks for a refund.",
                "complaint": "Customer expresses a complaint.",
                "stock_query": "Customer asks about stock.",
                "supplier_query": "Customer asks about a supplier.",
                "order_status": "Customer asks where their order is.",
                "other": "Customer intent is not recognized.",
            }.get(label, "Deterministic fake response.")
            return json.dumps({"label": label, "confidence": "high", "reason": reason})
        if action == "draft_customer_status_reply":
            return json.dumps({"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.", "tone": "professional", "included_order_ref": True, "included_status": True, "invented_compensation": False})
        if action == "draft_supplier_reorder_message":
            draft_po = metadata.get("args", {}).get("draft_po", {}) if isinstance(metadata.get("args", {}), dict) else {}
            supplier = metadata.get("args", {}).get("supplier", {}) if isinstance(metadata.get("args", {}), dict) else {}
            po_id = str(draft_po.get("po_id", "PO-DRAFT-TEST"))
            supplier_name = str(supplier.get("name", "Supplier"))
            sku_lines = draft_po.get("lines", []) if isinstance(draft_po, dict) else []
            skus = ", ".join(str(line.get("sku", "")) for line in sku_lines if isinstance(line, dict))
            return json.dumps({"subject": f"Purchase Order {po_id}", "body": f"Good day {supplier_name}, please find draft purchase order {po_id} for {skus}. Please confirm availability and lead time.", "tone": "professional", "included_po_id": True, "included_supplier_name": True, "included_sku_lines": True, "invented_terms": False})
        if action == "draft_reconciliation_exception_summary":
            return json.dumps({"summary": "Payments were reconciled against orders, invoices, and ledger entries. Exceptions require operator review before posting.", "risk_level": "high", "key_exceptions": ["One payment has an amount mismatch.", "One payment reference appears more than once.", "One payment appears to already be posted."], "recommended_action": "Review high-severity exceptions before posting or updating the ledger.", "invented_facts": False})
        if action == "compare_reply_to_facts":
            return json.dumps({"ok": True, "matches_facts": True, "unsupported_claims": [], "missing_required_facts": [], "reason": "Deterministic fake response."})
        if action == "summarize_customer_message":
            return json.dumps({"summary": "Customer asks for order status."})
        if action == "summarize_business_context":
            return json.dumps({"summary": "Customer asks about order status.", "risk_flags": [], "open_questions": []})
        return self.default_response


class OllamaLLMAdapter(BaseLLMAdapter):
    provider = "ollama"

    def __init__(
        self,
        model: str = "granite3.3:8b",
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 60,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str, system: str = "", metadata: dict[str, Any] | None = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0},
        }
        request = urllib_request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            raise LLMHTTPError(f"Ollama returned HTTP {exc.code}") from exc
        except urllib_error.URLError as exc:
            raise LLMConnectionError(f"Unable to contact Ollama provider: {exc}") from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout_seconds}s") from exc

        if status != 200:
            raise LLMHTTPError(f"Ollama returned HTTP {status}")

        try:
            response_payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMAdapterResponseError("Ollama provider returned malformed JSON.") from exc

        if not isinstance(response_payload, dict):
            raise LLMAdapterResponseError("Ollama provider returned an invalid response.")

        if response_payload.get("error"):
            raise LLMProviderError(str(response_payload["error"]))

        response_text = response_payload.get("response")
        if not isinstance(response_text, str):
            raise LLMAdapterResponseError("Ollama provider response is missing text.")
        return response_text


def check_llm_available(provider: str = "ollama", model: str = "granite3.3:8b") -> dict[str, Any]:
    if provider != "ollama":
        return {"ok": False, "provider": provider, "model": model, "error": f"Unsupported provider: {provider}"}
    adapter = OllamaLLMAdapter(model=model)
    payload = {
        "model": adapter.model,
        "prompt": "ping",
        "stream": False,
        "options": {"temperature": 0},
    }
    request = urllib_request.Request(
        f"{adapter.base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=5) as response:
            status = getattr(response, "status", 200)
            body = response.read().decode("utf-8")
    except Exception as exc:
        return {"ok": False, "provider": provider, "model": model, "error": str(exc) or "Ollama model unavailable."}
    if status != 200:
        return {"ok": False, "provider": provider, "model": model, "error": f"Ollama returned HTTP {status}"}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "provider": provider, "model": model, "error": "Ollama returned malformed JSON."}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("response"), str):
        return {"ok": False, "provider": provider, "model": model, "error": "Ollama model unavailable."}
    return {"ok": True, "provider": provider, "model": model, "error": ""}


def extract_json_from_text(text: str) -> dict[str, Any] | list[Any]:
    text = text.strip()
    if not text:
        raise LLMOutputParseError("LLM output is empty.")

    parsed = _try_json_loads(text)
    if parsed is not None:
        return parsed

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            block = _extract_balanced_block(text, start, opener, closer)
            if block is not None:
                parsed = _try_json_loads(block)
                if parsed is not None:
                    return parsed
            start = text.find(opener, start + 1)

    raise LLMOutputParseError("Unable to parse JSON from LLM output.")


def _try_json_loads(text: str) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def _extract_balanced_block(text: str, start: int, opener: str, closer: str) -> str | None:
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue

        if char == "\\":
            if in_string:
                escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _extract_order_ref_from_text(text: str) -> str:
    import re

    match = re.search(r"\b(ORD-\d+)\b", text or "", flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _classify_message_text(text: str) -> str:
    lowered = (text or "").lower()
    if "refund" in lowered:
        return "refund"
    if "complaint" in lowered or "bad" in lowered:
        return "complaint"
    if "stock" in lowered or "available" in lowered:
        return "stock_query"
    if "supplier" in lowered:
        return "supplier_query"
    if "order" in lowered or "where is" in lowered:
        return "order_status"
    return "other"


def _extract_message_from_prompt(prompt: str) -> str:
    marker = "Message:\n"
    if marker in prompt:
        return prompt.split(marker, 1)[1].strip()
    marker = "Message:"
    if marker in prompt:
        return prompt.split(marker, 1)[1].strip()
    return prompt
