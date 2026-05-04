from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BUSINESS_ROOT = Path("runtime_data") / "business"
REPO_BUSINESS_ROOT = Path(__file__).resolve().parents[1] / "runtime_data" / "business"


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, dict)]
    return []


def load_business_dataset(runtime_root: str | Path = "runtime_data") -> dict[str, list[dict[str, Any]]]:
    root = Path(runtime_root) / "business"
    if not root.is_dir():
        root = REPO_BUSINESS_ROOT
    return {
        "customers": _load_json(root / "customers.json"),
        "customer_messages": _load_json(root / "customer_messages.json"),
        "orders": _load_json(root / "orders.json"),
        "order_items": _load_json(root / "order_items.json"),
        "payments": _load_json(root / "payments.json"),
        "shipments": _load_json(root / "shipments.json"),
        "inventory": _load_json(root / "inventory.json"),
        "suppliers": _load_json(root / "suppliers.json"),
        "purchase_orders": _load_json(root / "purchase_orders.json"),
        "supplier_invoices": _load_json(root / "supplier_invoices.json"),
    }


def search_orders(
    customer_id: str | None = None,
    order_id: str | None = None,
    order_ref: str | None = None,
    status: str | None = None,
    runtime_root: str | Path = "runtime_data",
) -> list[dict[str, Any]]:
    orders = load_business_dataset(runtime_root)["orders"]
    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for order in orders:
        if customer_id and str(order.get("customer_id", "")).upper() != customer_id.strip().upper():
            continue
        candidate_order_ref = str(order.get("order_ref", "")).upper()
        candidate_order_id = str(order.get("order_id", "")).upper()
        lookup_value = (order_ref or order_id or "").strip().upper()
        if order_ref:
            if candidate_order_ref != lookup_value:
                continue
        elif order_id and candidate_order_id != lookup_value:
            if candidate_order_ref != lookup_value:
                continue
        if status and str(order.get("status", "")).upper() != status.strip().upper():
            continue
        canonical_key = candidate_order_ref or candidate_order_id or json.dumps(order, sort_keys=True)
        if canonical_key in seen_keys:
            continue
        seen_keys.add(canonical_key)
        results.append(dict(order))
    return results


def get_order(order_id: str, runtime_root: str | Path = "runtime_data") -> dict[str, Any] | None:
    results = search_orders(order_ref=order_id, runtime_root=runtime_root)
    if not results:
        results = search_orders(order_id=order_id, runtime_root=runtime_root)
    if not results:
        return None
    order = dict(results[0])
    order.setdefault("order_id", order.get("order_ref", ""))
    return order


def get_customer(customer_id: str, runtime_root: str | Path = "runtime_data") -> dict[str, Any] | None:
    customers = load_business_dataset(runtime_root)["customers"]
    for customer in customers:
        if str(customer.get("customer_id", "")).upper() == customer_id.strip().upper():
            return dict(customer)
    return None


def get_shipment(
    order_id: str,
    runtime_root: str | Path = "runtime_data",
    prefer_order_ref: bool = False,
) -> dict[str, Any] | None:
    shipments = load_business_dataset(runtime_root)["shipments"]
    lookup_value = order_id.strip().upper()
    if prefer_order_ref:
        for shipment in shipments:
            if str(shipment.get("order_ref", "")).upper() == lookup_value:
                return dict(shipment)
    for shipment in shipments:
        candidate_order_ref = str(shipment.get("order_ref", "")).upper()
        candidate_order_id = str(shipment.get("order_id", "")).upper()
        if candidate_order_ref == lookup_value or candidate_order_id == lookup_value:
            return dict(shipment)
    return None


def get_payment(order_id: str, runtime_root: str | Path = "runtime_data") -> dict[str, Any] | None:
    payments = load_business_dataset(runtime_root)["payments"]
    for payment in payments:
        if str(payment.get("order_ref", payment.get("order_id", ""))).upper() == order_id.strip().upper():
            return dict(payment)
    return None


def search_inventory(
    sku: str | None = None,
    below_reorder: bool = False,
    runtime_root: str | Path = "runtime_data",
) -> list[dict[str, Any]]:
    items = load_business_dataset(runtime_root)["inventory"]
    results: list[dict[str, Any]] = []
    for item in items:
        if sku and str(item.get("sku", "")).upper() != sku.strip().upper():
            continue
        if below_reorder and int(item.get("available_stock", 0) or 0) > int(item.get("reorder_threshold", 0) or 0):
            continue
        results.append(dict(item))
    return results


def get_order_items(order_ref: str, runtime_root: str | Path = "runtime_data") -> list[dict[str, Any]]:
    order_items = load_business_dataset(runtime_root)["order_items"]
    return [dict(item) for item in order_items if str(item.get("order_ref", "")).upper() == order_ref.strip().upper()]


def get_supplier(supplier_id: str, runtime_root: str | Path = "runtime_data") -> dict[str, Any] | None:
    suppliers = load_business_dataset(runtime_root)["suppliers"]
    for supplier in suppliers:
        if str(supplier.get("supplier_id", "")).upper() == supplier_id.strip().upper():
            return dict(supplier)
    return None


def search_suppliers_active(runtime_root: str | Path = "runtime_data") -> list[dict[str, Any]]:
    suppliers = load_business_dataset(runtime_root)["suppliers"]
    return [dict(supplier) for supplier in suppliers if str(supplier.get("status", "")).lower() == "active"]


def search_purchase_orders_open_by_sku(sku: str, runtime_root: str | Path = "runtime_data") -> list[dict[str, Any]]:
    purchase_orders = load_business_dataset(runtime_root)["purchase_orders"]
    return [
        dict(po)
        for po in purchase_orders
        if str(po.get("sku", "")).upper() == sku.strip().upper() and str(po.get("status", "")).lower() in {"open", "draft"}
    ]


def get_supplier_invoice(invoice_id: str, runtime_root: str | Path = "runtime_data") -> dict[str, Any] | None:
    invoices = load_business_dataset(runtime_root)["supplier_invoices"]
    for invoice in invoices:
        if str(invoice.get("invoice_id", "")).upper() == invoice_id.strip().upper():
            return dict(invoice)
    return None
