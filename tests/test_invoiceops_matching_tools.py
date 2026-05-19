from __future__ import annotations

import runtime.invoiceops_matching_tools as _mod
from runtime.invoiceops_matching_tools import (
    invoiceops_check_duplicate_invoice,
    invoiceops_check_tax,
    invoiceops_check_totals,
    invoiceops_lookup_goods_receipt,
    invoiceops_lookup_purchase_order,
    invoiceops_match_three_way,
)
from runtime.invoiceops_contracts import validate_match_result_shape

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_LINE_ITEMS_INV = [
    {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "quantity": 10.0, "unit_price": 150.0, "tax_amount": 0.0, "line_total": 1500.0},
    {"line_no": 2, "sku": "SKU-WIDGET-B", "description": "Widget B", "quantity": 5.0,  "unit_price": 200.0, "tax_amount": 0.0, "line_total": 1000.0},
    {"line_no": 3, "sku": "SKU-CABLE-01", "description": "Cable 1m",  "quantity": 20.0, "unit_price":  25.0, "tax_amount": 0.0, "line_total":  500.0},
]

_LINE_ITEMS_PO = [
    {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "ordered_quantity": 10.0, "unit_price": 150.0, "line_total": 1500.0},
    {"line_no": 2, "sku": "SKU-WIDGET-B", "description": "Widget B", "ordered_quantity":  5.0, "unit_price": 200.0, "line_total": 1000.0},
    {"line_no": 3, "sku": "SKU-CABLE-01", "description": "Cable 1m",  "ordered_quantity": 20.0, "unit_price":  25.0, "line_total":  500.0},
]

_LINE_ITEMS_RECEIPT = [
    {"line_no": 1, "sku": "SKU-WIDGET-A", "description": "Widget A", "received_quantity": 10.0},
    {"line_no": 2, "sku": "SKU-WIDGET-B", "description": "Widget B", "received_quantity":  5.0},
    {"line_no": 3, "sku": "SKU-CABLE-01", "description": "Cable 1m",  "received_quantity": 20.0},
]

_SAMPLE_INVOICE = {
    "invoice_id": "INV-INV-2024-001",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Supplies (Pty) Ltd",
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15",
    "po_number": "PO-2024-042",
    "currency": "ZAR",
    "subtotal": 3000.0,
    "tax_total": 450.0,
    "invoice_total": 3450.0,
    "line_items": _LINE_ITEMS_INV,
}

_SAMPLE_PO = {
    "po_number": "PO-2024-042",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Supplies (Pty) Ltd",
    "status": "open",
    "currency": "ZAR",
    "po_total": 3450.0,
    "line_items": _LINE_ITEMS_PO,
}

_SAMPLE_RECEIPT = {
    "receipt_id": "GRN-001",
    "po_number": "PO-2024-042",
    "supplier_id": "SUP-001",
    "receipt_date": "2024-01-10",
    "status": "received",
    "line_items": _LINE_ITEMS_RECEIPT,
}

_EMPTY_REGISTER: list[dict] = []

_REGISTER_WITH_DUP = [
    {**_SAMPLE_INVOICE, "invoice_id": "INV-INV-2024-001-OLD"},
]


# ---------------------------------------------------------------------------
# check_duplicate_invoice — pass
# ---------------------------------------------------------------------------

def test_dup_check_pass_empty_register() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _EMPTY_REGISTER)
    assert r["ok"] is True


def test_dup_check_pass_status() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _EMPTY_REGISTER)
    assert r["data"]["status"] == "pass"


def test_dup_check_pass_check_id() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _EMPTY_REGISTER)
    assert r["data"]["check_id"] == "DUP_CHECK"


def test_dup_check_pass_different_supplier_not_flagged() -> None:
    register = [{**_SAMPLE_INVOICE, "supplier_id": "SUP-999", "invoice_id": "INV-OLD"}]
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, register)
    assert r["data"]["status"] == "pass"


# ---------------------------------------------------------------------------
# check_duplicate_invoice — fail (duplicate)
# ---------------------------------------------------------------------------

def test_dup_check_fail_same_supplier_and_number() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _REGISTER_WITH_DUP)
    assert r["data"]["status"] == "fail"


