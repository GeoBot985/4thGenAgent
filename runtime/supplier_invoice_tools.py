from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .company_store import read_json_table
from .taskframe import utc_now
from .tool_result_contract import build_tool_evidence


DEFAULT_RUNTIME_ROOT = "runtime_data"


def supplier_invoice_read(invoice_ref: str, runtime_root: str = DEFAULT_RUNTIME_ROOT) -> dict:
    invoice = _find_one("supplier_invoices", lambda row: _row_ref(row, "invoice_ref", "invoice_id") == _norm(invoice_ref), runtime_root)
    if not invoice:
        return _tool_result(
            "supplier_invoice_result",
            False,
            {},
            _evidence("supplier_invoice/read", runtime_root, "read", "supplier_invoices", [invoice_ref], error_code="SUPPLIER_INVOICE_NOT_FOUND"),
            "SUPPLIER_INVOICE_NOT_FOUND",
            output_ref="invoice",
        )
    lines = _find_many("supplier_invoice_lines", lambda row: _row_ref(row, "invoice_ref", "invoice_id") == _row_ref(invoice, "invoice_ref", "invoice_id"), runtime_root)
    data = _normalize_invoice(invoice, lines)
    return _tool_result(
        "supplier_invoice_result",
        True,
        data,
        _evidence("supplier_invoice/read", runtime_root, "read", "supplier_invoices", [invoice_ref], output_ref="invoice", extra={"record_count": 1, "line_count": len(lines)}),
        "",
        output_ref="invoice",
    )


def po_read(po_ref: str, runtime_root: str = DEFAULT_RUNTIME_ROOT) -> dict:
    po = _find_one("purchase_orders", lambda row: _row_ref(row, "po_ref", "po_id") == _norm(po_ref), runtime_root)
    if not po:
        return _tool_result(
            "purchase_order_result",
            True,
            {},
            _evidence(
                "po/read",
                runtime_root,
                "read",
                "purchase_orders",
                [po_ref],
                output_ref="purchase_order",
                extra={"record_count": 0},
                error_code="PURCHASE_ORDER_NOT_FOUND",
            ),
            "",
            output_ref="purchase_order",
        )
    lines = _find_many("purchase_order_lines", lambda row: _row_ref(row, "po_ref", "po_id") == _row_ref(po, "po_ref", "po_id"), runtime_root)
    data = _normalize_purchase_order(po, lines)
    return _tool_result(
        "purchase_order_result",
        True,
        data,
        _evidence("po/read", runtime_root, "read", "purchase_orders", [po_ref], output_ref="purchase_order", extra={"record_count": 1, "line_count": len(lines)}),
        "",
        output_ref="purchase_order",
    )


def receipt_read_by_po(po_ref: str, runtime_root: str = DEFAULT_RUNTIME_ROOT) -> dict:
    receipts = _find_many("goods_receipts", lambda row: _row_ref(row, "po_ref", "po_id") == _norm(po_ref), runtime_root)
    receipt_refs = [str(row.get("receipt_ref", row.get("receipt_id", ""))) for row in receipts]
    receipt_lines = _find_many("goods_receipt_lines", lambda row: _row_ref(row, "po_ref", "po_id") == _norm(po_ref), runtime_root)
    data = {
        "po_ref": _norm(po_ref),
        "receipt_refs": receipt_refs,
        "receipt_count": len(receipts),
        "lines": [_normalize_receipt_line(line) for line in receipt_lines],
        "receipts": [_normalize_receipt(receipt, receipt_lines) for receipt in receipts],
    }
    return _tool_result(
        "goods_receipt_result",
        True,
        data,
        _evidence("receipt/read_by_po", runtime_root, "read", "goods_receipts", [po_ref], output_ref="receipts", extra={"record_count": len(receipts), "line_count": len(receipt_lines)}),
        "",
        output_ref="receipts",
    )


