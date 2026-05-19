from __future__ import annotations

import json

from runtime.llm_tools import validate_llm_output
from runtime.supplier_invoice_tools import (
    draft_supplier_invoice_exception_summary,
    po_read,
    receipt_read_by_po,
    supplier_invoice_build_exception_report,
    supplier_invoice_check_duplicate,
    supplier_invoice_execute_ledger_write,
    supplier_invoice_match_three_way,
    supplier_invoice_prepare_ledger_write,
    supplier_invoice_prepare_match_run_write,
    supplier_invoice_read,
)


def test_supplier_invoice_read_returns_invoice():
    result = supplier_invoice_read("SIN-4001", runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["type"] == "supplier_invoice_result"
    assert result["data"]["invoice_ref"] == "SIN-4001"
    assert result["data"]["po_ref"] == "PO-2001"


def test_supplier_invoice_read_missing_invoice_fails():
    result = supplier_invoice_read("SIN-9999", runtime_root="runtime_data")
    assert result["ok"] is False
    assert result["error"]


def test_po_read_returns_po():
    result = po_read("PO-2001", runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["po_ref"] == "PO-2001"


def test_receipt_read_by_po_returns_receipts():
    result = receipt_read_by_po("PO-2001", runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["receipt_count"] == 1
    assert result["data"]["receipt_refs"] == ["GRN-3001"]


def test_duplicate_invoice_detected():
    result = supplier_invoice_check_duplicate("SUP-1001", "INV-7785", invoice_ref="SIN-4005", runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["duplicate"] is True


def test_duplicate_invoice_ignores_current_invoice_ref():
    result = supplier_invoice_check_duplicate("SUP-1001", "INV-7785", invoice_ref="SIN-4005", runtime_root="runtime_data")
    assert result["data"]["duplicates"]
    assert all(item.get("invoice_ref") != "SIN-4005" for item in result["data"]["duplicates"])


def test_three_way_match_happy_path_matches():
    invoice = supplier_invoice_read("SIN-4001", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2001", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2001", runtime_root="runtime_data")["data"]
    result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["match_status"] == "matched"
    assert result["data"]["exceptions"] == []


def test_three_way_match_price_mismatch_exception():
    invoice = supplier_invoice_read("SIN-4002", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2002", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2002", runtime_root="runtime_data")["data"]
    result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")
    assert result["data"]["match_status"] == "exception"
    assert any(exc["code"] == "PRICE_MISMATCH" for exc in result["data"]["exceptions"])


def test_three_way_match_quantity_exceeds_receipt_exception():
    invoice = supplier_invoice_read("SIN-4003", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2003", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2003", runtime_root="runtime_data")["data"]
    result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")
    assert result["data"]["match_status"] == "exception"
    assert any(exc["code"] == "RECEIPT_MISMATCH" for exc in result["data"]["exceptions"])


def test_three_way_match_missing_receipt_exception():
    invoice = supplier_invoice_read("SIN-4004", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2004", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2004", runtime_root="runtime_data")["data"]
    result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")
    assert result["data"]["match_status"] == "exception"
    assert any(exc["code"] == "RECEIPT_NOT_FOUND" for exc in result["data"]["exceptions"])


def test_three_way_match_tax_total_mismatch_exception():
    invoice = supplier_invoice_read("SIN-4006", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2002", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2002", runtime_root="runtime_data")["data"]
    result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")
    assert any(exc["code"] == "TAX_MISMATCH" for exc in result["data"]["exceptions"])


def test_three_way_match_unknown_sku_exception():
    invoice = supplier_invoice_read("SIN-4999", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2005", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2005", runtime_root="runtime_data")["data"]
    result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")
    assert any(exc["code"] == "UNKNOWN_SKU" for exc in result["data"]["exceptions"])


def test_prepare_match_run_write_returns_pending_sheet_rows():
    invoice = supplier_invoice_read("SIN-4001", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2001", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2001", runtime_root="runtime_data")["data"]
    match_result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")["data"]
    result = supplier_invoice_prepare_match_run_write(match_result, runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["status"] == "PENDING_APPROVAL"
    assert result["data"]["action_type"] == "write_supplier_invoice_match_run"
    assert result["data"]["rows"]


def test_prepare_ledger_write_allowed_for_matched_invoice():
    invoice = supplier_invoice_read("SIN-4001", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2001", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2001", runtime_root="runtime_data")["data"]
    match_result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")["data"]
    result = supplier_invoice_prepare_ledger_write(invoice, match_result, runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["status"] == "PENDING_APPROVAL"
    assert result["data"]["ledger_rows"]


def test_prepare_ledger_write_blocked_for_exception_invoice():
    invoice = supplier_invoice_read("SIN-4002", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2002", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2002", runtime_root="runtime_data")["data"]
    match_result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")["data"]
    result = supplier_invoice_prepare_ledger_write(invoice, match_result, runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["not_applicable"] is True


def test_execute_ledger_write_dry_run_does_not_mutate_data():
    rows = [{"ledger_account": "accruals", "amount": 1150.0}]
    result = supplier_invoice_execute_ledger_write(rows, dry_run=True, runtime_root="runtime_data")
    assert result["ok"] is True
    assert result["data"]["dry_run"] is True


def test_execute_ledger_write_live_mode_blocked():
    result = supplier_invoice_execute_ledger_write([{"ledger_account": "accruals"}], dry_run=False, runtime_root="runtime_data")
    assert result["ok"] is False
    assert "blocked" in result["error"].lower()


def test_exception_report_contains_deterministic_exception_codes():
    invoice = supplier_invoice_read("SIN-4002", runtime_root="runtime_data")["data"]
    purchase_order = po_read("PO-2002", runtime_root="runtime_data")["data"]
    receipts = receipt_read_by_po("PO-2002", runtime_root="runtime_data")["data"]
    match_result = supplier_invoice_match_three_way(invoice, purchase_order, receipts, runtime_root="runtime_data")["data"]
    report = supplier_invoice_build_exception_report(invoice, purchase_order, receipts, match_result, runtime_root="runtime_data")
    assert report["ok"] is True
    assert report["data"]["match_status"] == "exception"
    assert report["data"]["exceptions"]


def test_llm_exception_summary_cannot_invent_facts():
    bad = validate_llm_output(
        "draft_supplier_invoice_exception_summary",
        json.dumps(
            {
                "summary": "bad",
                "risk_level": "high",
                "key_exceptions": [],
                "recommended_action": "none",
                "invented_facts": True,
            }
        ),
    )
    assert bad["ok"] is False

    good = validate_llm_output(
        "draft_supplier_invoice_exception_summary",
        json.dumps(
            {
                "summary": "good",
                "risk_level": "low",
                "key_exceptions": [],
                "recommended_action": "review",
                "invented_facts": False,
            }
        ),
    )
    assert good["ok"] is True
