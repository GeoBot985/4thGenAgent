from __future__ import annotations

from typing import Any


def message_validate_customer_status_reply(draft_reply: dict, order_context: dict) -> dict:
    body = str((draft_reply or {}).get("reply") or (draft_reply or {}).get("body") or "")
    order = (order_context or {}).get("order", {}) if isinstance(order_context, dict) else {}
    shipment = (order_context or {}).get("shipment", {}) if isinstance(order_context, dict) else {}
    facts = [str(item) for item in (order_context or {}).get("facts", []) if isinstance(item, str)]
    order_ref = str(order.get("order_ref", ""))
    ok = bool(body) and (not order_ref or order_ref in body)
    forbidden = any(token in body.lower() for token in ("refund", "compensation", "voucher", "credit", "free", "discount"))
    if forbidden:
        ok = False
    return {"ok": ok, "checks": [], "errors": [] if ok else ["STATUS_REPLY_INVALID"], "reply": draft_reply or {}, "order_context": order_context or {}, "facts": facts}


def message_validate_supplier_reorder_message(supplier_message: dict, draft_po: dict) -> dict:
    body = str((supplier_message or {}).get("body") or "")
    po_id = str((draft_po or {}).get("po_id") or "")
    skus = [str(line.get("sku", "")) for line in (draft_po or {}).get("lines", []) if isinstance(line, dict)]
    ok = bool(body) and (not po_id or po_id in body) and all(not sku or sku in body for sku in skus)
    return {"ok": ok, "checks": [], "errors": [] if ok else ["SUPPLIER_MESSAGE_INVALID"]}