def supplier_invoice_check_duplicate(
    supplier_id: str,
    supplier_invoice_number: str,
    invoice_ref: str = "",
    runtime_root: str = DEFAULT_RUNTIME_ROOT,
) -> dict:
    supplier_id_n = _norm(supplier_id)
    invoice_number_n = _norm(supplier_invoice_number)
    current_ref = _norm(invoice_ref)
    invoice_rows = read_json_table("supplier_invoices", runtime_root)
    run_rows = read_json_table("supplier_invoice_match_runs", runtime_root)
    duplicates: list[dict[str, Any]] = []
    for row in invoice_rows:
        if _row_ref(row, "invoice_ref", "invoice_id") == current_ref:
            continue
        if _norm(row.get("supplier_id")) == supplier_id_n and _norm(row.get("supplier_invoice_number")) == invoice_number_n:
            duplicates.append({"source": "supplier_invoices", **_strip_record(row)})
    for row in run_rows:
        if _norm(row.get("supplier_id")) == supplier_id_n and _norm(row.get("supplier_invoice_number")) == invoice_number_n:
            if current_ref and _norm(row.get("invoice_ref")) == current_ref:
                continue
            duplicates.append({"source": "supplier_invoice_match_runs", **_strip_record(row)})

    ok = len(duplicates) == 0
    data = {
        "supplier_id": supplier_id_n,
        "supplier_invoice_number": invoice_number_n,
        "invoice_ref": current_ref,
        "duplicate": not ok,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
    }
    return _tool_result(
        "supplier_invoice_duplicate_check_result",
        True,
        data,
        _evidence(
            "supplier_invoice/check_duplicate",
            runtime_root,
            "validation",
            "supplier_invoice_match_runs",
            [supplier_id_n, invoice_number_n, current_ref],
            output_ref="duplicate_check",
            extra={"record_count": len(duplicates), "duplicate": not ok},
        ),
        "",
        output_ref="duplicate_check",
    )


