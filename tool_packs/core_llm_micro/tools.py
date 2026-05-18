from __future__ import annotations

from typing import Any

from runtime.order_tools import order_extract_ref_from_text
from runtime.tool_result_contract import build_tool_evidence


def llm_extract_order_ref(text: str) -> dict[str, Any]:
    raw = order_extract_ref_from_text(text)
    ok = bool(raw.get("ok"))
    return {
        "ok": ok,
        "type": "order_ref_result",
        "data": {
            "order_ref": str(raw.get("order_ref", "")),
            "order_id": str(raw.get("order_id", raw.get("order_ref", ""))),
            "confidence": str(raw.get("confidence", "none")),
            "source": "toolpack",
        },
        "evidence": build_tool_evidence(
            tool="q/extract_order_ref",
            mode="dry_run",
            source="migrated_toolpack",
            operation="read",
            input_refs=["text"],
            output_ref="order_ref_result",
            extra={
                "order_ref_found": bool(raw.get("order_ref", "")),
                "confidence": str(raw.get("confidence", "none")),
            },
        ),
        "error": "" if ok else str(raw.get("error", "ORDER_ID_NOT_FOUND")),
    }
