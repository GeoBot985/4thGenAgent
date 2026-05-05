from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .persistence import ensure_dir, write_json_atomic


BUSINESS_FILES = [
    "customers",
    "customer_messages",
    "orders",
    "order_items",
    "shipments",
    "payments",
    "inventory",
    "suppliers",
    "purchase_orders",
    "supplier_invoices",
]

DATASET_MANIFEST_NAME = "dataset_manifest.json"


def get_business_dir(runtime_data_dir: str = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "business"


def business_file_path(name: str, runtime_data_dir: str = "runtime_data") -> Path:
    return get_business_dir(runtime_data_dir) / f"{name}.json"


def dataset_manifest_path(runtime_data_dir: str = "runtime_data") -> Path:
    return get_business_dir(runtime_data_dir) / DATASET_MANIFEST_NAME


def load_dataset_manifest(runtime_data_dir: str = "runtime_data") -> dict:
    path = dataset_manifest_path(runtime_data_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def load_business_records(name: str, runtime_data_dir: str = "runtime_data") -> list[dict]:
    path = business_file_path(name, runtime_data_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [dict(item) for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def save_business_records(name: str, records: list[dict], runtime_data_dir: str = "runtime_data") -> None:
    path = business_file_path(name, runtime_data_dir)
    ensure_dir(path.parent)
    write_json_atomic(path, [dict(item) for item in records])


def find_one(name: str, key: str, value: object, runtime_data_dir: str = "runtime_data") -> dict | None:
    for record in load_business_records(name, runtime_data_dir):
        if record.get(key) == value:
            return dict(record)
    return None


def find_many(name: str, key: str, value: object, runtime_data_dir: str = "runtime_data") -> list[dict]:
    return [dict(record) for record in load_business_records(name, runtime_data_dir) if record.get(key) == value]


def search_records(name: str, filters: dict, runtime_data_dir: str = "runtime_data") -> list[dict]:
    results: list[dict] = []
    for record in load_business_records(name, runtime_data_dir):
        if all(record.get(key) == value for key, value in dict(filters or {}).items()):
            results.append(dict(record))
    return results


def seed_business_dataset(runtime_data_dir: str = "runtime_data", overwrite: bool = False) -> dict:
    business_dir = get_business_dir(runtime_data_dir)
    ensure_dir(business_dir)
    files_written: list[str] = []
    datasets = _seed_payloads()
    for name, records in datasets.items():
        path = business_file_path(name, runtime_data_dir)
        if path.exists() and not overwrite:
            continue
        save_business_records(name, records, runtime_data_dir)
        files_written.append(path.name)
    dataset_manifest = {
        "dataset_version": 2,
        "name": "Demo Business Dataset v2",
        "seeded_at": "2026-05-01T00:00:00Z",
        "record_counts": {name: len(records) for name, records in datasets.items()},
    }
    if overwrite or not dataset_manifest_path(runtime_data_dir).exists():
        write_json_atomic(dataset_manifest_path(runtime_data_dir), dataset_manifest)
        files_written.append(DATASET_MANIFEST_NAME)
    return {
        "ok": True,
        "dataset_version": 2,
        "business_dir": str(business_dir),
        "files_written": files_written,
        "record_counts": dataset_manifest["record_counts"],
        "error": "",
    }


def reset_business_dataset(runtime_data_dir: str = "runtime_data") -> dict:
    return seed_business_dataset(runtime_data_dir, overwrite=True)


def validate_business_dataset(runtime_data_dir: str = "runtime_data") -> dict:
    customers = load_business_records("customers", runtime_data_dir)
    orders = load_business_records("orders", runtime_data_dir)
    order_items = load_business_records("order_items", runtime_data_dir)
    shipments = load_business_records("shipments", runtime_data_dir)
    payments = load_business_records("payments", runtime_data_dir)
    inventory = load_business_records("inventory", runtime_data_dir)
    suppliers = load_business_records("suppliers", runtime_data_dir)
    purchase_orders = load_business_records("purchase_orders", runtime_data_dir)
    invoices = load_business_records("supplier_invoices", runtime_data_dir)
    errors: list[str] = []
    warnings: list[str] = []
    customer_ids = {c.get("customer_id") for c in customers}
    supplier_ids = {s.get("supplier_id") for s in suppliers}
    sku_records = {i.get("sku"): i for i in inventory}
    if len(customer_ids) != len(customers):
        errors.append("Duplicate customer_id.")
    if len({o.get("order_ref") for o in orders}) != len(orders):
        errors.append("Duplicate order_ref.")
    for order in orders:
        if order.get("customer_id") not in customer_ids:
            errors.append(f"Order customer missing: {order.get('order_ref')}")
    totals = {}
    for item in order_items:
        totals.setdefault(item.get("order_ref"), 0.0)
        totals[item.get("order_ref")] += float(item.get("line_total", 0) or 0)
    for order in orders:
        if round(float(order.get("total_amount", 0) or 0), 2) != round(float(totals.get(order.get("order_ref"), 0) or 0), 2):
            errors.append(f"Order total mismatch: {order.get('order_ref')}")
    for item in order_items:
        if item.get("order_ref") not in {o.get("order_ref") for o in orders}:
            errors.append(f"Order item missing order: {item.get('order_ref')}")
    for shipment in shipments:
        if shipment.get("order_ref") and shipment.get("order_ref") not in {o.get("order_ref") for o in orders}:
            errors.append(f"Shipment missing order: {shipment.get('order_ref')}")
    for payment in payments:
        if payment.get("status") != "unmatched_order" and payment.get("order_ref") not in {o.get("order_ref") for o in orders}:
            errors.append(f"Payment missing order: {payment.get('payment_id')}")
    for item in inventory:
        if item.get("supplier_id") not in supplier_ids:
            errors.append(f"Inventory supplier missing: {item.get('sku')}")
        if int(item.get("available_stock", 0) or 0) != int(item.get("stock_on_hand", 0) or 0) - int(item.get("reserved_stock", 0) or 0):
            errors.append(f"Inventory available stock mismatch: {item.get('sku')}")
    for po in purchase_orders:
        if po.get("supplier_id") not in supplier_ids:
            errors.append(f"PO supplier missing: {po.get('po_id')}")
        if po.get("sku") not in sku_records:
            errors.append(f"PO sku missing: {po.get('po_id')}")
    for inv in invoices:
        if inv.get("supplier_id") not in supplier_ids:
            errors.append(f"Invoice supplier missing: {inv.get('invoice_id')}")
        if inv.get("po_id") and inv.get("po_id") not in {po.get("po_id") for po in purchase_orders}:
            errors.append(f"Invoice PO missing: {inv.get('invoice_id')}")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "record_counts": {name: len(load_business_records(name, runtime_data_dir)) for name in BUSINESS_FILES}}


def _seed_payloads() -> dict[str, list[dict[str, Any]]]:
    return {
        "customers": [
            {"customer_id": "CUST-1001", "name": "Alex", "preferred_channel": "whatsapp", "whatsapp_chat": "Alex Customer", "email": "alex@example.test", "status": "active"},
            {"customer_id": "CUST-1002", "name": "Bianca", "preferred_channel": "email", "whatsapp_chat": "Bianca Customer", "email": "bianca@example.test", "status": "active"},
            {"customer_id": "CUST-1003", "name": "Chris", "preferred_channel": "callcentre", "whatsapp_chat": "Chris Customer", "email": "chris@example.test", "status": "active"},
            {"customer_id": "CUST-1004", "name": "Dana", "preferred_channel": "whatsapp", "whatsapp_chat": "Dana Customer", "email": "dana@example.test", "status": "active"},
            {"customer_id": "CUST-1005", "name": "Evan", "preferred_channel": "email", "whatsapp_chat": "Evan Customer", "email": "evan@example.test", "status": "inactive"},
        ],
        "customer_messages": [
            {"message_id": "msg_001", "customer_id": "CUST-1001", "customer_name": "Alex", "channel": "callcentre", "received_at": "2026-05-01T08:00:00Z", "status": "NEW", "message": "Where is my order ORD-10042?", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "order_status_happy_path"}},
            {"message_id": "msg_002", "customer_id": "CUST-1002", "customer_name": "Bianca", "channel": "callcentre", "received_at": "2026-05-01T08:05:00Z", "status": "NEW", "message": "I want a refund for order ORD-10043.", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "refund_request"}},
            {"message_id": "msg_003", "customer_id": "CUST-1003", "customer_name": "Chris", "channel": "callcentre", "received_at": "2026-05-01T08:10:00Z", "status": "NEW", "message": "Do you have stock of SKU-CHAIR-01?", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "stock_query"}},
            {"message_id": "msg_004", "customer_id": "CUST-9999", "customer_name": "Unknown", "channel": "callcentre", "received_at": "2026-05-01T08:15:00Z", "status": "NEW", "message": "Where is my order ORD-99999?", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "missing_customer_and_order"}},
            {"message_id": "msg_005", "customer_id": "CUST-1001", "customer_name": "Alex", "channel": "callcentre", "received_at": "2026-05-01T08:20:00Z", "status": "NEW", "message": "Where is order ORD-10044?", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "wrong_customer_order_pairing"}},
            {"message_id": "msg_006", "customer_id": "CUST-1004", "customer_name": "Dana", "channel": "callcentre", "received_at": "2026-05-01T08:25:00Z", "status": "NEW", "message": "Is SKU-LAMP-01 still available?", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "stock_query"}},
            {"message_id": "msg_007", "customer_id": "CUST-1002", "customer_name": "Bianca", "channel": "email", "received_at": "2026-05-01T08:30:00Z", "status": "NEW", "message": "Please reconcile payment for ORD-10043.", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "payment_reconciliation"}},
            {"message_id": "msg_008", "customer_id": "CUST-1003", "customer_name": "Chris", "channel": "email", "received_at": "2026-05-01T08:35:00Z", "status": "NEW", "message": "Need supplier invoice match for PO-5001.", "linked_frame_id": "", "pending_action_id": "", "processed_at": "", "completed_at": "", "failure_reason": "", "metadata": {"scenario": "supplier_invoice"}},
        ],
        "orders": [
            {"order_ref": "ORD-10042", "customer_id": "CUST-1001", "status": "shipped", "created_date": "2026-04-25", "total_amount": 1299.99, "currency": "ZAR"},
            {"order_ref": "ORD-10043", "customer_id": "CUST-1002", "status": "delivered", "created_date": "2026-04-20", "total_amount": 499.50, "currency": "ZAR"},
            {"order_ref": "ORD-10044", "customer_id": "CUST-1004", "status": "processing", "created_date": "2026-04-29", "total_amount": 899.00, "currency": "ZAR"},
            {"order_ref": "ORD-10045", "customer_id": "CUST-1003", "status": "cancelled", "created_date": "2026-04-18", "total_amount": 299.00, "currency": "ZAR"},
            {"order_ref": "ORD-10046", "customer_id": "CUST-1001", "status": "delivered", "created_date": "2026-04-12", "total_amount": 150.00, "currency": "ZAR"},
            {"order_ref": "ORD-10047", "customer_id": "CUST-1002", "status": "shipped", "created_date": "2026-04-27", "total_amount": 250.00, "currency": "ZAR"},
            {"order_ref": "ORD-10048", "customer_id": "CUST-1004", "status": "processing", "created_date": "2026-04-30", "total_amount": 1200.00, "currency": "ZAR"},
            {"order_ref": "ORD-10049", "customer_id": "CUST-1001", "status": "delivered", "created_date": "2026-04-11", "total_amount": 199.00, "currency": "ZAR"},
        ],
        "order_items": [
            {"order_ref": "ORD-10042", "sku": "SKU-DESK-01", "description": "Compact office desk", "quantity": 1, "unit_price": 1299.99, "line_total": 1299.99},
            {"order_ref": "ORD-10042", "sku": "SKU-PAD-01", "description": "Desk pad", "quantity": 1, "unit_price": 0.00, "line_total": 0.00},
            {"order_ref": "ORD-10043", "sku": "SKU-LAMP-01", "description": "LED desk lamp", "quantity": 1, "unit_price": 499.50, "line_total": 499.50},
            {"order_ref": "ORD-10043", "sku": "SKU-CABLE-01", "description": "USB-C cable", "quantity": 1, "unit_price": 0.00, "line_total": 0.00},
            {"order_ref": "ORD-10044", "sku": "SKU-CHAIR-01", "description": "Ergonomic office chair", "quantity": 1, "unit_price": 899.00, "line_total": 899.00},
            {"order_ref": "ORD-10045", "sku": "SKU-CABLE-01", "description": "USB-C cable", "quantity": 2, "unit_price": 149.50, "line_total": 299.00},
            {"order_ref": "ORD-10046", "sku": "SKU-CHAIR-01", "description": "Ergonomic office chair", "quantity": 1, "unit_price": 150.00, "line_total": 150.00},
            {"order_ref": "ORD-10047", "sku": "SKU-LAMP-01", "description": "LED desk lamp", "quantity": 1, "unit_price": 250.00, "line_total": 250.00},
            {"order_ref": "ORD-10048", "sku": "SKU-DESK-01", "description": "Compact office desk", "quantity": 1, "unit_price": 1200.00, "line_total": 1200.00},
            {"order_ref": "ORD-10048", "sku": "SKU-STAND-01", "description": "Monitor stand", "quantity": 1, "unit_price": 0.00, "line_total": 0.00},
            {"order_ref": "ORD-10049", "sku": "SKU-MOUSE-01", "description": "Wireless mouse", "quantity": 1, "unit_price": 199.00, "line_total": 199.00},
            {"order_ref": "ORD-10049", "sku": "SKU-PAD-01", "description": "Desk pad", "quantity": 1, "unit_price": 0.00, "line_total": 0.00},
        ],
        "shipments": [
            {"order_ref": "ORD-10042", "shipment_id": "SHIP-9001", "status": "in_transit", "carrier": "DemoCourier", "tracking_ref": "TRK-778899", "estimated_delivery": "2026-05-03"},
            {"order_ref": "ORD-10043", "shipment_id": "SHIP-9002", "status": "delivered", "carrier": "DemoCourier", "tracking_ref": "TRK-778900", "estimated_delivery": "2026-04-24", "delivered_at": "2026-04-24T14:30:00Z"},
            {"order_ref": "ORD-10044", "shipment_id": "", "status": "not_shipped", "carrier": "", "tracking_ref": "", "estimated_delivery": ""},
            {"order_ref": "ORD-10045", "shipment_id": "SHIP-9003", "status": "cancelled", "carrier": "", "tracking_ref": "", "estimated_delivery": ""},
            {"order_ref": "ORD-10046", "shipment_id": "SHIP-9004", "status": "delivered", "carrier": "DemoCourier", "tracking_ref": "TRK-778901", "estimated_delivery": "2026-04-16", "delivered_at": "2026-04-16T12:00:00Z"},
        ],
        "payments": [
            {"payment_id": "PAY-7001", "order_ref": "ORD-10042", "customer_id": "CUST-1001", "amount": 1299.99, "currency": "ZAR", "status": "matched", "paid_at": "2026-04-25T10:00:00Z", "provider_ref": "BANK-001"},
            {"payment_id": "PAY-7002", "order_ref": "ORD-10043", "customer_id": "CUST-1002", "amount": 499.50, "currency": "ZAR", "status": "matched", "paid_at": "2026-04-20T09:00:00Z", "provider_ref": "BANK-002"},
            {"payment_id": "PAY-7003", "order_ref": "ORD-10044", "customer_id": "CUST-1004", "amount": 799.00, "currency": "ZAR", "status": "amount_mismatch", "paid_at": "2026-04-29T11:00:00Z", "provider_ref": "BANK-003"},
            {"payment_id": "PAY-7004", "order_ref": "ORD-99998", "customer_id": "CUST-1003", "amount": 300.00, "currency": "ZAR", "status": "unmatched_order", "paid_at": "2026-04-30T12:00:00Z", "provider_ref": "BANK-004"},
            {"payment_id": "PAY-7005", "order_ref": "ORD-10046", "customer_id": "CUST-1001", "amount": 150.00, "currency": "ZAR", "status": "matched", "paid_at": "2026-04-12T09:10:00Z", "provider_ref": "BANK-005"},
            {"payment_id": "PAY-7006", "order_ref": "ORD-10047", "customer_id": "CUST-1002", "amount": 250.00, "currency": "ZAR", "status": "matched", "paid_at": "2026-04-27T09:10:00Z", "provider_ref": "BANK-006"},
            {"payment_id": "PAY-7007", "order_ref": "ORD-10048", "customer_id": "CUST-1004", "amount": 1200.00, "currency": "ZAR", "status": "matched", "paid_at": "2026-04-30T10:10:00Z", "provider_ref": "BANK-007"},
            {"payment_id": "PAY-7008", "order_ref": "ORD-10049", "customer_id": "CUST-1001", "amount": 199.00, "currency": "ZAR", "status": "matched", "paid_at": "2026-04-11T09:10:00Z", "provider_ref": "BANK-008"},
        ],
        "inventory": [
            {"sku": "SKU-DESK-01", "name": "Compact office desk", "stock_on_hand": 12, "reserved_stock": 2, "available_stock": 10, "reorder_threshold": 5, "reorder_quantity": 10, "supplier_id": "SUP-001", "status": "active"},
            {"sku": "SKU-LAMP-01", "name": "LED desk lamp", "stock_on_hand": 3, "reserved_stock": 1, "available_stock": 2, "reorder_threshold": 5, "reorder_quantity": 20, "supplier_id": "SUP-002", "status": "active"},
            {"sku": "SKU-CHAIR-01", "name": "Ergonomic office chair", "stock_on_hand": 0, "reserved_stock": 0, "available_stock": 0, "reorder_threshold": 3, "reorder_quantity": 8, "supplier_id": "SUP-001", "status": "active"},
            {"sku": "SKU-CABLE-01", "name": "USB-C cable", "stock_on_hand": 50, "reserved_stock": 5, "available_stock": 45, "reorder_threshold": 10, "reorder_quantity": 50, "supplier_id": "SUP-003", "status": "active"},
            {"sku": "SKU-MOUSE-01", "name": "Wireless mouse", "stock_on_hand": 8, "reserved_stock": 1, "available_stock": 7, "reorder_threshold": 4, "reorder_quantity": 20, "supplier_id": "SUP-003", "status": "active"},
            {"sku": "SKU-PRINTER-01", "name": "Compact printer", "stock_on_hand": 2, "reserved_stock": 0, "available_stock": 2, "reorder_threshold": 3, "reorder_quantity": 5, "supplier_id": "SUP-002", "status": "active"},
            {"sku": "SKU-PAD-01", "name": "Desk pad", "stock_on_hand": 20, "reserved_stock": 3, "available_stock": 17, "reorder_threshold": 10, "reorder_quantity": 25, "supplier_id": "SUP-003", "status": "active"},
            {"sku": "SKU-STAND-01", "name": "Monitor stand", "stock_on_hand": 6, "reserved_stock": 2, "available_stock": 4, "reorder_threshold": 4, "reorder_quantity": 10, "supplier_id": "SUP-001", "status": "active"},
        ],
        "suppliers": [
            {"supplier_id": "SUP-001", "name": "Demo Furniture Supply", "status": "active", "email": "orders@furniture-supplier.example.test", "lead_time_days": 5, "preferred_channel": "email"},
            {"supplier_id": "SUP-002", "name": "Demo Lighting Supply", "status": "active", "email": "orders@lighting-supplier.example.test", "lead_time_days": 3, "preferred_channel": "email"},
            {"supplier_id": "SUP-003", "name": "Demo Accessories Supply", "status": "active", "email": "orders@accessories-supplier.example.test", "lead_time_days": 2, "preferred_channel": "email"},
            {"supplier_id": "SUP-004", "name": "Inactive Supplier", "status": "inactive", "email": "inactive@example.test", "lead_time_days": 10, "preferred_channel": "email"},
        ],
        "purchase_orders": [
            {"po_id": "PO-5001", "supplier_id": "SUP-002", "status": "open", "created_at": "2026-04-30T10:00:00Z", "sku": "SKU-LAMP-01", "quantity": 20, "unit_cost": 250.00, "total_amount": 5000.00, "currency": "ZAR", "lines": [{"sku": "SKU-LAMP-01", "quantity": 20, "unit_cost": 250.00, "line_total": 5000.00}], "total": 5000.00},
            {"po_id": "PO-5002", "supplier_id": "SUP-001", "status": "draft", "created_at": "2026-05-01T09:00:00Z", "sku": "SKU-CHAIR-01", "quantity": 8, "unit_cost": 600.00, "total_amount": 4800.00, "currency": "ZAR", "lines": [{"sku": "SKU-CHAIR-01", "quantity": 8, "unit_cost": 600.00, "line_total": 4800.00}], "total": 4800.00},
            {"po_id": "PO-5003", "supplier_id": "SUP-003", "status": "open", "created_at": "2026-04-28T09:00:00Z", "sku": "SKU-CABLE-01", "quantity": 50, "unit_cost": 35.00, "total_amount": 1750.00, "currency": "ZAR", "lines": [{"sku": "SKU-CABLE-01", "quantity": 50, "unit_cost": 35.00, "line_total": 1750.00}], "total": 1750.00},
            {"po_id": "PO-5004", "supplier_id": "SUP-001", "status": "cancelled", "created_at": "2026-04-15T09:00:00Z", "sku": "SKU-DESK-01", "quantity": 10, "unit_cost": 700.00, "total_amount": 7000.00, "currency": "ZAR", "lines": [{"sku": "SKU-DESK-01", "quantity": 10, "unit_cost": 700.00, "line_total": 7000.00}], "total": 7000.00},
        ],
        "supplier_invoices": [
            {"invoice_id": "INV-SUP-8001", "supplier_id": "SUP-002", "po_id": "PO-5001", "amount": 5000.00, "currency": "ZAR", "status": "matched", "received_at": "2026-05-01T09:30:00Z"},
            {"invoice_id": "INV-SUP-8002", "supplier_id": "SUP-001", "po_id": "PO-5002", "amount": 5200.00, "currency": "ZAR", "status": "amount_mismatch", "received_at": "2026-05-01T09:40:00Z"},
            {"invoice_id": "INV-SUP-8003", "supplier_id": "SUP-003", "po_id": "PO-5003", "amount": 1750.00, "currency": "ZAR", "status": "matched", "received_at": "2026-05-01T09:50:00Z"},
            {"invoice_id": "INV-SUP-8004", "supplier_id": "SUP-004", "po_id": "", "amount": 999.00, "currency": "ZAR", "status": "unmatched_po", "received_at": "2026-05-01T10:00:00Z"},
        ],
    }