def supplier_invoice_match_three_way(
    invoice: dict,
    purchase_order: dict,
    receipts: dict,
    tolerance_amount: float = 1.00,
    tolerance_percent: float = 0.01,
    runtime_root: str = DEFAULT_RUNTIME_ROOT,
) -> dict:
    invoice = dict(invoice or {})
    purchase_order = dict(purchase_order or {})
    receipts = dict(receipts or {})
    tolerance_amount = float(tolerance_amount or 0.0)
    tolerance_percent = float(tolerance_percent or 0.0)

    exceptions: list[dict[str, Any]] = []
    matched_lines: list[dict[str, Any]] = []

    invoice_ref = _row_ref(invoice, "invoice_ref", "invoice_id")
    po_ref = _row_ref(purchase_order, "po_ref", "po_id") or _norm(invoice.get("po_ref"))
    supplier_match = _norm(invoice.get("supplier_id")) == _norm(purchase_order.get("supplier_id"))
    if not purchase_order:
        exceptions.append(_exception("PO_NOT_FOUND", "high", "", "Purchase order is missing.", expected={"po_ref": po_ref}, actual={"invoice_po_ref": invoice.get("po_ref", "")}))
    elif not supplier_match:
        exceptions.append(_exception("SUPPLIER_MISMATCH", "high", "", "Invoice supplier does not match purchase order supplier.", expected={"supplier_id": purchase_order.get("supplier_id", "")}, actual={"supplier_id": invoice.get("supplier_id", "")}))

    receipt_refs = _receipt_refs(receipts)
    receipt_lines = _receipt_lines(receipts)
    if not receipt_refs:
        exceptions.append(_exception("RECEIPT_NOT_FOUND", "high", "", "No goods receipt was found for the purchase order.", expected={"po_ref": po_ref}, actual={"receipt_refs": []}))

    po_lines = _normalize_lines(purchase_order.get("lines", []))
    invoice_lines = _normalize_lines(invoice.get("lines", []))
    receipt_totals_by_sku = _group_receipt_quantities(receipt_lines)
    receipt_total = 0.0
    po_total = 0.0
    invoice_total = _money(invoice.get("total", invoice.get("amount", 0.0)))
    invoice_subtotal = _money(invoice.get("subtotal", 0.0))
    invoice_tax = _money(invoice.get("tax", 0.0))
    tax_rate = float(invoice.get("tax_rate", purchase_order.get("tax_rate", 0.15)) or 0.0)

    for line_index, inv_line in enumerate(invoice_lines, start=1):
        sku = _norm(inv_line.get("sku"))
        po_line = next((line for line in po_lines if _norm(line.get("sku")) == sku), None)
        if po_line is None:
            exceptions.append(_exception("UNKNOWN_SKU", "high", str(line_index), f"Invoice SKU {sku} is not on the purchase order.", expected={"skus": [line.get("sku") for line in po_lines]}, actual={"sku": sku}))
            continue
        invoice_qty = int(inv_line.get("quantity", 0) or 0)
        po_qty = int(po_line.get("quantity", 0) or 0)
        received_qty = int(receipt_totals_by_sku.get(sku, 0) or 0)
        po_unit_price = _money(po_line.get("unit_cost", po_line.get("unit_price", 0.0)))
        invoice_unit_price = _money(inv_line.get("unit_price", 0.0))
        line_total = _money(inv_line.get("line_total", invoice_qty * invoice_unit_price))
        expected_line_total = round(invoice_qty * invoice_unit_price, 2)
        receipt_line_total = round(received_qty * po_unit_price, 2)
        po_total += round(po_qty * po_unit_price, 2)
        receipt_total += receipt_line_total

        line_exceptions: list[str] = []
        if invoice_qty > po_qty:
            line_exceptions.append("QUANTITY_MISMATCH")
            exceptions.append(_exception("QUANTITY_MISMATCH", "high", str(line_index), "Invoice quantity exceeds purchase order quantity.", expected={"quantity": po_qty}, actual={"quantity": invoice_qty, "sku": sku}))
        if invoice_qty > received_qty:
            line_exceptions.append("RECEIPT_QUANTITY_MISMATCH")
            exceptions.append(_exception("RECEIPT_MISMATCH", "high", str(line_index), "Invoice quantity exceeds received quantity.", expected={"received_qty": received_qty}, actual={"invoice_qty": invoice_qty, "sku": sku}))
        if not _within_tolerance(invoice_unit_price, po_unit_price, tolerance_amount, tolerance_percent):
            line_exceptions.append("PRICE_MISMATCH")
            exceptions.append(_exception("PRICE_MISMATCH", "high", str(line_index), "Invoice unit price does not match purchase order.", expected={"unit_price": po_unit_price}, actual={"unit_price": invoice_unit_price, "sku": sku}))
        if round(line_total, 2) != round(expected_line_total, 2):
            line_exceptions.append("LINE_TOTAL_MISMATCH")
            exceptions.append(_exception("LINE_TOTAL_MISMATCH", "high", str(line_index), "Invoice line total does not equal quantity times unit price.", expected={"line_total": expected_line_total}, actual={"line_total": line_total, "sku": sku}))
        matched_lines.append(
            {
                "line_ref": str(inv_line.get("line_ref", line_index)),
                "sku": sku,
                "invoice_qty": invoice_qty,
                "ordered_qty": po_qty,
                "received_qty": received_qty,
                "invoice_unit_price": invoice_unit_price,
                "po_unit_price": po_unit_price,
                "line_total": line_total,
                "status": "matched" if not line_exceptions else "exception",
                "exceptions": list(line_exceptions),
            }
        )

    expected_tax = round(invoice_subtotal * tax_rate, 2)
    if not _within_tolerance(invoice_tax, expected_tax, tolerance_amount, tolerance_percent):
        exceptions.append(_exception("TAX_MISMATCH", "high", "", "Invoice tax does not match the expected tax.", expected={"tax": expected_tax}, actual={"tax": invoice_tax, "tax_rate": tax_rate}))
    expected_total = round(invoice_subtotal + invoice_tax, 2)
    if round(invoice_total, 2) != round(expected_total, 2):
        exceptions.append(_exception("TOTAL_MISMATCH", "high", "", "Invoice grand total does not equal subtotal plus tax.", expected={"total": expected_total}, actual={"total": invoice_total}))
    duplicate_check = supplier_invoice_check_duplicate(
        supplier_id=str(invoice.get("supplier_id", "")),
        supplier_invoice_number=str(invoice.get("supplier_invoice_number", "")),
        invoice_ref=invoice_ref,
        runtime_root=runtime_root,
    )
    duplicate_data = duplicate_check.get("data", {}) if isinstance(duplicate_check, dict) else {}
    if duplicate_data.get("duplicate"):
        exceptions.append(_exception("DUPLICATE_INVOICE", "high", "", "Supplier invoice number has already been processed.", expected={"duplicate": False}, actual={"duplicate": True, "supplier_invoice_number": invoice.get("supplier_invoice_number", "")}))

    match_status = "matched" if not exceptions else "exception"
    totals = {
        "invoice_total": round(invoice_total, 2),
        "po_total": round(po_total, 2),
        "receipt_total": round(receipt_total, 2),
        "variance": round(invoice_total - expected_total, 2),
    }
    data = {
        "match_status": match_status,
        "invoice_ref": invoice_ref,
        "po_ref": po_ref,
        "receipt_refs": receipt_refs,
        "matched_lines": matched_lines,
        "exceptions": exceptions,
        "totals": totals,
    }
    return _tool_result(
        "supplier_invoice_match_result",
        True,
        data,
        _evidence(
            "supplier_invoice/match_three_way",
            runtime_root,
            "validation",
            "supplier_invoice_match",
            [invoice_ref, po_ref] + receipt_refs,
            output_ref="match_result",
            extra={
                "exception_count": len(exceptions),
                "line_count": len(matched_lines),
                "match_status": match_status,
                "totals": totals,
            },
        ),
        "",
        output_ref="match_result",
    )