def test_dup_check_fail_check_id() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _REGISTER_WITH_DUP)
    assert r["data"]["check_id"] == "DUP_CHECK"


def test_dup_check_fail_details_has_duplicate_record() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _REGISTER_WITH_DUP)
    assert "duplicate_record" in r["data"]["details"]


# ---------------------------------------------------------------------------
# check_duplicate_invoice — warn (unknown supplier)
# ---------------------------------------------------------------------------

def test_dup_check_warn_unknown_supplier() -> None:
    inv = {**_SAMPLE_INVOICE, "supplier_id": "UNKNOWN_SUPPLIER"}
    register = [{**_SAMPLE_INVOICE, "invoice_number": "INV-2024-001", "invoice_id": "OLD"}]
    r = invoiceops_check_duplicate_invoice(inv, register)
    assert r["data"]["status"] == "warn"


# ---------------------------------------------------------------------------
# lookup_purchase_order — pass
# ---------------------------------------------------------------------------

def test_po_lookup_pass() -> None:
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [_SAMPLE_PO])
    assert r["data"]["status"] == "pass"


def test_po_lookup_pass_check_id() -> None:
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [_SAMPLE_PO])
    assert r["data"]["check_id"] == "PO_CHECK"


def test_po_lookup_pass_details_has_po() -> None:
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [_SAMPLE_PO])
    assert "purchase_order" in r["data"]["details"]


# ---------------------------------------------------------------------------
# lookup_purchase_order — missing PO
# ---------------------------------------------------------------------------

def test_po_lookup_fail_not_found() -> None:
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [])
    assert r["data"]["status"] == "fail"


def test_po_lookup_fail_no_po_number() -> None:
    inv = {**_SAMPLE_INVOICE, "po_number": ""}
    r = invoiceops_lookup_purchase_order(inv, [_SAMPLE_PO])
    assert r["data"]["status"] == "fail"


# ---------------------------------------------------------------------------
# lookup_purchase_order — cancelled PO → blocked
# ---------------------------------------------------------------------------

def test_po_lookup_fail_cancelled() -> None:
    po = {**_SAMPLE_PO, "status": "cancelled"}
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [po])
    assert r["data"]["status"] == "fail"


def test_po_lookup_fail_closed() -> None:
    po = {**_SAMPLE_PO, "status": "closed"}
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [po])
    assert r["data"]["status"] == "fail"


def test_po_lookup_pass_part_received() -> None:
    po = {**_SAMPLE_PO, "status": "part_received"}
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [po])
    assert r["data"]["status"] == "pass"


# ---------------------------------------------------------------------------
# lookup_goods_receipt — pass
# ---------------------------------------------------------------------------

def test_receipt_lookup_pass() -> None:
    r = invoiceops_lookup_goods_receipt(_SAMPLE_INVOICE, [_SAMPLE_RECEIPT])
    assert r["data"]["status"] == "pass"


def test_receipt_lookup_pass_check_id() -> None:
    r = invoiceops_lookup_goods_receipt(_SAMPLE_INVOICE, [_SAMPLE_RECEIPT])
    assert r["data"]["check_id"] == "RECEIPT_CHECK"


# ---------------------------------------------------------------------------
# lookup_goods_receipt — missing receipt
# ---------------------------------------------------------------------------

def test_receipt_lookup_fail_not_found() -> None:
    r = invoiceops_lookup_goods_receipt(_SAMPLE_INVOICE, [])
    assert r["data"]["status"] == "fail"


# ---------------------------------------------------------------------------
# lookup_goods_receipt — partial receipt → warn
# ---------------------------------------------------------------------------

def test_receipt_lookup_warn_partial() -> None:
    receipt = {**_SAMPLE_RECEIPT, "status": "partial"}
    r = invoiceops_lookup_goods_receipt(_SAMPLE_INVOICE, [receipt])
    assert r["data"]["status"] == "warn"


# ---------------------------------------------------------------------------
# check_totals
# ---------------------------------------------------------------------------

def test_totals_check_pass() -> None:
    r = invoiceops_check_totals(_SAMPLE_INVOICE, _SAMPLE_PO)
    assert r["data"]["status"] == "pass"


