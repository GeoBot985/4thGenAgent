from __future__ import annotations

from typing import Any

from .business_store import get_customer, get_order, get_payment, get_shipment


def extract_order_ref_from_text(message: str) -> dict[str, Any]:
    import re

    if not isinstance(message, str) or not message.strip():
        return {"ok": False, "error": "ORDER_ID_NOT_FOUND", "message": "No order reference found in message."}
    match = re.search(r"\b(ORD-\d+)\b", message, flags=re.IGNORECASE)
    if not match:
        return {"ok": False, "error": "ORDER_ID_NOT_FOUND", "message": "No order reference found in message."}
    return {"ok": True, "order_ref": match.group(1).upper(), "confidence": "deterministic", "error": "", "evidence": [{"kind": "text_extract", "field": "order_ref"}]}


def customer_order_context_lookup(customer_id: str, order_ref: str) -> dict[str, Any]:
    customer = get_customer(customer_id)
    order = get_order(order_ref)
    shipment = get_shipment(order_ref)
    payment = get_payment(order_ref)
    facts: list[str] = []
    if customer:
        facts.append(f"Customer {customer.get('customer_id', '')} is {customer.get('name', '')}.")
    if order:
        facts.append(f"Order {order.get('order_ref', '')} belongs to {order.get('customer_id', '')}.")
        facts.append(f"Order {order.get('order_ref', '')} status is {order.get('status', '')}.")
    if shipment:
        facts.append(f"Shipment {shipment.get('shipment_id', '') or shipment.get('order_ref', '')} status is {shipment.get('status', '')}.")
        if shipment.get("estimated_delivery"):
            facts.append(f"Estimated delivery is {shipment.get('estimated_delivery')}.")
    evidence = [
        {"dataset": "customers", "query": {"customer_id": customer_id}, "found": customer is not None},
        {"dataset": "orders", "query": {"order_ref": order_ref}, "found": order is not None},
        {"dataset": "shipments", "query": {"order_ref": order_ref}, "found": shipment is not None},
        {"dataset": "payments", "query": {"order_ref": order_ref}, "found": payment is not None},
    ]
    if not order:
        return {"ok": False, "error": "ORDER_NOT_FOUND", "message": f"Order not found: {order_ref}", "customer": customer, "order": None, "shipment": shipment, "payment": payment, "facts": facts, "evidence": evidence}
    return {"ok": True, "error": "", "message": "", "customer": customer, "order": order, "shipment": shipment, "payment": payment, "facts": facts, "evidence": evidence}


def validate_customer_owns_order(customer_id: str, order: dict) -> dict[str, Any]:
    order_customer = order.get("customer_id") if isinstance(order, dict) else ""
    ok = bool(customer_id) and bool(order_customer) and customer_id == order_customer
    return {"ok": ok, "customer_id": customer_id, "order_customer_id": order_customer, "error": "" if ok else "CUSTOMER_ORDER_MISMATCH", "message": "" if ok else f"Order {order.get('order_ref', '')} belongs to {order_customer}, not {customer_id}."}


def build_customer_status_context(customer: dict, order: dict, shipment: dict) -> dict[str, Any]:
    facts = []
    if customer:
        facts.append(f"Customer {customer.get('customer_id', '')} is {customer.get('name', '')}.")
    if order:
        facts.append(f"Order {order.get('order_ref', '')} belongs to {order.get('customer_id', '')}.")
        facts.append(f"Order {order.get('order_ref', '')} status is {order.get('status', '')}.")
    if shipment:
        facts.append(f"Shipment {shipment.get('shipment_id', '') or shipment.get('order_ref', '')} status is {shipment.get('status', '')}.")
        if shipment.get("estimated_delivery"):
            facts.append(f"Estimated delivery is {shipment.get('estimated_delivery')}.")
    return {"ok": True, "customer": customer or {}, "order": order or {}, "shipment": shipment or {}, "facts": facts, "error": ""}


def validate_customer_status_reply(reply: dict, order: dict, shipment: dict, reply_check: dict | None = None) -> dict[str, Any]:
    body = str((reply or {}).get("reply") or (reply or {}).get("body") or "")
    order_ref = str(order.get("order_ref", "")) if isinstance(order, dict) else ""
    status = str(order.get("status", "")) if isinstance(order, dict) else ""
    shipment_status = str(shipment.get("status", "")) if isinstance(shipment, dict) else ""
    reply_ok = True
    unsupported_claims: list[Any] = []
    if isinstance(reply_check, dict):
        reply_ok = bool(reply_check.get("ok", True)) and bool(reply_check.get("matches_facts", True))
        unsupported_claims = list(reply_check.get("unsupported_claims") or [])
    unsupported = any(token in body.lower() for token in ("refund", "compensation", "voucher", "credit", "free"))
    ok = bool(body) and reply_ok and not unsupported and not unsupported_claims and (not order_ref or order_ref in body) and (not status or status in body.lower() or shipment_status in body.lower())
    return {
        "ok": ok,
        "error": "" if ok else "STATUS_REPLY_INVALID",
        "message": "" if ok else "Reply failed status validation.",
        "reply": reply or {},
        "order": order or {},
        "shipment": shipment or {},
        "reply_check": reply_check or {},
    }


def prepare_customer_message_action(customer_id: str, channel: str, reply: dict) -> dict[str, Any]:
    body = str((reply or {}).get("reply") or (reply or {}).get("body") or "")
    if not body:
        return {"ok": False, "error": "INVALID_REPLY", "message": "Reply body is required.", "customer_id": customer_id, "channel": channel}
    return {"ok": True, "error": "", "message": "", "action_type": "send_customer_message", "customer_id": customer_id, "channel": channel, "body": body, "evidence": [{"kind": "pending_action", "channel": channel, "customer_id": customer_id}]}