def supplier_invoice_prepare_match_run_write(
    match_result: dict,
    runtime_root: str = DEFAULT_RUNTIME_ROOT,
) -> dict:
    match_result = dict(match_result or {})
    match_status = str(match_result.get("match_status", "exception")).strip().lower()
    rows = _build_match_run_rows(match_result)
    range_name = "SupplierInvoiceMatchRuns!A:Z" if match_status == "matched" else "SupplierInvoiceMatchExceptions!A:Z"
    action_type = "write_supplier_invoice_match_run" if match_status == "matched" else "write_supplier_invoice_match_exception"
    return _tool_result(
        "supplier_invoice_match_write_prepare_result",
        True,
        {
            "action_type": action_type,
            "tool": "sheet/write_rows",
            "spreadsheet_id": "",
            "range_name": range_name,
            "rows": rows,
            "mode": "append",
            "status": "PENDING_APPROVAL",
            "match_status": match_status,
        },
        _evidence(
            "supplier_invoice/prepare_match_run_write",
            runtime_root,
            "prepare",
            "supplier_invoice_match_runs",
            [str(match_result.get("invoice_ref", ""))],
            output_ref="match_run_write",
            extra={"row_count": len(rows), "match_status": match_status, "range_name": range_name},
        ),
        "",
        output_ref="match_run_write",
    )


def supplier_invoice_prepare_ledger_write(
    invoice: dict,
    match_result: dict,
    runtime_root: str = DEFAULT_RUNTIME_ROOT,
) -> dict:
    match_result = dict(match_result or {})
    invoice = dict(invoice or {})
    if str(match_result.get("match_status", "")).lower() != "matched":
        return _tool_result(
            "supplier_invoice_ledger_write_prepare_result",
            True,
            {
                "action_type": "post_supplier_invoice_ledger_entry",
                "tool": "supplier_invoice/execute_ledger_write",
                "ledger_rows": [],
                "status": "NOT_APPLICABLE",
                "match_status": str(match_result.get("match_status", "exception")),
                "not_applicable": True,
            },
            _evidence(
                "supplier_invoice/prepare_ledger_write",
                runtime_root,
                "prepare",
                "ledger_entries",
                [str(invoice.get("invoice_ref", ""))],
                output_ref="ledger_write",
                extra={"match_status": str(match_result.get("match_status", "exception")), "ledger_rows": 0, "not_applicable": True},
            ),
            "",
            output_ref="ledger_write",
        )

    ledger_rows = _build_ledger_rows(invoice, match_result)
    return _tool_result(
        "supplier_invoice_ledger_write_prepare_result",
        True,
        {
            "action_type": "post_supplier_invoice_ledger_entry",
            "tool": "supplier_invoice/execute_ledger_write",
            "ledger_rows": ledger_rows,
            "status": "PENDING_APPROVAL",
            "match_status": "matched",
        },
        _evidence(
            "supplier_invoice/prepare_ledger_write",
            runtime_root,
            "prepare",
            "ledger_entries",
            [str(invoice.get("invoice_ref", ""))],
            output_ref="ledger_write",
            extra={"match_status": "matched", "ledger_rows": len(ledger_rows)},
        ),
        "",
        output_ref="ledger_write",
    )