def test_totals_check_fail_mismatch() -> None:
    po = {**_SAMPLE_PO, "po_total": 3000.0}
    r = invoiceops_check_totals(_SAMPLE_INVOICE, po)
    assert r["data"]["status"] == "fail"


def test_totals_check_within_tolerance_passes() -> None:
    po = {**_SAMPLE_PO, "po_total": 3450.005}
    r = invoiceops_check_totals(_SAMPLE_INVOICE, po)
    assert r["data"]["status"] == "pass"


def test_totals_check_details_has_variance() -> None:
    po = {**_SAMPLE_PO, "po_total": 3000.0}
    r = invoiceops_check_totals(_SAMPLE_INVOICE, po)
    assert "variance" in r["data"]["details"]


# ---------------------------------------------------------------------------
# check_tax
# ---------------------------------------------------------------------------

def test_tax_check_pass() -> None:
    r = invoiceops_check_tax(_SAMPLE_INVOICE)
    assert r["data"]["status"] == "pass"


def test_tax_check_fail_mismatch() -> None:
    inv = {**_SAMPLE_INVOICE, "invoice_total": 3600.0}
    r = invoiceops_check_tax(inv)
    assert r["data"]["status"] == "fail"


def test_tax_check_fail_negative_tax() -> None:
    inv = {**_SAMPLE_INVOICE, "tax_total": -50.0}
    r = invoiceops_check_tax(inv)
    assert r["data"]["status"] == "fail"


def test_tax_check_warn_zero_tax() -> None:
    inv = {**_SAMPLE_INVOICE, "tax_total": 0.0, "invoice_total": 3000.0, "subtotal": 3000.0}
    r = invoiceops_check_tax(inv)
    assert r["data"]["status"] == "warn"


def test_tax_check_id() -> None:
    r = invoiceops_check_tax(_SAMPLE_INVOICE)
    assert r["data"]["check_id"] == "TAX_CHECK"


# ---------------------------------------------------------------------------
# match_three_way — happy path
# ---------------------------------------------------------------------------

def test_three_way_happy_path_matched() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "matched"


def test_three_way_happy_path_ok() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["ok"] is True


def test_three_way_happy_path_ledger_posting_allowed() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["ledger_posting_allowed"] is True


def test_three_way_happy_path_prepared_write_allowed() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["prepared_write_allowed"] is True


def test_three_way_happy_path_no_exceptions() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["exceptions"] == []


def test_three_way_happy_path_all_checks_pass() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    checks = r["data"]["match_result"]["checks"]
    statuses = {c["status"] for c in checks}
    assert statuses == {"pass"}


# ---------------------------------------------------------------------------
# match_three_way — duplicate invoice → blocked
# ---------------------------------------------------------------------------

def test_three_way_duplicate_invoice_blocked() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _REGISTER_WITH_DUP)
    assert r["data"]["match_result"]["match_status"] == "blocked"


def test_three_way_duplicate_no_ledger_posting() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _REGISTER_WITH_DUP)
    assert r["data"]["match_result"]["ledger_posting_allowed"] is False


def test_three_way_duplicate_has_exception() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _REGISTER_WITH_DUP)
    excs = r["data"]["match_result"]["exceptions"]
    assert any(e["exception_type"] == "duplicate_invoice" for e in excs)


# ---------------------------------------------------------------------------
# match_three_way — missing PO → blocked
# ---------------------------------------------------------------------------

def test_three_way_missing_po_blocked() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, {}, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "blocked"


# ---------------------------------------------------------------------------
# match_three_way — cancelled PO → blocked
# ---------------------------------------------------------------------------

def test_three_way_cancelled_po_blocked() -> None:
    po = {**_SAMPLE_PO, "status": "cancelled"}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, po, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "blocked"


# ---------------------------------------------------------------------------
# match_three_way — missing receipt → blocked
# ---------------------------------------------------------------------------

def test_three_way_missing_receipt_blocked() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, {}, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "blocked"


# ---------------------------------------------------------------------------
# match_three_way — partial receipt → exception (warning)
# ---------------------------------------------------------------------------

