from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from .company_store import read_json_table


def inventory_search_low_stock(runtime_root: str = "runtime_data") -> dict:
    items = read_json_table("inventory", runtime_root)
    low_stock = [item for item in items if int(item.get("available_stock", 0) or 0) <= int(item.get("reorder_threshold", 0) or 0)]
    return {"items": low_stock, "count": len(low_stock)}


def inventory_filter_reorder_candidates(items: list[dict]) -> dict:
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for item in items:
        reorder_qty = max(0, int(item.get("target_stock_level", 0) or 0) - int(item.get("available_stock", 0) or 0))
        if reorder_qty > 0 and item.get("preferred_supplier_id") and item.get("unit_cost") is not None:
            candidate = dict(item)
            candidate["reorder_qty"] = reorder_qty
            candidates.append(candidate)
        else:
            excluded.append(dict(item))
    return {"candidates": candidates, "excluded": excluded, "count": len(candidates)}


def purchase_order_check_duplicate_open(candidates: list[dict], runtime_root: str = "runtime_data") -> dict:
    purchase_orders = read_json_table("purchase_orders", runtime_root)
    open_statuses = {"open", "draft", "submitted", "approved"}
    valid_candidates: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for candidate in candidates:
        sku = str(candidate.get("sku", ""))
        duplicate = next((po for po in purchase_orders if str(po.get("status", "")).lower() in open_statuses and any(str(line.get("sku", "")).upper() == sku.upper() for line in (po.get("lines", []) if isinstance(po.get("lines"), list) else []))), None)
        if duplicate:
            duplicates.append({"sku": sku, "po_id": duplicate.get("po_id", ""), "status": duplicate.get("status", "")})
        else:
            valid_candidates.append(dict(candidate))
    return {"valid_candidates": valid_candidates, "duplicates": duplicates, "blocked_count": len(duplicates), "valid_count": len(valid_candidates)}


def supplier_select_for_sku(candidates: list[dict], runtime_root: str = "runtime_data") -> dict:
    suppliers = read_json_table("suppliers", runtime_root)
    selected_candidates: list[dict[str, Any]] = []
    excluded_candidates: list[dict[str, Any]] = []
    selected_supplier: dict[str, Any] | None = None
    for candidate in candidates:
        supplier_id = candidate.get("preferred_supplier_id")
        supplier = next((row for row in suppliers if row.get("supplier_id") == supplier_id), None)
        if not supplier or str(supplier.get("status", "")).lower() != "active" or candidate.get("sku") not in set(supplier.get("supported_skus", []) if isinstance(supplier.get("supported_skus"), list) else []):
            excluded_candidates.append(dict(candidate))
            continue
        if selected_supplier is None:
            selected_supplier = dict(supplier)
        if supplier.get("supplier_id") == selected_supplier.get("supplier_id"):
            selected_candidates.append(dict(candidate))
        else:
            excluded_candidates.append(dict(candidate))
    if not selected_supplier:
        return {"supplier": {}, "selected_candidates": [], "excluded_candidates": excluded_candidates, "selection_reason": "No active preferred supplier found."}
    return {"supplier": {"supplier_id": selected_supplier.get("supplier_id", ""), "name": selected_supplier.get("name", ""), "email": selected_supplier.get("email", ""), "lead_time_days": selected_supplier.get("lead_time_days", 0)}, "selected_candidates": selected_candidates, "excluded_candidates": excluded_candidates, "selection_reason": "Preferred active supplier selected for first valid supplier group."}


def purchase_order_build_draft(supplier: dict, candidates: list[dict]) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    po_id = f"PO-DRAFT-{timestamp}-{uuid.uuid4().hex[:6].upper()}"
    lines = []
    total = 0.0
    currency = "ZAR"
    for candidate in candidates:
        quantity = int(candidate.get("reorder_qty", 0) or 0)
        unit_cost = round(float(candidate.get("unit_cost", 0) or 0), 2)
        line_total = round(quantity * unit_cost, 2)
        total += line_total
        currency = str(candidate.get("currency", currency))
        lines.append({"sku": candidate.get("sku", ""), "name": candidate.get("name", ""), "quantity": quantity, "unit_cost": unit_cost, "line_total": line_total})
    return {"po_id": po_id, "supplier_id": supplier.get("supplier_id", ""), "supplier_name": supplier.get("name", ""), "status": "draft", "currency": currency, "lines": lines, "total": round(total, 2)}


def purchase_order_validate_draft(draft_po: dict) -> dict:
    checks = []
    errors = []
    ok = True
    def add_check(check_id: str, condition: bool, message: str) -> None:
        nonlocal ok
        checks.append({"id": check_id, "ok": condition, "message": message})
        if not condition:
            ok = False
            errors.append(message)
    add_check("po_has_id", bool(draft_po.get("po_id")), "Draft PO has a po_id.")
    add_check("po_has_supplier_id", bool(draft_po.get("supplier_id")), "Draft PO has a supplier_id.")
    add_check("po_status_draft", draft_po.get("status") == "draft", "Draft PO status is draft.")
    lines = draft_po.get("lines", [])
    add_check("po_has_lines", isinstance(lines, list) and len(lines) > 0, "Draft PO has at least one line.")
    total = 0.0
    currency = draft_po.get("currency")
    currencies = set()
    for line in lines if isinstance(lines, list) else []:
        qty = int(line.get("quantity", 0) or 0)
        unit_cost = float(line.get("unit_cost", 0) or 0)
        line_total = float(line.get("line_total", 0) or 0)
        currencies.add(currency)
        add_check("po_line_sku", bool(line.get("sku")), "Each line has a sku.")
        add_check("po_line_qty_positive", qty > 0, "Each line quantity is greater than zero.")
        add_check("po_line_unit_cost_non_negative", unit_cost >= 0, "Each line unit_cost is non-negative.")
        add_check("po_line_total_matches", round(qty * unit_cost, 2) == round(line_total, 2), "Each line_total matches quantity * unit_cost.")
        total += round(line_total, 2)
    add_check("po_total_matches", round(float(draft_po.get("total", 0) or 0), 2) == round(total, 2), "PO total matches sum of line totals.")
    add_check("po_single_currency", len({str(draft_po.get("currency", ""))}) == 1, "Draft PO uses a single currency.")
    return {"ok": ok, "checks": checks, "errors": errors}


def supplier_prepare_message_action(supplier: dict, draft_po: dict, message: dict) -> dict:
    return {
        "action_type": "send_supplier_message",
        "tool": "supplier/send_message",
        "to": supplier.get("email", ""),
        "subject": str(message.get("subject", f"Purchase Order {draft_po.get('po_id', '')}")),
        "body": str(message.get("body", "")),
        "draft_po": dict(draft_po),
        "status": "PENDING_APPROVAL",
    }


def supplier_send_message(
    to: str,
    subject: str,
    body: str,
    draft_po: dict | None = None,
    dry_run: bool = True,
    runtime_root: str = "runtime_data",
) -> dict:
    po_id = str((draft_po or {}).get("po_id", ""))
    if not dry_run:
        return {
            "ok": False,
            "dry_run": False,
            "sent": False,
            "action": "supplier_send_message",
            "to": to,
            "subject": subject,
            "body_preview": body[:120],
            "po_id": po_id,
            "error": "Live supplier send is not supported in Spec 052.",
        }
    return {
        "ok": True,
        "dry_run": True,
        "action": "supplier_send_message",
        "to": to,
        "subject": subject,
        "body_preview": body[:120],
        "po_id": po_id,
        "sent": False,
        "message": "Supplier message dry-run execution completed.",
    }
