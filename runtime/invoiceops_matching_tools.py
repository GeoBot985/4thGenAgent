from __future__ import annotations

from typing import Any

from .tool_result_contract import build_tool_evidence

_MATCH_CHECK_TYPE = "invoiceops_match_check"
_MATCH_RESULT_TYPE = "invoiceops_match_result"

_TOLERANCE = 0.01
_UNKNOWN_SUPPLIER = "UNKNOWN_SUPPLIER"
_BLOCKING_PO_STATUSES = frozenset({"cancelled", "closed"})

# Check IDs used in the canonical checks list
_CHK_DUP = "DUP_CHECK"
_CHK_PO = "PO_CHECK"
_CHK_RECEIPT = "RECEIPT_CHECK"
_CHK_SUPPLIER = "SUPPLIER_CHECK"
_CHK_TOTALS = "TOTALS_CHECK"
_CHK_TAX = "TAX_CHECK"

# Which check IDs cause match_status = "blocked" when they fail
_BLOCKING_CHECK_IDS = frozenset({_CHK_DUP, _CHK_PO, _CHK_RECEIPT, _CHK_SUPPLIER, _CHK_TOTALS})

# Map from check_id prefix → exception_type
_EXCEPTION_TYPE_MAP: dict[str, str] = {
    _CHK_DUP: "duplicate_invoice",
    _CHK_PO: "missing_po",
    _CHK_RECEIPT: "missing_receipt",
    _CHK_SUPPLIER: "supplier_mismatch",
    _CHK_TOTALS: "amount_mismatch",
    _CHK_TAX: "tax_mismatch",
    "QTY_CHECK": "quantity_mismatch",
}


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def invoiceops_check_duplicate_invoice(
    invoice: dict,
    invoice_register: list[dict],
) -> dict:
    invoice_number = str(invoice.get("invoice_number", "")).strip()
    supplier_id = str(invoice.get("supplier_id", "")).strip()
    unknown = supplier_id == _UNKNOWN_SUPPLIER

    for rec in invoice_register:
        reg_supplier = str(rec.get("supplier_id", "")).strip()
        reg_number = str(rec.get("invoice_number", "")).strip()

        if unknown and reg_number == invoice_number:
            return _check("invoiceops/check_duplicate_invoice", _CHK_DUP, "warn",
                          expected="no duplicate",
                          actual=f"invoice_number={invoice_number!r} exists; supplier unknown",
                          message=(
                              f"Invoice number {invoice_number!r} already exists in register "
                              f"but supplier is UNKNOWN_SUPPLIER; uniqueness cannot be confirmed."
                          ),
                          details={"candidate": rec})

        if reg_supplier == supplier_id and reg_number == invoice_number:
            return _check("invoiceops/check_duplicate_invoice", _CHK_DUP, "fail",
                          expected="no duplicate",
                          actual=f"supplier={supplier_id!r}, invoice_number={invoice_number!r}",
                          message=f"Duplicate: invoice {invoice_number!r} already exists for supplier {supplier_id!r}.",
                          details={"duplicate_record": rec})

    return _check("invoiceops/check_duplicate_invoice", _CHK_DUP, "pass",
                  expected="no duplicate",
                  actual="not found in register",
                  message=f"Invoice {invoice_number!r} is unique for supplier {supplier_id!r}.",
                  details={})


def invoiceops_lookup_purchase_order(
    invoice: dict,
    po_register: list[dict],
) -> dict:
    po_number = str(invoice.get("po_number", "")).strip()
    if not po_number:
        return _check("invoiceops/lookup_purchase_order", _CHK_PO, "fail",
                      expected="po_number present in invoice",
                      actual="",
                      message="Invoice has no PO number.",
                      details={})

    for po in po_register:
        if str(po.get("po_number", "")).strip() == po_number:
            status = str(po.get("status", "")).strip()
            if status in _BLOCKING_PO_STATUSES:
                return _check("invoiceops/lookup_purchase_order", _CHK_PO, "fail",
                              expected="open or part_received",
                              actual=status,
                              message=f"PO {po_number!r} has status {status!r} and cannot be matched.",
                              details={"purchase_order": po})
            return _check("invoiceops/lookup_purchase_order", _CHK_PO, "pass",
                          expected=po_number,
                          actual=po_number,
                          message=f"PO {po_number!r} found with status {status!r}.",
                          details={"purchase_order": po})

    return _check("invoiceops/lookup_purchase_order", _CHK_PO, "fail",
                  expected=po_number,
                  actual="not found",
                  message=f"PO {po_number!r} not found in register.",
                  details={})


