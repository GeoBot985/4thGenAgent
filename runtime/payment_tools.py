from __future__ import annotations

from .business_store import get_payment


def payment_read_by_order(order_ref: str, runtime_root: str = "runtime_data") -> dict:
    payment = get_payment(order_ref, runtime_root=runtime_root)
    if not payment:
        return {"ok": True, "payment": {}, "error": ""}
    return {"ok": True, "payment": payment, "error": ""}
