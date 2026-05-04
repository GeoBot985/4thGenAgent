from __future__ import annotations

from .business_store import get_shipment


def shipment_read(order_ref: str, runtime_root: str = "runtime_data") -> dict:
    shipment = get_shipment(order_ref, runtime_root=runtime_root, prefer_order_ref=True)
    if not shipment:
        return {"ok": False, "shipment": {}, "error": "SHIPMENT_NOT_FOUND"}
    return {"ok": True, "shipment": shipment, "error": ""}
