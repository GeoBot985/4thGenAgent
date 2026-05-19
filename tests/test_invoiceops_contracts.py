from __future__ import annotations

from runtime.invoiceops_contracts import (
    validate_evidence_shape,
    validate_exception_shape,
    validate_goods_receipt_shape,
    validate_invoice_shape,
    validate_ledger_row_shape,
    validate_match_result_shape,
    validate_prepared_write_shape,
    validate_purchase_order_shape,
    validate_report_shape,
    validate_rollback_plan_shape,
    validate_supplier_shape,
)

# ---------------------------------------------------------------------------
# Minimal valid fixtures
# ---------------------------------------------------------------------------

_INVOICE_LINE = {
    "line_no": 1,
    "description": "Widget A",
    "sku": "SKU-001",
    "quantity": 2.0,
    "unit_price": 100.0,
    "tax_amount": 30.0,
    "line_total": 230.0,
}

_INVOICE = {
    "invoice_id": "INV-001",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Ltd",
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15",
    "po_number": "PO-001",
    "currency": "ZAR",
    "subtotal": 200.0,
    "tax_total": 30.0,
    "invoice_total": 230.0,
    "line_items": [_INVOICE_LINE],
}

_PO_LINE = {
    "line_no": 1,
    "sku": "SKU-001",
    "description": "Widget A",
    "ordered_quantity": 10.0,
    "unit_price": 100.0,
    "line_total": 1000.0,
}

_PO = {
    "po_number": "PO-001",
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Ltd",
    "status": "open",
    "currency": "ZAR",
    "po_total": 1000.0,
    "line_items": [_PO_LINE],
}

_RECEIPT_LINE = {
    "line_no": 1,
    "sku": "SKU-001",
    "description": "Widget A",
    "received_quantity": 5.0,
}

_RECEIPT = {
    "receipt_id": "GRN-001",
    "po_number": "PO-001",
    "supplier_id": "SUP-001",
    "receipt_date": "2024-01-20",
    "status": "received",
    "line_items": [_RECEIPT_LINE],
}

_SUPPLIER = {
    "supplier_id": "SUP-001",
    "supplier_name": "Acme Ltd",
    "status": "active",
    "vat_number": "4000000000",
    "payment_terms": "30 days",
    "default_currency": "ZAR",
}

_CHECK_ITEM = {
    "check_id": "CHK-001",
    "status": "pass",
    "expected": "PO-001",
    "actual": "PO-001",
    "message": "PO number matches.",
}

_MATCH_RESULT = {
    "match_id": "MTH-001",
    "invoice_id": "INV-001",
    "invoice_number": "INV-2024-001",
    "supplier_id": "SUP-001",
    "po_number": "PO-001",
    "match_status": "matched",
    "checks": [_CHECK_ITEM],
    "exceptions": [],
    "ledger_posting_allowed": True,
    "prepared_write_allowed": True,
}

_EXCEPTION = {
    "exception_id": "EXC-001",
    "exception_type": "amount_mismatch",
    "severity": "high",
    "invoice_id": "INV-001",
    "po_number": "PO-001",
    "message": "Invoice amount does not match PO.",
    "recommended_action": "Request corrected invoice.",
    "blocking": True,
}

_LEDGER_ROW = {
    "ledger_entry_id": "LED-001",
    "source_type": "supplier_invoice",
    "source_ref": "INV-001",
    "supplier_id": "SUP-001",
    "invoice_number": "INV-2024-001",
    "po_number": "PO-001",
    "debit_account": "5000",
    "credit_account": "2000",
    "amount": 230.0,
    "currency": "ZAR",
    "status": "prepared",
}

_ROLLBACK_PLAN = {
    "rollback_id": "RBK-001",
    "rollback_type": "delete_appended_rows",
    "target": "invoice_register",
    "source_prepared_write_id": "PW-001",
    "safe_to_auto_prepare": False,
    "steps": [
        {"step_no": 1, "action": "delete rows", "target": "invoice_register", "data": {"row_ids": ["R1"]}},
    ],
    "reason": "Undo appended invoice rows.",
}

