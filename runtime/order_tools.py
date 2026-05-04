from __future__ import annotations

import re
from typing import Any

from .business_store import get_order, get_order_items, search_orders, get_shipment, get_payment, get_customer


def order_read(order_ref: str, runtime_root: str = "runtime_data") -> dict:
    order = get_order(order_ref, runtime_root=runtime_root)
    if not order:
        return {"ok": False, "order": {}, "error": "ORDER_NOT_FOUND"}
    return {"ok": True, "order": order, "error": ""}


def order_search(customer_id: str = "", order_ref: str = "", status: str = "", runtime_root: str = "runtime_data") -> dict:
    orders = search_orders(customer_id=customer_id or None, order_ref=order_ref or None, status=status or None, runtime_root=runtime_root)
    return {"ok": True, "orders": orders, "count": len(orders), "error": ""}


def order_items_list(order_ref: str, runtime_root: str = "runtime_data") -> dict:
    items = get_order_items(order_ref, runtime_root=runtime_root)
    return {"ok": True, "order_items": items, "count": len(items), "error": ""}


def order_extract_ref_from_text(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "order_ref": "", "order_id": "", "confidence": "none", "error": "ORDER_ID_NOT_FOUND"}
    lowered = text.lower()
    match = re.search(r"\b(ORD-\d+)\b", text, flags=re.IGNORECASE)
    if match:
        order_ref = match.group(1).upper()
        return {"ok": True, "order_ref": order_ref, "order_id": order_ref, "confidence": "deterministic", "error": ""}
    match = re.search(r"(?:order\s*(?:number|ref|#)?\s*|#)(\d{3,})\b", lowered, flags=re.IGNORECASE)
    if match:
        order_ref = f"ORD-{match.group(1)}"
        return {"ok": True, "order_ref": order_ref, "order_id": order_ref, "confidence": "deterministic", "error": ""}
    if re.search(r"\b\d{4,}\b", text) and any(token in lowered for token in ("order", "ref", "number", "#")):
        digits = re.search(r"\b(\d{4,})\b", text)
        if digits:
            order_ref = f"ORD-{digits.group(1)}"
            return {"ok": True, "order_ref": order_ref, "order_id": order_ref, "confidence": "deterministic", "error": ""}
    return {"ok": False, "order_ref": "", "order_id": "", "confidence": "none", "error": "ORDER_ID_NOT_FOUND"}


def order_context_build(customer: dict, order: dict, shipment: dict, payment: dict | None = None, **_ignored: Any) -> dict:
    facts = []
    if customer:
        facts.append(f"Customer {customer.get('customer_id', '')} is {customer.get('name', '')}.")
    if order:
        facts.append(f"Order {order.get('order_ref', '')} belongs to {order.get('customer_id', '')}.")
        facts.append(f"Order {order.get('order_ref', '')} status is {order.get('status', '')}.")
    if shipment:
        facts.append(f"Shipment {shipment.get('shipment_id', '') or shipment.get('order_ref', '')} status is {shipment.get('status', '')}.")
    if payment:
        facts.append(f"Payment {payment.get('payment_id', '')} status is {payment.get('status', '')}.")
    return {"ok": True, "customer": customer or {}, "order": order or {}, "shipment": shipment or {}, "payment": payment or {}, "facts": facts, "error": ""}