def supplier_invoice_execute_ledger_write(
    ledger_rows: list[dict],
    dry_run: bool = True,
    runtime_root: str = DEFAULT_RUNTIME_ROOT,
) -> dict:
    ledger_rows = [dict(row) for row in ledger_rows if isinstance(row, dict)]
    before_rows = read_json_table("ledger_entries", runtime_root)
    if not dry_run:
        return _tool_result(
            "supplier_invoice_ledger_write_execution_result",
            False,
            {
                "dry_run": False,
                "executed": False,
                "before_rows": before_rows,
                "after_rows": before_rows,
                "ledger_rows": ledger_rows,
            },
            _evidence(
                "supplier_invoice/execute_ledger_write",
                runtime_root,
                "live",
                "ledger_entries",
                [],
                output_ref="ledger_write",
                extra={"live_blocked": True, "ledger_row_count": len(ledger_rows)},
            ),
            "LIVE_LEDGER_WRITE_BLOCKED",
            output_ref="ledger_write",
        )
    after_rows = before_rows + [dict(row) for row in ledger_rows]
    return _tool_result(
        "supplier_invoice_ledger_write_execution_result",
        True,
        {
            "dry_run": True,
            "executed": True,
            "before_rows": before_rows,
            "after_rows": after_rows,
            "ledger_rows": ledger_rows,
            "written": False,
            "preview": True,
        },
        _evidence(
            "supplier_invoice/execute_ledger_write",
            runtime_root,
            "dry_run",
            "ledger_entries",
            [],
            output_ref="ledger_write",
            extra={"before_count": len(before_rows), "after_count": len(after_rows), "ledger_row_count": len(ledger_rows)},
        ),
        "",
        output_ref="ledger_write",
    )


def supplier_invoice_build_exception_report(
    invoice: dict,
    purchase_order: dict,
    receipts: dict,
    match_result: dict,
    exception_summary: dict | None = None,
    runtime_root: str = DEFAULT_RUNTIME_ROOT,
) -> dict:
    invoice = dict(invoice or {})
    purchase_order = dict(purchase_order or {})
    receipts = dict(receipts or {})
    match_result = dict(match_result or {})
    summary = dict(exception_summary or {})
    exceptions = list(match_result.get("exceptions", [])) if isinstance(match_result.get("exceptions", []), list) else []
    report = {
        "title": "Supplier Invoice Match Exception Report",
        "invoice_ref": _row_ref(invoice, "invoice_ref", "invoice_id"),
        "po_ref": _row_ref(purchase_order, "po_ref", "po_id") or _norm(invoice.get("po_ref")),
        "supplier_id": _norm(invoice.get("supplier_id")),
        "match_status": str(match_result.get("match_status", "exception")),
        "summary": str(summary.get("summary", _default_exception_summary(match_result))),
        "exceptions": exceptions,
        "recommended_action": str(summary.get("recommended_action", _default_recommended_action(match_result))),
        "evidence_refs": [
            f"invoice:{_row_ref(invoice, 'invoice_ref', 'invoice_id')}",
            f"po:{_row_ref(purchase_order, 'po_ref', 'po_id')}",
            *[f"receipt:{ref}" for ref in _receipt_refs(receipts)],
        ],
        "match_result": match_result,
        "invoice_summary": _strip_record(invoice),
        "purchase_order_summary": _strip_record(purchase_order),
        "receipt_summary": {"receipt_refs": _receipt_refs(receipts), "receipt_count": len(_receipt_lines(receipts)), "receipts": _receipt_records(receipts)},
    }
    return _tool_result(
        "supplier_invoice_exception_report_result",
        True,
        report,
        _evidence(
            "supplier_invoice/build_exception_report",
            runtime_root,
            "report",
            "supplier_invoice_match_exceptions",
            [report["invoice_ref"], report["po_ref"]],
            output_ref="exception_report",
            extra={"exception_count": len(exceptions), "match_status": report["match_status"]},
        ),
        "",
        output_ref="exception_report",
    )


