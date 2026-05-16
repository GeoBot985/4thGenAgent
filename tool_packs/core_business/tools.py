from __future__ import annotations

from typing import Any

from runtime.business_context import get_business_order_context


def business_get_order_context(order_id: str, runtime_root: str = "runtime_data") -> dict[str, Any]:
    context = get_business_order_context(order_id, runtime_root=runtime_root)
    ok = bool(context.get("order"))
    return {
        "ok": ok,
        "type": "business_order_context",
        "data": context,
        "evidence": [{"kind": "business_context", "order_id": order_id}],
        "error": "" if ok else "ORDER_NOT_FOUND",
    }
