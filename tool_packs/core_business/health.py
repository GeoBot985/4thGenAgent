from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.business_context import get_business_order_context


def check_health(*, live: bool = False) -> dict[str, Any]:
    toolpack_path = Path(__file__).resolve().with_name("toolpack.json")
    context = get_business_order_context("ORD-10042", runtime_root="runtime_data")
    ok = bool(context.get("order")) and bool(context.get("customer"))
    return {
        "ok": ok,
        "toolpack_id": "core_business",
        "status": "ready" if ok else "failing",
        "severity": "info" if ok else "error",
        "message": "Core business context is available." if ok else "Core business context is missing demo fixtures.",
        "tool_count": 1,
        "live_checked": bool(live),
        "health_supported": True,
        "details": {
            "toolpack_path": str(toolpack_path),
            "live": bool(live),
            "order_found": bool(context.get("order")),
            "customer_found": bool(context.get("customer")),
            "shipment_found": bool(context.get("shipment")),
        },
        "errors": [] if ok else ["Demo business context not available."],
        "warnings": [],
    }
