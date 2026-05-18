"""Spec 110 — Order Management Workflow Pack v1 tools."""
from __future__ import annotations

import datetime
import json
from typing import Any

from .business_store import (
    get_customer,
    get_order,
    get_order_items,
    get_payment,
    get_shipment,
    load_business_dataset,
    search_inventory,
)
from .timing import utc_now

ALLOWED_SHIPMENT_STATUSES = {
    "pending",
    "packed",
    "ready_for_dispatch",
    "shipped",
    "in_transit",
    "delivered",
    "delayed",
    "exception",
    "cancelled",
}


def _parse_items(items: Any) -> list[dict]:
    """Parse items from either a list or a JSON-encoded string."""
    if items is None:
        return []
    if isinstance(items, str):
        items = items.strip()
        if not items:
            return []
        try:
            parsed = json.loads(items)
            if isinstance(parsed, list):
                return [dict(i) for i in parsed if isinstance(i, dict)]
            return []
        except (json.JSONDecodeError, ValueError):
            return []
    if isinstance(items, list):
        return [dict(i) for i in items if isinstance(i, dict)]
    return []


def order_validate_new(
    customer_id: str,
    items: Any = None,
    runtime_root: str = "runtime_data",
) -> dict:
    """Validate a new order: customer exists, items valid, stock available."""
    failure_reasons: list[str] = []

    # Check customer
    customer = get_customer(customer_id, runtime_root=runtime_root)
    if not customer:
        failure_reasons.append(f"CUSTOMER_NOT_FOUND:{customer_id}")

    # Parse items
    parsed_items = _parse_items(items)
    if not parsed_items:
        failure_reasons.append("ITEMS_EMPTY_OR_INVALID")

    stock_checks: list[dict] = []
    order_total: float = 0.0

    for item in parsed_items:
        sku = str(item.get("sku", "")).strip()
        quantity = int(item.get("quantity", 0) or 0)
        if not sku:
            failure_reasons.append("ITEM_MISSING_SKU")
            continue
        if quantity <= 0:
            failure_reasons.append(f"ITEM_INVALID_QUANTITY:{sku}")
            continue
        inv_results = search_inventory(sku=sku, runtime_root=runtime_root)
        if not inv_results:
            failure_reasons.append(f"SKU_NOT_FOUND:{sku}")
            stock_checks.append({"sku": sku, "quantity": quantity, "available_stock": 0, "sufficient": False})
            continue
        inv = inv_results[0]
        available = int(inv.get("available_stock", 0) or 0)
        sufficient = available >= quantity
        unit_price = float(inv.get("unit_price", 0.0) or 0.0)
        order_total += unit_price * quantity
        if not sufficient:
            failure_reasons.append(f"INSUFFICIENT_STOCK:{sku}:available={available}:requested={quantity}")
        stock_checks.append({
            "sku": sku,
            "quantity": quantity,
            "available_stock": available,
            "sufficient": sufficient,
        })

    valid = len(failure_reasons) == 0
    return {
        "ok": True,
        "customer_id": customer_id,
        "valid": valid,
        "items": parsed_items,
        "stock_checks": stock_checks,
        "order_total": order_total,
        "failure_reasons": failure_reasons,
        "error": "" if valid else "VALIDATION_FAILED",
    }


def order_prepare_stock_reservation(
    order_ref: str,
    items: Any = None,
    runtime_root: str = "runtime_data",
) -> dict:
    """Stage a stock reservation pending action. Does NOT mutate inventory."""
    parsed_items = _parse_items(items)
    reservation_lines: list[dict] = []

    for item in parsed_items:
        sku = str(item.get("sku", "")).strip()
        quantity = int(item.get("quantity", 0) or 0)
        inv_results = search_inventory(sku=sku, runtime_root=runtime_root)
        before_stock = int(inv_results[0].get("available_stock", 0) or 0) if inv_results else 0
        after_stock = max(0, before_stock - quantity)
        reservation_lines.append({
            "sku": sku,
            "quantity": quantity,
            "before_stock": before_stock,
            "after_stock": after_stock,
        })

    return {
        "ok": True,
        "action_type": "reserve_stock",
        "tool": "order/execute_stock_reservation",
        "order_ref": order_ref,
        "reservation_lines": reservation_lines,
        "status": "PENDING_APPROVAL",
        "created_at": utc_now(),
        "error": "",
    }


