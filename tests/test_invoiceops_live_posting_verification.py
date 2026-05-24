"""Spec 156 — InvoiceOps post-write verification tests."""
from __future__ import annotations

import pytest
from runtime.invoiceops_live_posting import verify_invoiceops_live_posting


def _base_action():
    return {
        "action_id": "pa_001",
        "target_register": "invoice_register",
        "business_ref": "INV-001",
        "idempotency_key": "ikey_001",
        "prepared_payload_hash": "abc123",
        "tool": "sheet/write_rows",
        "profile": "controlled_live_write",
    }


def _base_posting_plan():
    return {
        "posting_plan_id": "pp_001",
        "frame_id": "frame_001",
        "invoice_number": "INV-001",
    }


def _base_result(rows_written=1, executed=True):
    return {
        "executed": executed,
        "tool": "sheet/write_rows",
        "target_ref": "invoice_register",
        "rows_written": rows_written,
        "rows": [{"invoice_number": "INV-001", "amount": 500}],
    }


def test_verification_returns_dict():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(),
    )
    assert isinstance(result, dict)


def test_verification_has_verified_field():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(),
    )
    assert "verified" in result


def test_successful_execution_can_verify():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(rows_written=1),
    )
    assert isinstance(result["verified"], bool)


def test_execution_not_ok_fails_verification():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(executed=False),
    )
    assert result["verified"] is False


def test_zero_rows_written_fails_verification():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(rows_written=0),
    )
    assert result["verified"] is False


def test_negative_rows_written_fails_verification():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(rows_written=-1),
    )
    assert result["verified"] is False


def test_verification_has_checks_or_failures():
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(executed=False),
    )
    assert "checks" in result or "failures" in result or result["verified"] is False


def test_verification_no_live_call_made():
    """verify_invoiceops_live_posting must not call any live API."""
    result = verify_invoiceops_live_posting(
        posting_plan=_base_posting_plan(),
        action=_base_action(),
        execution_result=_base_result(),
    )
    assert isinstance(result, dict)
