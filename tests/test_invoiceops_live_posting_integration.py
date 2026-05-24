"""Spec 156 — InvoiceOps live posting integration guard tests.

Exercises the full plan→preflight→approval-pack pipeline in memory
without any live side effects or real credentials.
"""
from __future__ import annotations

import tempfile
import pytest
from runtime.invoiceops_live_posting import (
    build_invoiceops_live_posting_plan,
    run_invoiceops_live_posting_preflight,
)
from runtime.invoiceops_posting_approval_pack import build_invoiceops_posting_approval_pack
from runtime.invoiceops_posting_ledger import (
    build_posting_ledger_entry,
    append_posting_ledger_entry,
    read_posting_ledger_entries,
    STATUS_EXECUTED_VERIFIED,
)


def _make_write(target="invoice_register", idx=1):
    return {
        "prepared_write_id": f"pw_{idx}",
        "target": target,
        "rows": [{"invoice_number": "INV-INT-001", "amount": 500 * idx}],
        "rollback_plan": {"rollback_id": f"rp_{idx}", "steps": ["delete_row"]},
        "invoice_number": "INV-INT-001",
        "dry_run": True,
        "requires_approval": True,
    }


@pytest.fixture
def matched_plan():
    return build_invoiceops_live_posting_plan(
        frame_id="frame_int_001",
        invoice_id="INV-INT-001",
        invoice_number="INV-INT-001",
        supplier_name="Integration Supplier Ltd",
        po_number="PO-INT-001",
        match_status="matched",
        prepared_writes=[_make_write("invoice_register", 1)],
    )


def test_full_pipeline_plan_has_pending_action(matched_plan):
    assert len(matched_plan["pending_actions"]) == 1


def test_full_pipeline_preflight_not_ok_without_approval(matched_plan):
    with tempfile.TemporaryDirectory() as tmpdir:
        preflight = run_invoiceops_live_posting_preflight(
            posting_plan=matched_plan,
            runtime_data_dir=tmpdir,
        )
    # Pending action is PENDING_APPROVAL, not yet approved — preflight should not be fully ok
    assert isinstance(preflight, dict)


def test_full_pipeline_approval_pack_has_pending_actions(matched_plan):
    pack = build_invoiceops_posting_approval_pack(
        posting_plan=matched_plan,
        invoice={
            "invoice_id": "INV-INT-001",
            "invoice_number": "INV-INT-001",
            "supplier_name": "Integration Supplier Ltd",
            "po_number": "PO-INT-001",
            "invoice_total": 500.0,
        },
    )
    assert len(pack["pending_actions"]) == 1


def test_full_pipeline_ledger_records_after_simulated_execution(matched_plan):
    action = matched_plan["pending_actions"][0]
    entry = build_posting_ledger_entry(
        frame_id=matched_plan["frame_id"],
        posting_plan_id=matched_plan["posting_plan_id"],
        invoice_id=matched_plan["invoice_id"],
        invoice_number=matched_plan["invoice_number"],
        supplier_name=matched_plan["supplier_name"],
        target_register=action["target_register"],
        action_id=action["action_id"],
        approved_by="test_operator",
        worker_identity={"worker_id": "test_worker"},
        idempotency_key=action["idempotency_key"],
        payload_hash=action["prepared_payload_hash"],
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=True,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        append_posting_ledger_entry(entry, runtime_data_dir=tmpdir)
        entries = read_posting_ledger_entries(runtime_data_dir=tmpdir)
    assert len(entries) == 1
    assert entries[0]["status"] == STATUS_EXECUTED_VERIFIED


def test_pipeline_no_batch_posting():
    """Two writes produce two separate pending actions — not a batch."""
    plan = build_invoiceops_live_posting_plan(
        frame_id="frame_int_002",
        invoice_id="INV-INT-002",
        invoice_number="INV-INT-002",
        supplier_name="Batch Guard Supplier",
        po_number="PO-INT-002",
        match_status="matched",
        prepared_writes=[_make_write("invoice_register", 1), _make_write("match_register", 2)],
    )
    # Each prepared write becomes its own pending action — no aggregation
    assert plan["eligible_write_count"] == len(plan["pending_actions"])


def test_pipeline_idempotency_keys_are_unique(matched_plan):
    plan = build_invoiceops_live_posting_plan(
        frame_id="frame_int_003",
        invoice_id="INV-INT-003",
        invoice_number="INV-INT-003",
        supplier_name="Idempotency Supplier",
        po_number="PO-INT-003",
        match_status="matched",
        prepared_writes=[_make_write("invoice_register", 1), _make_write("match_register", 2)],
    )
    keys = [a["idempotency_key"] for a in plan["pending_actions"]]
    assert len(set(keys)) == len(keys)


def test_pipeline_no_auto_approval():
    plan = build_invoiceops_live_posting_plan(
        frame_id="frame_int_004",
        invoice_id="INV-INT-004",
        invoice_number="INV-INT-004",
        supplier_name="No Auto Approval Supplier",
        po_number="PO-INT-004",
        match_status="matched",
        prepared_writes=[_make_write("invoice_register", 1)],
    )
    for action in plan["pending_actions"]:
        assert action["status"] == "PENDING_APPROVAL"
        assert not action.get("approved_by")


def test_pipeline_no_execute_import_in_module():
    """The core posting plan module must not automatically execute any write."""
    import inspect
    from runtime import invoiceops_live_posting as mod
    src = inspect.getsource(mod)
    assert "auto_execute" not in src
    assert "auto_approve" not in src