def draft_supplier_invoice_exception_summary(
    invoice: dict,
    purchase_order: dict,
    receipts: dict,
    match_result: dict,
) -> dict:
    match_result = dict(match_result or {})
    exceptions = list(match_result.get("exceptions", [])) if isinstance(match_result.get("exceptions", []), list) else []
    key_exceptions = [str(item.get("code", "")).strip() for item in exceptions if isinstance(item, dict) and str(item.get("code", "")).strip()]
    match_status = str(match_result.get("match_status", "")).strip().lower()
    summary = _default_exception_summary(match_result)
    if match_status == "matched":
        key_exceptions = []
        summary = "The invoice matches the purchase order and receipt data. No exception facts were invented."
    return {
        "ok": True,
        "type": "draft_supplier_invoice_exception_summary_result",
        "data": {
            "summary": summary,
            "risk_level": "low" if match_status == "matched" else "high",
            "key_exceptions": key_exceptions,
            "recommended_action": _default_recommended_action(match_result),
            "invented_facts": False,
        },
        "evidence": _evidence(
            "llm/draft_supplier_invoice_exception_summary",
            DEFAULT_RUNTIME_ROOT,
            "draft",
            "supplier_invoice_match_exceptions",
            [str(match_result.get("invoice_ref", "")), str(match_result.get("po_ref", ""))],
            output_ref="exception_summary",
            extra={"match_status": match_status, "key_exception_count": len(key_exceptions)},
        ),
        "error": "",
        "metadata": {
            "tool": "llm/draft_supplier_invoice_exception_summary",
            "source": "builtin",
            "mode": "draft",
            "operation": "validation",
        },
    }


