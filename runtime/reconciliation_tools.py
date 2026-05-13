from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def reconciliation_match_payments(payments: list[dict], orders: list[dict], invoices: list[dict], ledger_entries: list[dict]) -> dict:
    recon_run_id = f"RECON-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    matched = []
    exceptions = []
    seen_refs: set[str] = set()
    dup_refs: set[str] = set()
    for payment in payments:
        ref = str(payment.get("payment_ref", ""))
        if ref in seen_refs:
            dup_refs.add(ref)
        seen_refs.add(ref)
    for payment in payments:
        payment_id = str(payment.get("payment_id", ""))
        payment_ref = str(payment.get("payment_ref", ""))
        order_ref = str(payment.get("order_ref", ""))
        currency = str(payment.get("currency", ""))
        amount = round(float(payment.get("amount", 0) or 0), 2)
        order = next((row for row in orders if str(row.get("order_ref", "")) == order_ref), None)
        invoice = None
        if order and str(order.get("invoice_id", "")):
            invoice = next((row for row in invoices if str(row.get("invoice_id", "")) == str(order.get("invoice_id", ""))), None)
        if not invoice and order_ref:
            invoice = next((row for row in invoices if str(row.get("order_ref", "")) == order_ref), None)
        already_posted = any(str(entry.get("source_ref", "")) in {payment_ref, payment_id} for entry in ledger_entries)
        if payment_ref in dup_refs:
            exceptions.append(_exc("duplicate_payment_ref", payment, currency, message="Duplicate payment reference.", severity="high"))
            continue
        if already_posted:
            exceptions.append(_exc("already_posted", payment, currency, message="Payment already posted to ledger.", severity="medium"))
            continue
        if not order:
            exceptions.append(_exc("missing_order", payment, currency, message="Order could not be matched.", severity="high"))
            continue
        if not invoice:
            exceptions.append(_exc("missing_invoice", payment, currency, message="Invoice could not be matched.", severity="high"))
            continue
        invoice_total = round(float(invoice.get("invoice_total", 0) or 0), 2)
        if str(invoice.get("currency", "")) != currency or str(order.get("currency", "")) != currency:
            exceptions.append(_exc("currency_mismatch", payment, currency, message="Currency mismatch.", severity="critical"))
            continue
        if round(amount, 2) != round(invoice_total, 2):
            exceptions.append(_exc("amount_mismatch", payment, currency, expected_amount=invoice_total, actual_amount=amount, message="Payment amount does not match invoice.", severity="high"))
            continue
        matched.append({"payment_id": payment_id, "payment_ref": payment_ref, "order_ref": order_ref, "invoice_id": str(invoice.get("invoice_id", "")), "amount": amount, "currency": currency, "already_posted": False, "status": "matched"})
    summary = {"matched_count": len(matched), "exception_count": len(exceptions), "duplicate_count": sum(1 for exc in exceptions if exc["exception_type"] == "duplicate_payment_ref"), "amount_mismatch_count": sum(1 for exc in exceptions if exc["exception_type"] == "amount_mismatch"), "already_posted_count": sum(1 for exc in exceptions if exc["exception_type"] == "already_posted"), "unmatched_count": sum(1 for exc in exceptions if exc["exception_type"] == "missing_order"), "status": "exceptions" if exceptions else "matched"}
    return {"ok": True, "recon_run_id": recon_run_id, "payments_checked": len(payments), "matched": matched, "exceptions": exceptions, "summary": summary}


def reconciliation_validate_result(reconciliation_result: dict) -> dict:
    checks = []
    errors = []
    matched = reconciliation_result.get("matched", [])
    exceptions = reconciliation_result.get("exceptions", [])
    summary = reconciliation_result.get("summary", {})
    ok = bool(reconciliation_result.get("recon_run_id")) and isinstance(matched, list) and isinstance(exceptions, list) and isinstance(summary, dict)
    summary_ok = summary.get("matched_count") == len(matched) and summary.get("exception_count") == len(exceptions)
    checks.append({"id": "summary_counts_match", "ok": summary_ok, "message": "Summary counts match result lists."})
    if not summary_ok:
        ok = False
        errors.append("SUMMARY_COUNTS_MISMATCH")
    return {"ok": ok and summary_ok, "checks": checks, "errors": errors}


def _exc(exception_type: str, payment: dict, currency: str, expected_amount: float = 0.0, actual_amount: float = 0.0, message: str = "", severity: str = "high") -> dict:
    return {"exception_id": f"EXC-{uuid4().hex[:8].upper()}", "exception_type": exception_type, "payment_ref": str(payment.get("payment_ref", "")), "payment_id": str(payment.get("payment_id", "")), "order_ref": str(payment.get("order_ref", "")), "invoice_id": str(payment.get("invoice_id", "")), "expected_amount": expected_amount, "actual_amount": actual_amount, "currency": currency, "severity": severity, "message": message}