_PREPARED_WRITE = {
    "prepared_write_id": "PW-001",
    "target": "invoice_register",
    "operation": "append",
    "rows": [{"invoice_id": "INV-001"}],
    "dry_run": True,
    "requires_approval": True,
    "rollback_plan": _ROLLBACK_PLAN,
}

_REPORT = {
    "report_id": "RPT-001",
    "invoice_id": "INV-001",
    "match_status": "matched",
    "summary": "All checks passed.",
    "checks": [_CHECK_ITEM],
    "exceptions": [],
    "prepared_writes": [_PREPARED_WRITE],
    "rollback_plans": [_ROLLBACK_PLAN],
    "evidence": [],
}

_EVIDENCE = {
    "evidence_id": "EVD-001",
    "source_type": "fixture",
    "source_ref": "tests/fixtures/invoice_001.json",
    "field_path": "invoice.invoice_number",
    "raw_value": "INV-2024-001",
    "confidence": 1.0,
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _copy(base: dict, **overrides) -> dict:
    d = dict(base)
    d.update(overrides)
    return d


def _drop(base: dict, *keys: str) -> dict:
    d = dict(base)
    for k in keys:
        d.pop(k, None)
    return d


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

def test_invoice_valid_minimal() -> None:
    r = validate_invoice_shape(_INVOICE)
    assert r["ok"] is True
    assert r["errors"] == []


def test_invoice_missing_fields_fail() -> None:
    r = validate_invoice_shape(_drop(_INVOICE, "invoice_id", "supplier_id"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_invoice_wrong_field_type_fails() -> None:
    r = validate_invoice_shape(_copy(_INVOICE, invoice_id=123))
    assert r["ok"] is False
    assert any("invoice_id" in e for e in r["errors"])


def test_invoice_invalid_date_format_fails() -> None:
    r = validate_invoice_shape(_copy(_INVOICE, invoice_date="15-01-2024"))
    assert r["ok"] is False
    assert any("invoice_date" in e for e in r["errors"])


def test_invoice_total_mismatch_generates_warning() -> None:
    r = validate_invoice_shape(_copy(_INVOICE, invoice_total=999.0))
    assert r["ok"] is True
    assert any("invoice_total" in w for w in r["warnings"])


def test_invoice_line_total_mismatch_generates_warning() -> None:
    bad_line = _copy(_INVOICE_LINE, line_total=9999.0)
    r = validate_invoice_shape(_copy(_INVOICE, line_items=[bad_line]))
    assert any("line_total" in w for w in r["warnings"])


def test_invoice_line_item_wrong_type_fails() -> None:
    bad_line = _copy(_INVOICE_LINE, quantity="two")
    r = validate_invoice_shape(_copy(_INVOICE, line_items=[bad_line]))
    assert r["ok"] is False
    assert any("quantity" in e for e in r["errors"])


def test_invoice_line_item_non_dict_fails() -> None:
    r = validate_invoice_shape(_copy(_INVOICE, line_items=["not a dict"]))
    assert r["ok"] is False


# ---------------------------------------------------------------------------
# Purchase order
# ---------------------------------------------------------------------------

def test_purchase_order_valid_minimal() -> None:
    r = validate_purchase_order_shape(_PO)
    assert r["ok"] is True
    assert r["errors"] == []


def test_purchase_order_missing_fields_fail() -> None:
    r = validate_purchase_order_shape(_drop(_PO, "po_number", "status"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_purchase_order_invalid_status_fails() -> None:
    r = validate_purchase_order_shape(_copy(_PO, status="pending"))
    assert r["ok"] is False
    assert any("status" in e for e in r["errors"])


def test_purchase_order_wrong_type_fails() -> None:
    r = validate_purchase_order_shape(_copy(_PO, po_total="a lot"))
    assert r["ok"] is False
    assert any("po_total" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Goods receipt
# ---------------------------------------------------------------------------

def test_goods_receipt_valid_minimal() -> None:
    r = validate_goods_receipt_shape(_RECEIPT)
    assert r["ok"] is True
    assert r["errors"] == []


def test_goods_receipt_missing_fields_fail() -> None:
    r = validate_goods_receipt_shape(_drop(_RECEIPT, "receipt_id", "receipt_date"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_goods_receipt_invalid_status_fails() -> None:
    r = validate_goods_receipt_shape(_copy(_RECEIPT, status="delivered"))
    assert r["ok"] is False
    assert any("status" in e for e in r["errors"])


def test_goods_receipt_wrong_received_quantity_fails() -> None:
    bad_line = _copy(_RECEIPT_LINE, received_quantity="five")
    r = validate_goods_receipt_shape(_copy(_RECEIPT, line_items=[bad_line]))
    assert r["ok"] is False
    assert any("received_quantity" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

def test_supplier_valid_minimal() -> None:
    r = validate_supplier_shape(_SUPPLIER)
    assert r["ok"] is True
    assert r["errors"] == []


def test_supplier_missing_fields_fail() -> None:
    r = validate_supplier_shape(_drop(_SUPPLIER, "supplier_id", "vat_number"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_supplier_invalid_status_fails() -> None:
    r = validate_supplier_shape(_copy(_SUPPLIER, status="pending"))
    assert r["ok"] is False
    assert any("status" in e for e in r["errors"])


def test_supplier_wrong_type_fails() -> None:
    r = validate_supplier_shape(_copy(_SUPPLIER, supplier_id=42))
    assert r["ok"] is False
    assert any("supplier_id" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------

def test_match_result_valid_minimal() -> None:
    r = validate_match_result_shape(_MATCH_RESULT)
    assert r["ok"] is True
    assert r["errors"] == []


def test_match_result_missing_fields_fail() -> None:
    r = validate_match_result_shape(_drop(_MATCH_RESULT, "match_id", "match_status"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_match_result_invalid_match_status_fails() -> None:
    r = validate_match_result_shape(_copy(_MATCH_RESULT, match_status="pending"))
    assert r["ok"] is False
    assert any("match_status" in e for e in r["errors"])


def test_match_result_invalid_check_status_fails() -> None:
    bad_check = _copy(_CHECK_ITEM, status="unknown")
    r = validate_match_result_shape(_copy(_MATCH_RESULT, checks=[bad_check]))
    assert r["ok"] is False
    assert any("status" in e for e in r["errors"])


def test_match_result_wrong_bool_type_fails() -> None:
    r = validate_match_result_shape(_copy(_MATCH_RESULT, ledger_posting_allowed="yes"))
    assert r["ok"] is False
    assert any("ledger_posting_allowed" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

def test_exception_valid_minimal() -> None:
    r = validate_exception_shape(_EXCEPTION)
    assert r["ok"] is True
    assert r["errors"] == []


def test_exception_missing_fields_fail() -> None:
    r = validate_exception_shape(_drop(_EXCEPTION, "exception_id", "severity"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_exception_invalid_exception_type_fails() -> None:
    r = validate_exception_shape(_copy(_EXCEPTION, exception_type="unknown_error"))
    assert r["ok"] is False
    assert any("exception_type" in e for e in r["errors"])


def test_exception_invalid_severity_fails() -> None:
    r = validate_exception_shape(_copy(_EXCEPTION, severity="critical"))
    assert r["ok"] is False
    assert any("severity" in e for e in r["errors"])


def test_exception_blocking_wrong_type_fails() -> None:
    r = validate_exception_shape(_copy(_EXCEPTION, blocking="yes"))
    assert r["ok"] is False
    assert any("blocking" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Ledger row
# ---------------------------------------------------------------------------

def test_ledger_row_valid_minimal() -> None:
    r = validate_ledger_row_shape(_LEDGER_ROW)
    assert r["ok"] is True
    assert r["errors"] == []


def test_ledger_row_missing_fields_fail() -> None:
    r = validate_ledger_row_shape(_drop(_LEDGER_ROW, "ledger_entry_id", "amount"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_ledger_row_invalid_status_fails() -> None:
    r = validate_ledger_row_shape(_copy(_LEDGER_ROW, status="pending"))
    assert r["ok"] is False
    assert any("status" in e for e in r["errors"])


def test_ledger_row_wrong_source_type_fails() -> None:
    r = validate_ledger_row_shape(_copy(_LEDGER_ROW, source_type="customer_invoice"))
    assert r["ok"] is False
    assert any("source_type" in e for e in r["errors"])


def test_ledger_row_amount_wrong_type_fails() -> None:
    r = validate_ledger_row_shape(_copy(_LEDGER_ROW, amount="two-thirty"))
    assert r["ok"] is False
    assert any("amount" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Prepared write
# ---------------------------------------------------------------------------

def test_prepared_write_valid_minimal() -> None:
    r = validate_prepared_write_shape(_PREPARED_WRITE)
    assert r["ok"] is True
    assert r["errors"] == []


def test_prepared_write_dry_run_true_no_warning() -> None:
    r = validate_prepared_write_shape(_copy(_PREPARED_WRITE, dry_run=True))
    assert not any("dry_run" in w for w in r["warnings"])


def test_prepared_write_dry_run_false_warns() -> None:
    r = validate_prepared_write_shape(_copy(_PREPARED_WRITE, dry_run=False))
    assert any("dry_run" in w for w in r["warnings"])


def test_prepared_write_requires_approval_false_errors() -> None:
    r = validate_prepared_write_shape(_copy(_PREPARED_WRITE, requires_approval=False))
    assert r["ok"] is False
    assert any("requires_approval" in e for e in r["errors"])


def test_prepared_write_write_like_empty_rollback_plan_errors() -> None:
    r = validate_prepared_write_shape(_copy(_PREPARED_WRITE, operation="append", rollback_plan={}))
    assert r["ok"] is False
    assert any("rollback_plan" in e for e in r["errors"])


def test_prepared_write_missing_fields_fail() -> None:
    r = validate_prepared_write_shape(_drop(_PREPARED_WRITE, "prepared_write_id", "dry_run"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_prepared_write_invalid_target_fails() -> None:
    r = validate_prepared_write_shape(_copy(_PREPARED_WRITE, target="unknown_register"))
    assert r["ok"] is False
    assert any("target" in e for e in r["errors"])


def test_prepared_write_invalid_operation_fails() -> None:
    r = validate_prepared_write_shape(_copy(_PREPARED_WRITE, operation="delete"))
    assert r["ok"] is False
    assert any("operation" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Rollback plan
# ---------------------------------------------------------------------------

def test_rollback_plan_valid_minimal() -> None:
    r = validate_rollback_plan_shape(_ROLLBACK_PLAN)
    assert r["ok"] is True
    assert r["errors"] == []


def test_rollback_plan_missing_fields_fail() -> None:
    r = validate_rollback_plan_shape(_drop(_ROLLBACK_PLAN, "rollback_id", "rollback_type"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_rollback_plan_invalid_rollback_type_fails() -> None:
    r = validate_rollback_plan_shape(_copy(_ROLLBACK_PLAN, rollback_type="undo_everything"))
    assert r["ok"] is False
    assert any("rollback_type" in e for e in r["errors"])


def test_rollback_plan_step_missing_data_dict_fails() -> None:
    bad_step = {"step_no": 1, "action": "delete", "target": "register", "data": "not a dict"}
    r = validate_rollback_plan_shape(_copy(_ROLLBACK_PLAN, steps=[bad_step]))
    assert r["ok"] is False
    assert any("data" in e for e in r["errors"])


def test_rollback_plan_safe_auto_wrong_type_fails() -> None:
    r = validate_rollback_plan_shape(_copy(_ROLLBACK_PLAN, safe_to_auto_prepare="yes"))
    assert r["ok"] is False
    assert any("safe_to_auto_prepare" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def test_report_valid_minimal() -> None:
    r = validate_report_shape(_REPORT)
    assert r["ok"] is True
    assert r["errors"] == []


def test_report_missing_fields_fail() -> None:
    r = validate_report_shape(_drop(_REPORT, "report_id", "match_status"))
    assert r["ok"] is False
    assert any("Missing required fields" in e for e in r["errors"])


def test_report_invalid_match_status_fails() -> None:
    r = validate_report_shape(_copy(_REPORT, match_status="in_progress"))
    assert r["ok"] is False
    assert any("match_status" in e for e in r["errors"])


def test_report_can_contain_all_components() -> None:
    full = _copy(
        _REPORT,
        checks=[_CHECK_ITEM],
        exceptions=[_EXCEPTION],
        prepared_writes=[_PREPARED_WRITE],
        rollback_plans=[_ROLLBACK_PLAN],
        evidence=[_EVIDENCE],
    )
    r = validate_report_shape(full)
    assert r["ok"] is True
    assert r["errors"] == []


def test_report_list_fields_wrong_type_fails() -> None:
    r = validate_report_shape(_copy(_REPORT, checks="not a list"))
    assert r["ok"] is False
    assert any("checks" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_evidence_valid_minimal() -> None:
    r = validate_evidence_shape(_EVIDENCE)
    assert r["ok"] is True
    assert r["errors"] == []


def test_evidence_invalid_source_type_fails() -> None:
    r = validate_evidence_shape(_copy(_EVIDENCE, source_type="database"))
    assert r["ok"] is False
    assert any("source_type" in e for e in r["errors"])


def test_evidence_confidence_out_of_range_fails() -> None:
    r = validate_evidence_shape(_copy(_EVIDENCE, confidence=1.5))
    assert r["ok"] is False
    assert any("confidence" in e for e in r["errors"])


def test_evidence_confidence_wrong_type_fails() -> None:
    r = validate_evidence_shape(_copy(_EVIDENCE, confidence="high"))
    assert r["ok"] is False
    assert any("confidence" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# All validators return {ok, errors, warnings}
# ---------------------------------------------------------------------------

def test_all_validators_return_correct_shape() -> None:
    validators = [
        (validate_invoice_shape, _INVOICE),
        (validate_purchase_order_shape, _PO),
        (validate_goods_receipt_shape, _RECEIPT),
        (validate_supplier_shape, _SUPPLIER),
        (validate_match_result_shape, _MATCH_RESULT),
        (validate_exception_shape, _EXCEPTION),
        (validate_ledger_row_shape, _LEDGER_ROW),
        (validate_prepared_write_shape, _PREPARED_WRITE),
        (validate_rollback_plan_shape, _ROLLBACK_PLAN),
        (validate_report_shape, _REPORT),
        (validate_evidence_shape, _EVIDENCE),
    ]
    for fn, fixture in validators:
        result = fn(fixture)
        assert isinstance(result, dict), f"{fn.__name__} must return a dict"
        assert "ok" in result, f"{fn.__name__} missing 'ok'"
        assert "errors" in result, f"{fn.__name__} missing 'errors'"
        assert "warnings" in result, f"{fn.__name__} missing 'warnings'"
        assert isinstance(result["ok"], bool), f"{fn.__name__} 'ok' must be bool"
        assert isinstance(result["errors"], list), f"{fn.__name__} 'errors' must be list"
        assert isinstance(result["warnings"], list), f"{fn.__name__} 'warnings' must be list"


def test_all_validators_reject_non_dict_input() -> None:
    validators = [
        validate_invoice_shape,
        validate_purchase_order_shape,
        validate_goods_receipt_shape,
        validate_supplier_shape,
        validate_match_result_shape,
        validate_exception_shape,
        validate_ledger_row_shape,
        validate_prepared_write_shape,
        validate_rollback_plan_shape,
        validate_report_shape,
        validate_evidence_shape,
    ]
    for fn in validators:
        result = fn("not a dict")  # type: ignore[arg-type]
        assert result["ok"] is False, f"{fn.__name__} should reject non-dict input"
        assert result["errors"], f"{fn.__name__} should report errors for non-dict input"