def _build_match_run_rows(match_result: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = {
        "invoice_ref": match_result.get("invoice_ref", ""),
        "po_ref": match_result.get("po_ref", ""),
        "match_status": match_result.get("match_status", ""),
        "exception_count": len(match_result.get("exceptions", [])) if isinstance(match_result.get("exceptions"), list) else 0,
        "totals": deepcopy(match_result.get("totals", {})) if isinstance(match_result.get("totals"), dict) else {},
        "created_at": utc_now(),
    }
    rows.append({"table": "SupplierInvoiceMatchRuns", **base})
    for exc in match_result.get("exceptions", []) if isinstance(match_result.get("exceptions"), list) else []:
        if not isinstance(exc, dict):
            continue
        rows.append(
            {
                "table": "SupplierInvoiceMatchExceptions",
                "invoice_ref": match_result.get("invoice_ref", ""),
                "po_ref": match_result.get("po_ref", ""),
                "code": exc.get("code", ""),
                "severity": exc.get("severity", ""),
                "line_ref": exc.get("line_ref", ""),
                "message": exc.get("message", ""),
                "expected": deepcopy(exc.get("expected", {})) if isinstance(exc.get("expected"), dict) else {},
                "actual": deepcopy(exc.get("actual", {})) if isinstance(exc.get("actual"), dict) else {},
                "created_at": utc_now(),
            }
        )
    return rows


def _build_ledger_rows(invoice: dict, match_result: dict) -> list[dict[str, Any]]:
    po_ref = _row_ref(invoice, "po_ref", "po_id")
    invoice_ref = _row_ref(invoice, "invoice_ref", "invoice_id")
    total = _money(invoice.get("total", invoice.get("amount", 0.0)))
    return [
        {
            "ledger_entry_id": f"LEDGER-{invoice_ref or 'INV'}",
            "source_type": "supplier_invoice",
            "source_ref": invoice_ref,
            "supplier_invoice_number": _norm(invoice.get("supplier_invoice_number")),
            "supplier_id": _norm(invoice.get("supplier_id")),
            "po_ref": po_ref,
            "debit_account": "goods_received_not_invoiced",
            "credit_account": "accounts_payable",
            "amount": round(total, 2),
            "currency": _norm(invoice.get("currency", "ZAR")) or "ZAR",
            "status": "prepared",
            "match_status": str(match_result.get("match_status", "")),
            "posted_at": "",
        }
    ]


def _normalize_invoice(invoice: dict, lines: list[dict]) -> dict:
    invoice = _strip_record(invoice)
    invoice["invoice_ref"] = _row_ref(invoice, "invoice_ref", "invoice_id")
    invoice["po_ref"] = _row_ref(invoice, "po_ref", "po_id")
    invoice["lines"] = [_normalize_line(line) for line in lines]
    invoice["subtotal"] = round(sum(_money(line.get("line_total", 0.0)) for line in invoice["lines"]), 2)
    if "tax_rate" not in invoice:
        invoice["tax_rate"] = 0.15
    if "tax" not in invoice:
        invoice["tax"] = round(float(invoice["subtotal"]) * float(invoice.get("tax_rate", 0.15)), 2)
    if "total" not in invoice:
        invoice["total"] = round(float(invoice["subtotal"]) + float(invoice["tax"]), 2)
    return invoice


def _normalize_purchase_order(po: dict, lines: list[dict]) -> dict:
    po = _strip_record(po)
    po["po_ref"] = _row_ref(po, "po_ref", "po_id")
    po["lines"] = [_normalize_line(line) for line in lines]
    po["subtotal"] = round(sum(_money(line.get("line_total", 0.0)) for line in po["lines"]), 2)
    if "tax_rate" not in po:
        po["tax_rate"] = 0.15
    po["tax"] = round(float(po["subtotal"]) * float(po.get("tax_rate", 0.15)), 2)
    po["total"] = round(float(po["subtotal"]) + float(po.get("tax", 0.0)), 2)
    return po


def _normalize_receipt(receipt: dict, receipt_lines: list[dict]) -> dict:
    receipt = _strip_record(receipt)
    receipt["receipt_ref"] = _row_ref(receipt, "receipt_ref", "receipt_id")
    receipt["po_ref"] = _row_ref(receipt, "po_ref", "po_id")
    if receipt_lines:
        receipt["lines"] = [_normalize_receipt_line(line) for line in receipt_lines if _row_ref(line, "receipt_ref", "receipt_id") == receipt["receipt_ref"]]
    else:
        receipt["lines"] = []
    return receipt


def _normalize_line(line: dict) -> dict:
    data = _strip_record(line)
    data["line_ref"] = str(data.get("line_ref", data.get("line_id", "")) or "")
    data["sku"] = _norm(data.get("sku"))
    data["quantity"] = int(data.get("quantity", 0) or 0)
    data["unit_price"] = _money(data.get("unit_price", data.get("unit_cost", 0.0)))
    data["line_total"] = round(_money(data.get("line_total", data["quantity"] * data["unit_price"])), 2)
    return data


def _normalize_lines(lines: list[dict]) -> list[dict]:
    return [_normalize_line(line) for line in lines if isinstance(line, dict)]


def _normalize_receipt_line(line: dict) -> dict:
    data = _normalize_line(line)
    data["receipt_ref"] = _row_ref(data, "receipt_ref", "receipt_id")
    data["po_ref"] = _row_ref(data, "po_ref", "po_id")
    data["received_qty"] = int(data.get("received_qty", data.get("quantity", 0)) or 0)
    return data


def _group_receipt_quantities(receipt_lines: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for line in receipt_lines:
        if not isinstance(line, dict):
            continue
        sku = _norm(line.get("sku"))
        qty = int(line.get("received_qty", line.get("quantity", 0)) or 0)
        totals[sku] = totals.get(sku, 0) + qty
    return totals


def _receipt_refs(receipts: dict) -> list[str]:
    if not isinstance(receipts, dict):
        return []
    refs: list[str] = []
    for receipt in receipts.get("receipts", []):
        if isinstance(receipt, dict):
            ref = _row_ref(receipt, "receipt_ref", "receipt_id")
            if ref:
                refs.append(ref)
    if not refs and receipts.get("receipt_refs"):
        refs.extend([_norm(item) for item in receipts.get("receipt_refs", []) if _norm(item)])
    return refs


def _receipt_records(receipts: dict) -> list[dict]:
    if not isinstance(receipts, dict):
        return []
    result: list[dict] = []
    for receipt in receipts.get("receipts", []):
        if isinstance(receipt, dict):
            result.append(_strip_record(receipt))
    return result


def _receipt_lines(receipts: dict) -> list[dict]:
    if not isinstance(receipts, dict):
        return []
    lines = receipts.get("lines", [])
    return [dict(line) for line in lines if isinstance(line, dict)]


def _default_exception_summary(match_result: dict) -> str:
    exceptions = list(match_result.get("exceptions", [])) if isinstance(match_result.get("exceptions"), list) else []
    if not exceptions:
        return "The supplier invoice matched the purchase order and receipt data."
    codes = ", ".join(str(item.get("code", "")) for item in exceptions if isinstance(item, dict) and item.get("code"))
    return f"The invoice has {len(exceptions)} exception(s): {codes}."


def _default_recommended_action(match_result: dict) -> str:
    if str(match_result.get("match_status", "")).lower() == "matched":
        return "Approve the staged match-run and ledger writes."
    return "Review the exception report and approve only the exception write."


def _exception(code: str, severity: str, line_ref: str, message: str, *, expected: dict | None = None, actual: dict | None = None) -> dict:
    return {
        "code": code,
        "severity": severity,
        "line_ref": line_ref,
        "message": message,
        "expected": dict(expected or {}),
        "actual": dict(actual or {}),
    }


def _within_tolerance(actual: float, expected: float, tolerance_amount: float, tolerance_percent: float) -> bool:
    actual = round(float(actual or 0.0), 2)
    expected = round(float(expected or 0.0), 2)
    delta = abs(actual - expected)
    percent_threshold = abs(expected) * float(tolerance_percent or 0.0)
    return delta <= max(float(tolerance_amount or 0.0), percent_threshold)


def _find_one(table_name: str, predicate, runtime_root: str) -> dict[str, Any] | None:
    for row in read_json_table(table_name, runtime_root):
        candidate = dict(row)
        if predicate(candidate):
            return candidate
    return None


def _find_many(table_name: str, predicate, runtime_root: str) -> list[dict[str, Any]]:
    return [dict(row) for row in read_json_table(table_name, runtime_root) if predicate(dict(row))]


def _row_ref(row: dict, *fields: str) -> str:
    for field in fields:
        value = row.get(field, "")
        text = _norm(value)
        if text:
            return text
    return ""


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _money(value: Any) -> float:
    try:
        return round(float(value or 0.0), 2)
    except Exception:
        return 0.0


def _strip_record(record: dict) -> dict[str, Any]:
    return {str(key): value for key, value in dict(record or {}).items() if value is not None}


def _evidence(
    tool: str,
    runtime_root: str,
    operation: str,
    source_table: str,
    input_refs: list[str] | None = None,
    *,
    output_ref: str = "",
    extra: dict | None = None,
    error_code: str = "",
) -> dict:
    mode = "dry_run" if operation in {"prepare", "validation", "report"} else "live_read"
    evidence = build_tool_evidence(
        tool=tool,
        mode=mode,
        source="builtin",
        operation=operation,
        input_refs=input_refs or [],
        output_ref=output_ref,
        extra={
            "runtime_root": runtime_root,
            "source_table": source_table,
            **(extra or {}),
            **({"safe_error_code": error_code} if error_code else {}),
        },
    )
    return evidence


def _tool_result(result_type: str, ok: bool, data: dict, evidence: dict, error: str, *, output_ref: str = "") -> dict:
    return {
        "ok": ok,
        "type": result_type,
        "data": data,
        "evidence": evidence,
        "error": error,
        "metadata": {
            "tool": evidence.get("tool", ""),
            "mode": evidence.get("mode", ""),
            "source": evidence.get("source", ""),
            "operation": evidence.get("operation", ""),
            "output_ref": output_ref,
            "runtime_root": evidence.get("runtime_root", DEFAULT_RUNTIME_ROOT),
        },
    }