def order_execute_stock_reservation(
    order_ref: str,
    reservation_lines: Any = None,
    dry_run: bool = True,
    runtime_root: str = "runtime_data",
) -> dict:
    """Simulate stock reservation. dry_run=False is blocked."""
    if not dry_run:
        return {
            "ok": False,
            "dry_run": False,
            "order_ref": order_ref,
            "reservation_lines": [],
            "before_stock": {},
            "after_stock": {},
            "executed": False,
            "error": "LIVE_MODE_BLOCKED",
            "evidence": "Live stock mutation is not permitted. Only dry_run=True is supported.",
        }

    # Parse reservation_lines (may arrive as JSON string or list)
    if isinstance(reservation_lines, str):
        try:
            reservation_lines = json.loads(reservation_lines)
        except (json.JSONDecodeError, ValueError):
            reservation_lines = []
    if not reservation_lines:
        reservation_lines = []

    before_stock: dict[str, int] = {}
    after_stock: dict[str, int] = {}
    evidence_lines: list[str] = []

    for line in reservation_lines:
        sku = str(line.get("sku", "")).strip()
        quantity = int(line.get("quantity", 0) or 0)
        inv_results = search_inventory(sku=sku, runtime_root=runtime_root)
        b_stock = int(inv_results[0].get("available_stock", 0) or 0) if inv_results else int(line.get("before_stock", 0) or 0)
        a_stock = max(0, b_stock - quantity)
        before_stock[sku] = b_stock
        after_stock[sku] = a_stock
        evidence_lines.append(f"[DRY-RUN] SKU {sku}: {b_stock} -> {a_stock} (reserved {quantity})")

    return {
        "ok": True,
        "dry_run": True,
        "order_ref": order_ref,
        "reservation_lines": reservation_lines,
        "before_stock": before_stock,
        "after_stock": after_stock,
        "executed": True,
        "error": "",
        "evidence": "; ".join(evidence_lines) if evidence_lines else "No reservation lines processed.",
    }


def order_check_payment_status(
    order_ref: str,
    runtime_root: str = "runtime_data",
) -> dict:
    """Check payment status for an order."""
    order = get_order(order_ref, runtime_root=runtime_root)
    if not order:
        return {
            "ok": False,
            "order_ref": order_ref,
            "payment_status": "ORDER_NOT_FOUND",
            "payment_refs": [],
            "paid_amount": 0.0,
            "order_total": 0.0,
            "can_release": False,
            "error": "ORDER_NOT_FOUND",
        }

    order_total = float(order.get("total_amount", 0.0) or 0.0)
    payment = get_payment(order_ref, runtime_root=runtime_root)

    if not payment:
        return {
            "ok": True,
            "order_ref": order_ref,
            "payment_status": "no_payment",
            "payment_refs": [],
            "paid_amount": 0.0,
            "order_total": order_total,
            "can_release": False,
            "error": "",
        }

    payment_status = str(payment.get("status", "")).strip()
    paid_amount = float(payment.get("amount", 0.0) or 0.0)
    payment_refs = [str(payment.get("payment_id", ""))]
    can_release = payment_status == "matched"

    return {
        "ok": True,
        "order_ref": order_ref,
        "payment_status": payment_status,
        "payment_refs": payment_refs,
        "paid_amount": paid_amount,
        "order_total": order_total,
        "can_release": can_release,
        "error": "",
    }


def order_prepare_release_paid_order(
    order_ref: str,
    runtime_root: str = "runtime_data",
) -> dict:
    """Prepare a release action for a paid order."""
    payment_check = order_check_payment_status(order_ref, runtime_root=runtime_root)
    can_release = payment_check.get("can_release", False)
    payment_status = payment_check.get("payment_status", "unknown")

    if not can_release:
        return {
            "ok": False,
            "order_ref": order_ref,
            "payment_status": payment_status,
            "can_release": False,
            "error": f"CANNOT_RELEASE:payment_status={payment_status}",
        }

    return {
        "ok": True,
        "action_type": "release_paid_order",
        "tool": "order/execute_release_paid_order",
        "order_ref": order_ref,
        "status": "PENDING_APPROVAL",
        "created_at": utc_now(),
        "payment_status": payment_status,
        "can_release": True,
        "error": "",
    }


