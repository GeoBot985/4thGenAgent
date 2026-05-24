"""Spec 156 — InvoiceOps prepared writes eligibility validation tests."""
from __future__ import annotations

import pytest
from runtime.invoiceops_live_posting import validate_invoiceops_prepared_writes_for_live


def _valid_write(target="invoice_register", **overrides):
    base = {
        "prepared_write_id": "pw_1",
        "target": target,
        "rows": [{"invoice_number": "INV-001", "amount": 500}],
        "rollback_plan": {"rollback_id": "rp_1"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }
    base.update(overrides)
    return base


def test_invoice_register_is_eligible():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("invoice_register"),
    )
    assert result["eligible"] is True
    assert not result["errors"]


def test_match_register_is_eligible():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("match_register", rows=[{"invoice_number": "INV-001", "match_status": "matched"}]),
    )
    assert result["eligible"] is True


def test_exception_register_is_eligible():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("exception_register", rows=[{"invoice_number": "INV-001", "exception_type": "missing_po"}]),
    )
    assert result["eligible"] is True


def test_blocked_target_supplier_master():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("supplier_master"),
    )
    assert result["eligible"] is False
    assert result["errors"]


def test_blocked_target_bank_register():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("bank_register"),
    )
    assert result["eligible"] is False


def test_blocked_target_payment_register():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("payment_register"),
    )
    assert result["eligible"] is False


def test_blocked_target_po_register():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("po_register"),
    )
    assert result["eligible"] is False


def test_empty_rows_blocked():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write(rows=[]),
    )
    assert result["eligible"] is False
    assert result["errors"]


def test_missing_rollback_plan_blocked():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write(rollback_plan={}),
    )
    assert result["eligible"] is False
    assert result["errors"]


def test_none_rollback_plan_blocked():
    pw = _valid_write()
    pw["rollback_plan"] = None
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=pw,
    )
    assert result["eligible"] is False


def test_valid_result_has_target_field():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("invoice_register"),
    )
    assert "target" in result


def test_valid_result_has_row_count():
    result = validate_invoiceops_prepared_writes_for_live(
        prepared_write=_valid_write("invoice_register"),
    )
    assert result["row_count"] == 1