def invoiceops_lookup_goods_receipt(
    invoice: dict,
    receipt_register: list[dict],
) -> dict:
    po_number = str(invoice.get("po_number", "")).strip()
    for receipt in receipt_register:
        if str(receipt.get("po_number", "")).strip() == po_number:
            status = str(receipt.get("status", "")).strip()
            rid = str(receipt.get("receipt_id", ""))
            if status == "cancelled":
                return _check("invoiceops/lookup_goods_receipt", _CHK_RECEIPT, "fail",
                              expected="received or partial",
                              actual="cancelled",
                              message=f"Receipt {rid!r} for PO {po_number!r} is cancelled.",
                              details={"goods_receipt": receipt})
            if status == "partial":
                return _check("invoiceops/lookup_goods_receipt", _CHK_RECEIPT, "warn",
                              expected="received",
                              actual="partial",
                              message=f"Receipt {rid!r} for PO {po_number!r} is partial; goods not fully received.",
                              details={"goods_receipt": receipt})
            return _check("invoiceops/lookup_goods_receipt", _CHK_RECEIPT, "pass",
                          expected="received",
                          actual=rid,
                          message=f"Receipt {rid!r} found for PO {po_number!r}.",
                          details={"goods_receipt": receipt})

    return _check("invoiceops/lookup_goods_receipt", _CHK_RECEIPT, "fail",
                  expected=f"receipt for po={po_number!r}",
                  actual="not found",
                  message=f"No goods receipt found for PO {po_number!r}.",
                  details={})


def invoiceops_check_totals(invoice: dict, purchase_order: dict) -> dict:
    inv_total = _num(invoice.get("invoice_total", 0))
    po_total = _num(purchase_order.get("po_total", 0))
    variance = round(inv_total - po_total, 4)

    if abs(variance) <= _TOLERANCE:
        return _check("invoiceops/check_totals", _CHK_TOTALS, "pass",
                      expected=str(po_total),
                      actual=str(inv_total),
                      message=f"Invoice total {inv_total} matches PO total {po_total}.",
                      details={"invoice_total": inv_total, "po_total": po_total, "variance": variance})

    return _check("invoiceops/check_totals", _CHK_TOTALS, "fail",
                  expected=str(po_total),
                  actual=str(inv_total),
                  message=(
                      f"Invoice total {inv_total} does not match PO total {po_total} "
                      f"(variance {variance}, tolerance {_TOLERANCE})."
                  ),
                  details={"invoice_total": inv_total, "po_total": po_total, "variance": variance})


def invoiceops_check_tax(invoice: dict) -> dict:
    subtotal = _num(invoice.get("subtotal", 0))
    tax_total = _num(invoice.get("tax_total", 0))
    inv_total = _num(invoice.get("invoice_total", 0))
    expected_total = round(subtotal + tax_total, 4)
    variance = round(inv_total - expected_total, 4)

    if tax_total < 0:
        return _check("invoiceops/check_tax", _CHK_TAX, "fail",
                      expected="tax_total >= 0",
                      actual=str(tax_total),
                      message=f"Tax total {tax_total} is negative.",
                      details={"subtotal": subtotal, "tax_total": tax_total, "invoice_total": inv_total})

    if abs(variance) > _TOLERANCE:
        return _check("invoiceops/check_tax", _CHK_TAX, "fail",
                      expected=str(expected_total),
                      actual=str(inv_total),
                      message=(
                          f"Invoice total {inv_total} does not equal subtotal + tax_total "
                          f"({expected_total}) — variance {variance}."
                      ),
                      details={"subtotal": subtotal, "tax_total": tax_total, "expected_total": expected_total,
                               "invoice_total": inv_total, "variance": variance})

    if tax_total == 0.0:
        return _check("invoiceops/check_tax", _CHK_TAX, "warn",
                      expected="tax_total > 0",
                      actual="0.0",
                      message="Tax total is zero; verify that no tax applies to this invoice.",
                      details={"subtotal": subtotal, "tax_total": tax_total, "invoice_total": inv_total})

    return _check("invoiceops/check_tax", _CHK_TAX, "pass",
                  expected=str(expected_total),
                  actual=str(inv_total),
                  message=f"Invoice total {inv_total} equals subtotal + tax_total ({expected_total}).",
                  details={"subtotal": subtotal, "tax_total": tax_total, "invoice_total": inv_total})


