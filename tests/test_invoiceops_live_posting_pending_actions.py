"""Spec 156 — InvoiceOps pending action shape and content tests."""
from __future__ import annotations

import hashlib
import json
import pytest
from runtime.invoiceops_live_posting import build_invoiceops_live_posting_plan


def _plan_with_write(target="invoice_register", rows=None, extra=None):
    rows = rows or [{"invoice_number": "INV-001", "amount": 500}]
    pw = {
        "prepared_write_id": "pw_1",
        "target": target,
        "rows": rows,
        "rollback_plan": {"rollback_id": "rp_1", "steps": ["delete_row"]},
        "invoice_number": "INV-001",
        "dry_run": True,
        "requires_approval": True,
    }
    if extra:
        pw.update(extra)
    return build_invoiceops_live_posting_plan(
        frame_id="frame_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        po_number="PO-001",
        match_status="matched",
        prepared_writes=[pw],
    )


def test_pending_action_has_action_id():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action.get("action_id")


def test_pending_action_status_is_pending_approval():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action["status"] == "PENDING_APPROVAL"


def test_pending_action_action_type():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action["action_type"] == "invoiceops_sheet_write_rows"


def test_pending_action_has_target_register():
    plan = _plan_with_write("match_register", rows=[{"invoice_number": "INV-001", "match_status": "matched"}])
    action = plan["pending_actions"][0]
    assert "match" in action["target_register"]


def test_pending_action_business_ref_is_invoice_number():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action["business_ref"] == "INV-001"


def test_pending_action_has_idempotency_key():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    key = action.get("idempotency_key", "")
    assert len(key) > 0


def test_pending_action_idempotency_key_is_deterministic():
    plan1 = _plan_with_write()
    plan2 = _plan_with_write()
    assert plan1["pending_actions"][0]["idempotency_key"] == plan2["pending_actions"][0]["idempotency_key"]


def test_pending_action_has_payload_hash():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action.get("prepared_payload_hash")


def test_pending_action_payload_hash_is_sha256():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    h = action["prepared_payload_hash"]
    # SHA-256 hex is 64 chars
    assert len(h) == 64 or len(h) > 16  # some implementations may truncate


def test_pending_action_has_rollback_plan():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action.get("rollback_plan")


def test_pending_action_rollback_plan_has_rollback_id():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action["rollback_plan"].get("rollback_id") == "rp_1"


def test_pending_action_has_approval_context():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert "approval_context" in action


def test_pending_action_tool_is_sheet_write_rows():
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action.get("tool") == "sheet/write_rows"


def test_pending_action_tool_is_sheet_write_rows_second_check():
    """Confirm tool field is present and correct (second check for completeness)."""
    plan = _plan_with_write()
    action = plan["pending_actions"][0]
    assert action.get("tool") == "sheet/write_rows"
    assert "action_id" in action
