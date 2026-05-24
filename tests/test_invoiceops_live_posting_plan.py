"""Spec 156 — InvoiceOps Live Posting Plan builder tests."""
from __future__ import annotations

import pytest
from runtime.invoiceops_live_posting import build_invoiceops_live_posting_plan


def _base_plan(match_status="matched", prepared_writes=None):
    return build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status=match_status,
        prepared_writes=prepared_writes or [],
    )


def test_plan_has_posting_plan_id():
    plan = _base_plan()
    assert plan["posting_plan_id"].startswith("PP-")


def test_plan_carries_frame_id():
    plan = _base_plan()
    assert plan["frame_id"] == "frame_001"


def test_plan_carries_invoice_metadata():
    plan = _base_plan()
    assert plan["invoice_id"] == "INV-001"
    assert plan["invoice_number"] == "INV-001"
    assert plan["supplier_name"] == "Acme Ltd"
    assert plan["po_number"] == "PO-001"


def test_plan_matched_status():
    plan = _base_plan(match_status="matched")
    assert plan["match_status"] == "matched"


def test_plan_exception_status():
    plan = _base_plan(match_status="exception")
    assert plan["match_status"] == "exception"


def test_plan_blocked_status_yields_no_eligible_writes():
    pw = [{
        "prepared_write_id": "pw_1",
        "target": "ledger_register",
        "rows": [{"invoice_number": "INV-001", "debit": 100}],
        "rollback_plan": {"rollback_id": "rp_1"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }]
    plan = _base_plan(match_status="blocked", prepared_writes=pw)
    assert plan["eligible_write_count"] == 0
    assert plan["blocked_write_count"] >= 1


def test_plan_empty_prepared_writes_has_zero_pending_actions():
    plan = _base_plan()
    assert plan["pending_actions"] == []
    assert plan["eligible_write_count"] == 0


def test_plan_valid_prepared_write_creates_pending_action():
    pw = [{
        "prepared_write_id": "pw_1",
        "target": "invoice_register",
        "rows": [{"invoice_number": "INV-001", "amount": 500}],
        "rollback_plan": {"rollback_id": "rp_1"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }]
    plan = _base_plan(prepared_writes=pw)
    assert plan["eligible_write_count"] == 1
    assert len(plan["pending_actions"]) == 1


def test_plan_blocked_target_not_in_pending_actions():
    pw = [{
        "prepared_write_id": "pw_blocked",
        "target": "supplier_master",
        "rows": [{"supplier": "Acme"}],
        "rollback_plan": {"rollback_id": "rp_b"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }]
    plan = _base_plan(prepared_writes=pw)
    assert plan["eligible_write_count"] == 0
    assert len(plan["pending_actions"]) == 0
    assert len(plan["blocked_writes"]) >= 1


def test_plan_has_write_targets_field():
    plan = _base_plan()
    assert "write_targets" in plan


def test_plan_has_rollback_plans_field():
    plan = _base_plan()
    assert "rollback_plans" in plan


def test_plan_has_idempotency_keys_field():
    pw = [{
        "prepared_write_id": "pw_2",
        "target": "match_register",
        "rows": [{"invoice_number": "INV-001", "match_status": "matched"}],
        "rollback_plan": {"rollback_id": "rp_2"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }]
    plan = _base_plan(prepared_writes=pw)
    assert len(plan["idempotency_keys"]) == 1


def test_plan_has_payload_hashes_field():
    pw = [{
        "prepared_write_id": "pw_3",
        "target": "match_register",
        "rows": [{"invoice_number": "INV-001", "match_status": "matched"}],
        "rollback_plan": {"rollback_id": "rp_3"},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }]
    plan = _base_plan(prepared_writes=pw)
    assert len(plan["payload_hashes"]) == 1
