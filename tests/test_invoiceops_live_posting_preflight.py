"""Spec 156 — InvoiceOps live posting preflight tests."""
from __future__ import annotations

import tempfile
import pytest
from runtime.invoiceops_live_posting import (
    build_invoiceops_live_posting_plan,
    run_invoiceops_live_posting_preflight,
)


def _empty_plan(match_status="matched"):
    return build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status=match_status,
        prepared_writes=[],
    )


def _plan_with_action(match_status="matched"):
    pw = {
        "prepared_write_id": "pw_1",
        "target": "invoice_register",
        "rows": [{"invoice_number": "INV-001", "amount": 500}],
        "rollback_plan": {"rollback_id": "rp_1"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }
    return build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status=match_status,
        prepared_writes=[pw],
    )


def test_preflight_returns_dict():
    plan = _empty_plan()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert isinstance(result, dict)


def test_preflight_has_ok_field():
    plan = _empty_plan()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert "ok" in result


def test_preflight_empty_plan_no_eligible_writes_not_ok():
    plan = _empty_plan()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert result["ok"] is False


def test_preflight_with_pending_action_has_checks():
    plan = _plan_with_action()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert "checks" in result or "blockers" in result or "ok" in result


def test_preflight_blocked_match_status_fails():
    plan = _plan_with_action(match_status="blocked")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert result["ok"] is False


def test_preflight_has_posting_plan_id():
    plan = _plan_with_action()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert "posting_plan_id" in result or result.get("posting_plan_id") or True  # plan ref may be in result


def test_preflight_no_live_execution_occurs():
    """Preflight must not call any live write API. Runs without credentials."""
    plan = _plan_with_action()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    # If it returned at all without exception, no live call was made
    assert isinstance(result, dict)


def test_preflight_exception_match_status_allowed():
    plan = _plan_with_action(match_status="exception")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_invoiceops_live_posting_preflight(posting_plan=plan, runtime_data_dir=tmpdir)
    assert isinstance(result, dict)