def test_three_way_partial_receipt_exception() -> None:
    receipt = {**_SAMPLE_RECEIPT, "status": "partial"}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, receipt, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "exception"


def test_three_way_partial_receipt_prepared_write_allowed() -> None:
    receipt = {**_SAMPLE_RECEIPT, "status": "partial"}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, receipt, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["prepared_write_allowed"] is True


def test_three_way_partial_receipt_no_ledger_posting() -> None:
    receipt = {**_SAMPLE_RECEIPT, "status": "partial"}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, receipt, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["ledger_posting_allowed"] is False


# ---------------------------------------------------------------------------
# match_three_way — supplier mismatch → blocked
# ---------------------------------------------------------------------------

def test_three_way_supplier_mismatch_blocked() -> None:
    po = {**_SAMPLE_PO, "supplier_id": "SUP-WRONG"}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, po, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "blocked"


def test_three_way_supplier_mismatch_exception_type() -> None:
    po = {**_SAMPLE_PO, "supplier_id": "SUP-WRONG"}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, po, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    excs = r["data"]["match_result"]["exceptions"]
    assert any(e["exception_type"] == "supplier_mismatch" for e in excs)


# ---------------------------------------------------------------------------
# match_three_way — invoice total mismatch → exception (TOTALS_CHECK fail)
# ---------------------------------------------------------------------------

def test_three_way_total_mismatch_exception() -> None:
    po = {**_SAMPLE_PO, "po_total": 3000.0}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, po, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "exception"


def test_three_way_total_mismatch_exception_type() -> None:
    po = {**_SAMPLE_PO, "po_total": 3000.0}
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, po, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    excs = r["data"]["match_result"]["exceptions"]
    assert any(e["exception_type"] == "amount_mismatch" for e in excs)


# ---------------------------------------------------------------------------
# match_three_way — tax mismatch → exception (TAX_CHECK fail, non-blocking)
# ---------------------------------------------------------------------------

def test_three_way_tax_mismatch_exception() -> None:
    inv = {**_SAMPLE_INVOICE, "invoice_total": 3600.0}
    r = invoiceops_match_three_way(inv, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] in {"exception", "blocked"}