def invoiceops_match_three_way(
    invoice: dict,
    purchase_order: dict,
    goods_receipt: dict,
    invoice_register: list[dict] | None = None,
) -> dict:
    invoice = dict(invoice or {})
    purchase_order = dict(purchase_order or {})
    goods_receipt = dict(goods_receipt or {})

    # Run all checks
    dup_check = invoiceops_check_duplicate_invoice(invoice, invoice_register or [])
    po_check = _check_po_status(invoice, purchase_order)
    receipt_check = _check_receipt_status(invoice, goods_receipt)
    supplier_check = _check_supplier(invoice, purchase_order)
    totals_check = invoiceops_check_totals(invoice, purchase_order)
    tax_check = invoiceops_check_tax(invoice)
    qty_checks = _check_quantities(invoice, goods_receipt)

    all_checks = [dup_check, po_check, receipt_check, supplier_check, totals_check, tax_check] + qty_checks

    match_status = _determine_match_status(all_checks)
    ledger_posting_allowed = match_status == "matched"
    prepared_write_allowed = match_status in {"matched", "exception"}

    check_items = [_to_check_item(c) for c in all_checks]
    exceptions = _build_exceptions(all_checks, invoice)

    invoice_number = invoice.get("invoice_number", "UNKNOWN")
    po_number = invoice.get("po_number", "UNKNOWN")

    match_result: dict[str, Any] = {
        "match_id": f"MATCH-{invoice_number}-{po_number}",
        "invoice_id": invoice.get("invoice_id", ""),
        "invoice_number": invoice_number,
        "supplier_id": invoice.get("supplier_id", ""),
        "po_number": po_number,
        "match_status": match_status,
        "checks": check_items,
        "exceptions": exceptions,
        "ledger_posting_allowed": ledger_posting_allowed,
        "prepared_write_allowed": prepared_write_allowed,
    }

    evidence = build_tool_evidence(
        tool="invoiceops/match_three_way",
        mode="dry_run",
        source="builtin",
        operation="validation",
        input_refs=[invoice.get("invoice_id", ""), po_number],
        output_ref=_MATCH_RESULT_TYPE,
        extra={
            "match_status": match_status,
            "check_count": len(all_checks),
            "exception_count": len(exceptions),
        },
    )

    return {
        "ok": True,
        "type": _MATCH_RESULT_TYPE,
        "data": {"match_result": match_result},
        "evidence": evidence,
        "error": "",
        "metadata": {"match_status": match_status},
    }


# ---------------------------------------------------------------------------
# Internal check helpers (used only inside match_three_way)
# ---------------------------------------------------------------------------

def _check_po_status(invoice: dict, purchase_order: dict) -> dict:
    if not purchase_order:
        return _check("invoiceops/match_three_way", _CHK_PO, "fail",
                      expected=invoice.get("po_number", ""),
                      actual="not provided",
                      message=f"No purchase order provided for PO {invoice.get('po_number', '')!r}.",
                      details={})
    status = str(purchase_order.get("status", "")).strip()
    po_number = str(purchase_order.get("po_number", "")).strip()
    if status in _BLOCKING_PO_STATUSES:
        return _check("invoiceops/match_three_way", _CHK_PO, "fail",
                      expected="open or part_received",
                      actual=status,
                      message=f"PO {po_number!r} has status {status!r} and cannot be matched.",
                      details={"purchase_order": purchase_order})
    return _check("invoiceops/match_three_way", _CHK_PO, "pass",
                  expected="open or part_received",
                  actual=status,
                  message=f"PO {po_number!r} has status {status!r}.",
                  details={})


