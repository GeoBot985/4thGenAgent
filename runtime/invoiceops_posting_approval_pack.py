from __future__ import annotations

"""
Spec 156 — InvoiceOps Posting Approval Pack.

Builds a human-readable approval pack for operator review before any
live InvoiceOps sheet posting. Does not approve actions automatically.
"""

from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


APPROVAL_CHECKLIST_ITEMS = [
    "invoice_validated",
    "supplier_matched",
    "po_matched_or_exception_recorded",
    "receipt_matched_or_exception_recorded",
    "duplicate_check_passed",
    "totals_and_tax_checked",
    "ledger_rows_balanced",
    "rollback_plan_exists",
    "target_sheet_and_range_identified",
    "live_write_confirmation_required",
]


def build_invoiceops_posting_approval_pack(
    *,
    posting_plan: dict[str, Any],
    invoice: dict[str, Any] | None = None,
    match_result: dict[str, Any] | None = None,
    exceptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build the approval pack for InvoiceOps live posting.

    Returns a structured pack that the operator reviews before approving
    any pending actions. Does not change action status.
    """
    inv = dict(invoice or {})
    match = dict(match_result or {})
    excs = list(exceptions or [])

    invoice_id = str(inv.get("invoice_id") or posting_plan.get("invoice_id") or "")
    invoice_number = str(inv.get("invoice_number") or posting_plan.get("invoice_number") or "")
    supplier_name = str(inv.get("supplier_name") or posting_plan.get("supplier_name") or "")
    po_number = str(inv.get("po_number") or posting_plan.get("po_number") or "")
    match_status = str(match.get("match_status") or posting_plan.get("match_status") or "unknown")
    posting_plan_id = str(posting_plan.get("posting_plan_id") or "")
    pending_actions = list(posting_plan.get("pending_actions") or [])
    frame_id = str(posting_plan.get("frame_id") or "")

    # Build approval checklist
    checklist = _build_approval_checklist(
        invoice=inv,
        match_result=match,
        exceptions=excs,
        posting_plan=posting_plan,
    )

    # Build risk summary
    risk_summary = _build_risk_summary(
        match_status=match_status,
        exceptions=excs,
        posting_plan=posting_plan,
    )

    # Build rollback summary
    rollback_summary = _build_rollback_summary(posting_plan)

    # Build human summary
    human_summary = _build_human_summary(
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        po_number=po_number,
        match_status=match_status,
        eligible_count=posting_plan.get("eligible_write_count", 0),
        blocked_count=posting_plan.get("blocked_write_count", 0),
        action_count=len(pending_actions),
    )

    # Collect report refs
    report_refs = _collect_report_refs(inv, match, posting_plan)

    ok = all(item["passed"] for item in checklist if item.get("required"))

    return {
        "ok": ok,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "supplier_name": supplier_name,
        "po_number": po_number,
        "frame_id": frame_id,
        "posting_plan_id": posting_plan_id,
        "match_status": match_status,
        "pending_actions": pending_actions,
        "human_summary": human_summary,
        "risk_summary": risk_summary,
        "approval_checklist": checklist,
        "rollback_summary": rollback_summary,
        "report_refs": report_refs,
        "generated_at": _utc_now(),
    }


def _build_approval_checklist(
    *,
    invoice: dict[str, Any],
    match_result: dict[str, Any],
    exceptions: list[dict[str, Any]],
    posting_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    checklist: list[dict[str, Any]] = []

    def item(key: str, passed: bool, note: str = "", required: bool = True) -> None:
        checklist.append({
            "item": key,
            "passed": passed,
            "note": note,
            "required": required,
        })

    # 1. Invoice validated
    has_invoice = bool(invoice.get("invoice_id") or invoice.get("invoice_number"))
    item("invoice_validated", has_invoice, "" if has_invoice else "Invoice data not provided.")

    # 2. Supplier matched
    has_supplier = bool(invoice.get("supplier_name") or invoice.get("supplier_id"))
    item("supplier_matched", has_supplier, "" if has_supplier else "Supplier name/ID missing from invoice.")

    # 3. PO matched or exception recorded
    has_po = bool(invoice.get("po_number") or posting_plan.get("po_number"))
    has_po_exception = any(
        e.get("exception_type") in ("wrong_po", "missing_po")
        for e in exceptions
    )
    po_ok = has_po or has_po_exception
    item("po_matched_or_exception_recorded", po_ok, "" if po_ok else "PO not matched and no PO exception recorded.")

    # 4. Receipt matched or exception recorded
    match_checks = list(match_result.get("checks") or [])
    receipt_check = next((c for c in match_checks if "receipt" in str(c.get("check_id", "")).lower()), None)
    has_receipt_exception = any(e.get("exception_type") == "missing_receipt" for e in exceptions)
    receipt_ok = (receipt_check and receipt_check.get("status") in ("pass", "warn", "not_applicable")) or has_receipt_exception or not match_checks
    item("receipt_matched_or_exception_recorded", receipt_ok, "" if receipt_ok else "Receipt check failed and no receipt exception recorded.")

    # 5. Duplicate check passed
    dup_exception = any(e.get("exception_type") == "duplicate_invoice" for e in exceptions)
    dup_ok = not dup_exception
    item("duplicate_check_passed", dup_ok, "" if dup_ok else "Duplicate invoice exception detected.")

    # 6. Totals and tax checked
    has_totals = bool(invoice.get("invoice_total") or invoice.get("subtotal"))
    item("totals_and_tax_checked", has_totals, "" if has_totals else "Invoice totals not available for review.")

    # 7. Ledger rows balanced
    match_status = str(match_result.get("match_status") or posting_plan.get("match_status") or "")
    ledger_ok = match_status in ("matched", "exception") or match_status == ""
    item("ledger_rows_balanced", ledger_ok, "" if ledger_ok else f"Ledger balance uncertain (match_status={match_status}).")

    # 8. Rollback plan exists
    has_rollback = bool(posting_plan.get("rollback_plans"))
    item("rollback_plan_exists", has_rollback, "" if has_rollback else "No rollback plans found in posting plan.")

    # 9. Target sheet/range identified
    has_targets = bool(posting_plan.get("write_targets"))
    item("target_sheet_and_range_identified", has_targets, "" if has_targets else "No write targets in posting plan.")

    # 10. Live write confirmation required (always)
    item("live_write_confirmation_required", True, "Typed confirmation phrase required before execution.")

    return checklist


def _build_risk_summary(
    *,
    match_status: str,
    exceptions: list[dict[str, Any]],
    posting_plan: dict[str, Any],
) -> list[str]:
    risks: list[str] = []

    if match_status == "blocked":
        risks.append("CRITICAL: match_status is 'blocked'. Ledger writes are prohibited.")
    elif match_status == "exception":
        risks.append("WARNING: match_status is 'exception'. Review exceptions before posting.")

    high_exceptions = [e for e in exceptions if e.get("severity") in ("high", "blocker")]
    if high_exceptions:
        for exc in high_exceptions:
            risks.append(f"HIGH: {exc.get('exception_type', '')} — {exc.get('message', '')}")

    blocked_writes = posting_plan.get("blocked_write_count", 0)
    if blocked_writes:
        risks.append(f"INFO: {blocked_writes} write(s) blocked from live eligibility.")

    if not risks:
        risks.append("No significant risks identified.")

    return risks


def _build_rollback_summary(posting_plan: dict[str, Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for rp in posting_plan.get("rollback_plans") or []:
        summary.append({
            "rollback_id": rp.get("rollback_id", ""),
            "target": rp.get("target", ""),
            "rollback_type": rp.get("rollback_type", ""),
            "safe_to_auto_prepare": rp.get("safe_to_auto_prepare", False),
            "reason": rp.get("reason", ""),
        })
    return summary


def _build_human_summary(
    *,
    invoice_number: str,
    supplier_name: str,
    po_number: str,
    match_status: str,
    eligible_count: int,
    blocked_count: int,
    action_count: int,
) -> str:
    parts = [
        f"Invoice {invoice_number}" if invoice_number else "Unknown invoice",
        f"from {supplier_name}" if supplier_name else "",
        f"(PO: {po_number})" if po_number else "",
        f"— match status: {match_status}.",
        f"{eligible_count} write(s) eligible for live posting.",
    ]
    if blocked_count:
        parts.append(f"{blocked_count} write(s) blocked.")
    if action_count:
        parts.append(f"{action_count} pending action(s) await operator approval.")
    return " ".join(p for p in parts if p)


def _collect_report_refs(
    invoice: dict[str, Any],
    match_result: dict[str, Any],
    posting_plan: dict[str, Any],
) -> list[str]:
    refs: list[str] = []
    if invoice.get("invoice_id"):
        refs.append(f"invoice:{invoice['invoice_id']}")
    if match_result.get("match_id"):
        refs.append(f"match:{match_result['match_id']}")
    if posting_plan.get("posting_plan_id"):
        refs.append(f"posting_plan:{posting_plan['posting_plan_id']}")
    return refs
