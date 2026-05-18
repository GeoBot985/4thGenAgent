from __future__ import annotations

from typing import Any

from runtime.business_context import get_business_order_context
from runtime.tool_result_contract import build_tool_evidence


def business_get_order_context(order_id: str, runtime_root: str = "runtime_data") -> dict[str, Any]:
    context = get_business_order_context(order_id, runtime_root=runtime_root)
    ok = bool(context.get("order"))
    return {
        "ok": ok,
        "type": "business_order_context",
        "data": context,
        "evidence": build_tool_evidence(
            tool="business/get_order_context",
            mode="dry_run",
            source="migrated_toolpack",
            operation="read",
            input_refs=[f"order_id:{order_id}"],
            output_ref="business_order_context",
            extra={
                "order_id": order_id,
                "runtime_root": runtime_root,
                "order_found": ok,
            },
        ),
        "error": "" if ok else "ORDER_NOT_FOUND",
    }