def _check_receipt_status(invoice: dict, goods_receipt: dict) -> dict:
    po_number = str(invoice.get("po_number", "")).strip()
    if not goods_receipt:
        return _check("invoiceops/match_three_way", _CHK_RECEIPT, "fail",
                      expected=f"receipt for po={po_number!r}",
                      actual="not provided",
                      message=f"No goods receipt provided for PO {po_number!r}.",
                      details={})
    status = str(goods_receipt.get("status", "")).strip()
    rid = str(goods_receipt.get("receipt_id", ""))
    if status == "cancelled":
        return _check("invoiceops/match_three_way", _CHK_RECEIPT, "fail",
                      expected="received or partial",
                      actual="cancelled",
                      message=f"Receipt {rid!r} for PO {po_number!r} is cancelled.",
                      details={})
    if status == "partial":
        return _check("invoiceops/match_three_way", _CHK_RECEIPT, "warn",
                      expected="received",
                      actual="partial",
                      message=f"Receipt {rid!r} for PO {po_number!r} is partial.",
                      details={})
    return _check("invoiceops/match_three_way", _CHK_RECEIPT, "pass",
                  expected="received",
                  actual=rid,
                  message=f"Receipt {rid!r} for PO {po_number!r} is received.",
                  details={})


def _check_supplier(invoice: dict, purchase_order: dict) -> dict:
    inv_sup = str(invoice.get("supplier_id", "")).strip()
    po_sup = str(purchase_order.get("supplier_id", "")).strip() if purchase_order else ""
    if inv_sup == _UNKNOWN_SUPPLIER:
        return _check("invoiceops/match_three_way", _CHK_SUPPLIER, "warn",
                      expected="known supplier_id",
                      actual=_UNKNOWN_SUPPLIER,
                      message="Invoice supplier is UNKNOWN_SUPPLIER; supplier lookup was not performed.",
                      details={"invoice_supplier_id": inv_sup, "po_supplier_id": po_sup})
    if not purchase_order:
        return _check("invoiceops/match_three_way", _CHK_SUPPLIER, "not_applicable",
                      expected=inv_sup,
                      actual="no purchase order",
                      message="Supplier check skipped: no purchase order available.",
                      details={})
    if inv_sup != po_sup:
        return _check("invoiceops/match_three_way", _CHK_SUPPLIER, "fail",
                      expected=po_sup,
                      actual=inv_sup,
                      message=f"Invoice supplier {inv_sup!r} does not match PO supplier {po_sup!r}.",
                      details={"invoice_supplier_id": inv_sup, "po_supplier_id": po_sup})
    return _check("invoiceops/match_three_way", _CHK_SUPPLIER, "pass",
                  expected=po_sup,
                  actual=inv_sup,
                  message=f"Invoice supplier {inv_sup!r} matches PO supplier.",
                  details={})


def _check_quantities(invoice: dict, goods_receipt: dict) -> list[dict]:
    invoice_lines = invoice.get("line_items", [])
    receipt_lines = (goods_receipt or {}).get("line_items", [])

    received_by_sku: dict[str, float] = {}
    for rl in receipt_lines:
        sku = str(rl.get("sku", "")).strip()
        if sku:
            received_by_sku[sku] = received_by_sku.get(sku, 0.0) + _num(rl.get("received_quantity", 0))

    checks: list[dict] = []
    for i, il in enumerate(invoice_lines):
        sku = str(il.get("sku", "")).strip()
        inv_qty = _num(il.get("quantity", 0))
        check_id = f"QTY_CHECK_{sku or i + 1}"

        if not sku:
            checks.append(_check("invoiceops/match_three_way", check_id, "warn",
                                 expected="sku present",
                                 actual="no sku",
                                 message=f"Invoice line {i + 1} has no SKU; cannot match to receipt.",
                                 details={"line_no": il.get("line_no", i + 1)}))
            continue

        if sku not in received_by_sku:
            checks.append(_check("invoiceops/match_three_way", check_id, "warn",
                                 expected=f"sku={sku!r} in receipt",
                                 actual="not found in receipt",
                                 message=f"SKU {sku!r} not found in goods receipt; cannot verify quantity.",
                                 details={"sku": sku, "invoice_qty": inv_qty}))
            continue

        recv_qty = received_by_sku[sku]
        if inv_qty > recv_qty + _TOLERANCE:
            checks.append(_check("invoiceops/match_three_way", check_id, "fail",
                                 expected=f"invoice_qty <= received_qty={recv_qty}",
                                 actual=str(inv_qty),
                                 message=(
                                     f"Invoice quantity {inv_qty} for SKU {sku!r} "
                                     f"exceeds received quantity {recv_qty}."
                                 ),
                                 details={"sku": sku, "invoice_qty": inv_qty, "received_qty": recv_qty}))
        else:
            checks.append(_check("invoiceops/match_three_way", check_id, "pass",
                                 expected=f"invoice_qty <= received_qty={recv_qty}",
                                 actual=str(inv_qty),
                                 message=f"Quantity {inv_qty} for SKU {sku!r} is within received {recv_qty}.",
                                 details={"sku": sku, "invoice_qty": inv_qty, "received_qty": recv_qty}))

    return checks