def order_execute_release_paid_order(
    order_ref: str,
    dry_run: bool = True,
    runtime_root: str = "runtime_data",
) -> dict:
    """Simulate releasing a paid order: status paid->released, shipment pending->ready_for_dispatch."""
    order = get_order(order_ref, runtime_root=runtime_root)
    before_status = str(order.get("status", "unknown")) if order else "ORDER_NOT_FOUND"
    after_status = "released" if dry_run else before_status

    shipment = get_shipment(order_ref, runtime_root=runtime_root, prefer_order_ref=True)
    shipment_before = str(shipment.get("status", "none")) if shipment else "none"
    shipment_after = "ready_for_dispatch" if shipment and shipment_before in {"pending", "packed"} else shipment_before

    evidence_parts = [
        f"[DRY-RUN] Order {order_ref}: status {before_status} -> {after_status}",
        f"[DRY-RUN] Shipment: status {shipment_before} -> {shipment_after}",
    ]

    return {
        "ok": True,
        "dry_run": dry_run,
        "order_ref": order_ref,
        "before_status": before_status,
        "after_status": after_status,
        "executed": True,
        "error": "",
        "evidence": "; ".join(evidence_parts),
    }


def order_detect_delayed_orders(
    days_overdue: int = 2,
    runtime_root: str = "runtime_data",
) -> dict:
    """Detect orders that are released but not shipped by expected/estimated delivery date."""
    try:
        days_overdue = int(days_overdue)
    except (TypeError, ValueError):
        days_overdue = 2

    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days_overdue)

    dataset = load_business_dataset(runtime_root)
    shipments = dataset.get("shipments", [])
    orders = dataset.get("orders", [])

    # Build order map for quick lookup
    order_map: dict[str, dict] = {str(o.get("order_ref", "")).upper(): o for o in orders}

    active_statuses = {"in_transit", "packed", "ready_for_dispatch", "shipped"}

    delayed_orders: list[dict] = []
    for shipment in shipments:
        shipment_status = str(shipment.get("status", "")).strip().lower()
        if shipment_status not in active_statuses:
            continue
        est_delivery_str = str(shipment.get("estimated_delivery", "")).strip()
        if not est_delivery_str:
            continue
        try:
            est_delivery = datetime.date.fromisoformat(est_delivery_str)
        except (ValueError, TypeError):
            continue
        if est_delivery < cutoff:
            order_ref = str(shipment.get("order_ref", ""))
            order = order_map.get(order_ref.upper(), {})
            delayed_orders.append({
                "order_ref": order_ref,
                "shipment_id": shipment.get("shipment_id", ""),
                "shipment_status": shipment_status,
                "estimated_delivery": est_delivery_str,
                "days_overdue": (today - est_delivery).days,
                "order_status": order.get("status", "unknown"),
                "customer_id": order.get("customer_id", ""),
            })

    return {
        "ok": True,
        "delayed_orders": delayed_orders,
        "count": len(delayed_orders),
        "days_overdue": days_overdue,
        "checked_at": utc_now(),
        "error": "",
    }


def order_prepare_shipment_status_update(
    order_ref: str,
    shipment_status: str = "",
    tracking_ref: str = "",
    runtime_root: str = "runtime_data",
) -> dict:
    """Prepare a shipment status update as a pending action."""
    shipment_status = str(shipment_status).strip().lower()
    if shipment_status not in ALLOWED_SHIPMENT_STATUSES:
        return {
            "ok": False,
            "order_ref": order_ref,
            "shipment_status": shipment_status,
            "error": f"INVALID_SHIPMENT_STATUS:{shipment_status}",
        }

    return {
        "ok": True,
        "action_type": "update_shipment_status",
        "tool": "order/execute_shipment_status_update",
        "order_ref": order_ref,
        "shipment_status": shipment_status,
        "tracking_ref": str(tracking_ref or "").strip(),
        "status": "PENDING_APPROVAL",
        "created_at": utc_now(),
        "error": "",
    }


def order_execute_shipment_status_update(
    order_ref: str,
    shipment_status: str = "",
    tracking_ref: str = "",
    dry_run: bool = True,
    runtime_root: str = "runtime_data",
) -> dict:
    """Simulate a shipment status update."""
    shipment = get_shipment(order_ref, runtime_root=runtime_root, prefer_order_ref=True)
    before_status = str(shipment.get("status", "none")) if shipment else "none"
    after_status = str(shipment_status).strip().lower() if shipment_status else before_status
    tracking_ref = str(tracking_ref or "").strip()

    evidence = (
        f"[DRY-RUN] Shipment for {order_ref}: status {before_status} -> {after_status}"
        + (f"; tracking_ref={tracking_ref}" if tracking_ref else "")
    )

    return {
        "ok": True,
        "dry_run": dry_run,
        "order_ref": order_ref,
        "before_status": before_status,
        "after_status": after_status,
        "tracking_ref": tracking_ref,
        "executed": True,
        "error": "",
        "evidence": evidence,
    }