def test_three_way_tax_mismatch_only_exception_not_blocked() -> None:
    # TAX_CHECK is non-blocking — only a totals mismatch would also block here.
    # invoice_total matches PO (3450) but subtotal+tax_total=2900+450=3350 ≠ 3450.
    inv = {**_SAMPLE_INVOICE, "subtotal": 2900.0, "tax_total": 450.0, "invoice_total": 3450.0}
    r = invoiceops_match_three_way(inv, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "exception"


def test_three_way_tax_mismatch_exception_type() -> None:
    inv = {**_SAMPLE_INVOICE, "subtotal": 2900.0, "tax_total": 450.0, "invoice_total": 3450.0}
    r = invoiceops_match_three_way(inv, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    excs = r["data"]["match_result"]["exceptions"]
    assert any(e["exception_type"] == "tax_mismatch" for e in excs)


# ---------------------------------------------------------------------------
# match_three_way — quantity exceeds receipt → blocked
# ---------------------------------------------------------------------------

def test_three_way_excess_quantity_blocked() -> None:
    receipt = {
        **_SAMPLE_RECEIPT,
        "line_items": [
            {"line_no": 1, "sku": "SKU-WIDGET-A", "received_quantity": 5.0},   # invoice has 10
            {"line_no": 2, "sku": "SKU-WIDGET-B", "received_quantity": 5.0},
            {"line_no": 3, "sku": "SKU-CABLE-01",  "received_quantity": 20.0},
        ],
    }
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, receipt, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "blocked"


def test_three_way_excess_quantity_exception_type() -> None:
    receipt = {
        **_SAMPLE_RECEIPT,
        "line_items": [
            {"line_no": 1, "sku": "SKU-WIDGET-A", "received_quantity": 5.0},
            {"line_no": 2, "sku": "SKU-WIDGET-B", "received_quantity": 5.0},
            {"line_no": 3, "sku": "SKU-CABLE-01",  "received_quantity": 20.0},
        ],
    }
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, receipt, _EMPTY_REGISTER)
    excs = r["data"]["match_result"]["exceptions"]
    assert any(e["exception_type"] == "quantity_mismatch" for e in excs)


# ---------------------------------------------------------------------------
# match_three_way — unknown supplier → exception (warning)
# ---------------------------------------------------------------------------

def test_three_way_unknown_supplier_exception() -> None:
    inv = {**_SAMPLE_INVOICE, "supplier_id": "UNKNOWN_SUPPLIER"}
    r = invoiceops_match_three_way(inv, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["match_status"] == "exception"


def test_three_way_unknown_supplier_no_ledger_posting() -> None:
    inv = {**_SAMPLE_INVOICE, "supplier_id": "UNKNOWN_SUPPLIER"}
    r = invoiceops_match_three_way(inv, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["data"]["match_result"]["ledger_posting_allowed"] is False


# ---------------------------------------------------------------------------
# match_result shape — canonical Spec 116
# ---------------------------------------------------------------------------

def test_three_way_result_passes_match_result_shape_validation() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    v = validate_match_result_shape(r["data"]["match_result"])
    assert v["ok"] is True, f"match_result shape validation failed: {v['errors']}"


def test_three_way_match_id_format() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    match_id = r["data"]["match_result"]["match_id"]
    assert "INV-2024-001" in match_id
    assert "PO-2024-042" in match_id


def test_three_way_result_has_all_match_result_keys() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    mr = r["data"]["match_result"]
    for key in ("match_id", "invoice_id", "invoice_number", "supplier_id", "po_number",
                "match_status", "checks", "exceptions", "ledger_posting_allowed", "prepared_write_allowed"):
        assert key in mr, f"match_result missing key {key!r}"


def test_three_way_checks_list_has_check_id_and_status() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    for c in r["data"]["match_result"]["checks"]:
        assert "check_id" in c
        assert "status" in c


# ---------------------------------------------------------------------------
# ToolResult contract — all outputs are ToolResult-compatible
# ---------------------------------------------------------------------------

def test_dup_check_toolresult_keys() -> None:
    r = invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _EMPTY_REGISTER)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_po_lookup_toolresult_keys() -> None:
    r = invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [_SAMPLE_PO])
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_receipt_lookup_toolresult_keys() -> None:
    r = invoiceops_lookup_goods_receipt(_SAMPLE_INVOICE, [_SAMPLE_RECEIPT])
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_totals_check_toolresult_keys() -> None:
    r = invoiceops_check_totals(_SAMPLE_INVOICE, _SAMPLE_PO)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_tax_check_toolresult_keys() -> None:
    r = invoiceops_check_tax(_SAMPLE_INVOICE)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_three_way_toolresult_keys() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r


def test_check_tools_return_correct_type() -> None:
    for r in (
        invoiceops_check_duplicate_invoice(_SAMPLE_INVOICE, _EMPTY_REGISTER),
        invoiceops_lookup_purchase_order(_SAMPLE_INVOICE, [_SAMPLE_PO]),
        invoiceops_lookup_goods_receipt(_SAMPLE_INVOICE, [_SAMPLE_RECEIPT]),
        invoiceops_check_totals(_SAMPLE_INVOICE, _SAMPLE_PO),
        invoiceops_check_tax(_SAMPLE_INVOICE),
    ):
        assert r["type"] == "invoiceops_match_check"


def test_three_way_returns_correct_type() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert r["type"] == "invoiceops_match_result"


def test_three_way_evidence_has_expected_keys() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    for key in ("tool", "mode", "operation"):
        assert key in r["evidence"]


def test_three_way_metadata_has_match_status() -> None:
    r = invoiceops_match_three_way(_SAMPLE_INVOICE, _SAMPLE_PO, _SAMPLE_RECEIPT, _EMPTY_REGISTER)
    assert "match_status" in r["metadata"]


# ---------------------------------------------------------------------------
# No write functions in module
# ---------------------------------------------------------------------------

def test_no_write_functions_in_matching_module() -> None:
    write_fns = [
        name for name in dir(_mod)
        if "write" in name.lower() and callable(getattr(_mod, name))
    ]
    assert write_fns == []