# ---------------------------------------------------------------------------
# Match status and exception builders
# ---------------------------------------------------------------------------

def _determine_match_status(all_checks: list[dict]) -> str:
    has_warn_or_fail = False
    for c in all_checks:
        status = c["data"]["status"]
        check_id: str = c["data"]["check_id"]
        if status == "fail":
            is_blocking = (
                check_id in _BLOCKING_CHECK_IDS
                or check_id.startswith("QTY_CHECK_")
            )
            if is_blocking:
                return "blocked"
            has_warn_or_fail = True
        elif status == "warn":
            has_warn_or_fail = True
    return "exception" if has_warn_or_fail else "matched"


def _build_exceptions(all_checks: list[dict], invoice: dict) -> list[dict]:
    exceptions: list[dict] = []
    invoice_id = invoice.get("invoice_id", "")
    po_number = invoice.get("po_number", "")

    for c in all_checks:
        data = c["data"]
        status = data["status"]
        if status not in {"fail", "warn"}:
            continue

        check_id: str = data["check_id"]
        prefix = check_id.split("_CHECK")[0] + "_CHECK" if "_CHECK_" in check_id else check_id
        exc_type = _EXCEPTION_TYPE_MAP.get(prefix, "bad_invoice_input")
        blocking = status == "fail" and (check_id in _BLOCKING_CHECK_IDS or check_id.startswith("QTY_CHECK_"))

        severity: str
        if blocking:
            severity = "blocker"
        elif status == "fail":
            severity = "high"
        else:
            severity = "medium" if check_id == _CHK_DUP else "low"

        exceptions.append({
            "exception_id": f"EXC-{check_id}",
            "exception_type": exc_type,
            "severity": severity,
            "invoice_id": invoice_id,
            "po_number": po_number,
            "message": data["message"],
            "recommended_action": _recommended_action(exc_type),
            "blocking": blocking,
        })

    return exceptions


def _recommended_action(exc_type: str) -> str:
    return {
        "duplicate_invoice": "Verify this is not a resubmission; reject if confirmed duplicate.",
        "missing_po": "Obtain a valid purchase order before processing.",
        "missing_receipt": "Confirm goods have been received before approving payment.",
        "supplier_mismatch": "Verify supplier details on invoice and PO; contact supplier if needed.",
        "amount_mismatch": "Request corrected invoice or updated PO to reconcile totals.",
        "tax_mismatch": "Verify tax calculation and correct invoice or VAT registration.",
        "quantity_mismatch": "Reject excess quantity or obtain updated goods receipt.",
        "bad_invoice_input": "Review invoice data quality before resubmitting.",
    }.get(exc_type, "Review and resolve before posting.")


def _to_check_item(check_result: dict) -> dict:
    d = check_result["data"]
    return {
        "check_id": d["check_id"],
        "status": d["status"],
        "expected": d["expected"],
        "actual": d["actual"],
        "message": d["message"],
    }


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _check(
    tool_key: str,
    check_id: str,
    status: str,
    expected: str,
    actual: str,
    message: str,
    details: dict | None = None,
) -> dict:
    evidence = build_tool_evidence(
        tool=tool_key,
        mode="dry_run",
        source="builtin",
        operation="validation",
        input_refs=[],
        output_ref=_MATCH_CHECK_TYPE,
    )
    return {
        "ok": True,
        "type": _MATCH_CHECK_TYPE,
        "data": {
            "check_id": check_id,
            "status": status,
            "expected": str(expected),
            "actual": str(actual),
            "message": message,
            "details": details or {},
        },
        "evidence": evidence,
        "error": "",
        "metadata": {},
    }


def _num(value: Any) -> float:
    try:
        return float(value) if not isinstance(value, bool) else 0.0
    except (TypeError, ValueError):
        return 0.0
