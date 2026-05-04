from __future__ import annotations

import re
from typing import Any

from .business_store import get_customer, get_order, get_payment, get_shipment, search_inventory, search_orders


def get_mock_order(order_id: str) -> dict[str, Any] | None:
    return get_order(order_id, runtime_root="runtime_data")


def get_mock_order_context(order_id: str, runtime_root: str = "runtime_data") -> dict[str, Any]:
    order = get_order(order_id, runtime_root=runtime_root)
    if not order:
        return {
            "order": None,
            "customer": None,
            "shipment": None,
            "payment": None,
            "inventory": [],
            "searches": [],
        }
    customer = get_customer(str(order.get("customer_id", "")), runtime_root=runtime_root)
    shipment = get_shipment(order_id, runtime_root=runtime_root, prefer_order_ref=bool(order.get("order_ref")))
    payment = get_payment(order_id, runtime_root=runtime_root)
    inventory = search_inventory(runtime_root=runtime_root)
    return {
        "order": order,
        "customer": customer,
        "shipment": shipment,
        "payment": payment,
        "inventory": inventory,
        "searches": [
            {"dataset": "orders", "query": {"order_id": order_id}, "found": order is not None},
            {"dataset": "customers", "query": {"customer_id": order.get("customer_id", "")}, "found": customer is not None},
            {"dataset": "shipments", "query": {"order_id": order_id}, "found": shipment is not None},
            {"dataset": "payments", "query": {"order_id": order_id}, "found": payment is not None},
        ],
    }


def extract_order_id(message: str) -> str | None:
    if not isinstance(message, str) or not message.strip():
        return None
    match = re.search(r"\b(ORD-\d+)\b", message, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()
