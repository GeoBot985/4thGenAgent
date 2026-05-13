from __future__ import annotations


from .business_store import get_customer
from .company_store import find_many
from .taskframe import utc_now


def customer_read(customer_id: str, runtime_root: str = "runtime_data") -> dict:
    customer = get_customer(customer_id, runtime_root=runtime_root)
    if not customer:
        return {"ok": False, "customer": {}, "error": "CUSTOMER_ORDER_MISMATCH", "message": f"Customer not found: {customer_id}"}
    return {"ok": True, "customer": customer, "error": "", "message": ""}


def customer_search(customer_id: str = "", name: str = "", status: str = "", runtime_root: str = "runtime_data") -> dict:
    rows = find_many("customers", lambda row: True, runtime_root)
    results = []
    for row in rows:
        if customer_id and str(row.get("customer_id", "")).upper() != customer_id.upper():
            continue
        if name and name.lower() not in str(row.get("name", "")).lower():
            continue
        if status and str(row.get("status", "")).lower() != status.lower():
            continue
        results.append(row)
    return {"ok": True, "customers": results, "count": len(results), "error": ""}


def customer_validate_exists(customer: dict) -> dict:
    ok = bool(customer and customer.get("customer_id"))
    return {"ok": ok, "customer": customer or {}, "message": "" if ok else "Customer not found.", "error": "" if ok else "CUSTOMER_ORDER_MISMATCH"}


def customer_validate_owns_order(customer: dict, order: dict) -> dict:
    customer_id = str((customer or {}).get("customer_id", ""))
    order_customer_id = str((order or {}).get("customer_id", ""))
    ok = bool(customer_id) and customer_id == order_customer_id
    return {
        "ok": ok,
        "customer_id": customer_id,
        "order_customer_id": order_customer_id,
        "order_ref": str((order or {}).get("order_ref", "")),
        "message": "Customer owns order." if ok else "Customer does not own order.",
        "error": "" if ok else "CUSTOMER_ORDER_MISMATCH",
    }


def customer_prepare_message_action(customer: dict, channel: str, message: dict) -> dict:
    body = str((message or {}).get("reply") or (message or {}).get("body") or "")
    if not body:
        return {"ok": False, "error": "INVALID_MESSAGE", "message": "Reply body is required."}
    return {
        "ok": True,
        "action_type": "send_customer_message",
        "tool": "customer/send_message",
        "to": str((customer or {}).get("customer_id", "")),
        "channel": channel,
        "body": body,
        "status": "PENDING_APPROVAL",
        "created_at": utc_now(),
    }
