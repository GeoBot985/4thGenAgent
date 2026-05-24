"""Spec 156 — InvoiceOps posting ledger tests."""
from __future__ import annotations

import tempfile
import pytest
from runtime.invoiceops_posting_ledger import (
    build_posting_ledger_entry,
    append_posting_ledger_entry,
    read_posting_ledger_entries,
    get_posting_ledger_entry_by_action,
    get_posting_ledger_entry_by_idempotency_key,
    build_posting_ledger_report,
    record_posting_execution,
    STATUS_EXECUTED_VERIFIED,
    STATUS_EXECUTED_UNVERIFIED,
    STATUS_BLOCKED,
    STATUS_FAILED,
)


def _entry(**overrides):
    base = dict(
        frame_id="frame_001",
        posting_plan_id="pp_001",
        invoice_id="INV-001",
        invoice_number="INV-001",
        supplier_name="Acme Ltd",
        target_register="invoice_register",
        action_id="pa_001",
        approved_by="operator_1",
        worker_identity={"worker_id": "w1"},
        idempotency_key="ikey_001",
        payload_hash="hash_001",
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=True,
    )
    base.update(overrides)
    return build_posting_ledger_entry(**base)


def test_entry_has_posting_ledger_id():
    entry = _entry()
    assert entry["posting_ledger_id"].startswith("PLG-")


def test_entry_has_created_at():
    entry = _entry()
    assert entry.get("created_at")


def test_entry_carries_frame_id():
    entry = _entry()
    assert entry["frame_id"] == "frame_001"


def test_entry_carries_action_id():
    entry = _entry()
    assert entry["action_id"] == "pa_001"


def test_entry_carries_status():
    entry = _entry(status=STATUS_BLOCKED)
    assert entry["status"] == STATUS_BLOCKED


def test_entry_worker_identity_is_dict():
    entry = _entry(worker_identity="string_worker")
    assert isinstance(entry["worker_identity"], dict)


def test_status_constants_defined():
    assert STATUS_EXECUTED_VERIFIED == "EXECUTED_VERIFIED"
    assert STATUS_EXECUTED_UNVERIFIED == "EXECUTED_UNVERIFIED"
    assert STATUS_BLOCKED == "BLOCKED"
    assert STATUS_FAILED == "FAILED"


def test_append_and_read():
    entry = _entry()
    with tempfile.TemporaryDirectory() as tmpdir:
        append_posting_ledger_entry(entry, runtime_data_dir=tmpdir)
        entries = read_posting_ledger_entries(runtime_data_dir=tmpdir)
    assert len(entries) == 1
    assert entries[0]["action_id"] == "pa_001"


def test_append_multiple_entries():
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(3):
            e = _entry(action_id=f"pa_{i}", idempotency_key=f"ikey_{i}")
            append_posting_ledger_entry(e, runtime_data_dir=tmpdir)
        entries = read_posting_ledger_entries(runtime_data_dir=tmpdir)
    assert len(entries) == 3


def test_get_by_action_id():
    entry = _entry(action_id="pa_target")
    with tempfile.TemporaryDirectory() as tmpdir:
        append_posting_ledger_entry(entry, runtime_data_dir=tmpdir)
        found = get_posting_ledger_entry_by_action("pa_target", runtime_data_dir=tmpdir)
    assert found is not None
    assert found["action_id"] == "pa_target"


def test_get_by_action_id_not_found_returns_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        found = get_posting_ledger_entry_by_action("missing_id", runtime_data_dir=tmpdir)
    assert found is None


def test_get_by_idempotency_key():
    entry = _entry(idempotency_key="ikey_unique")
    with tempfile.TemporaryDirectory() as tmpdir:
        append_posting_ledger_entry(entry, runtime_data_dir=tmpdir)
        found = get_posting_ledger_entry_by_idempotency_key("ikey_unique", runtime_data_dir=tmpdir)
    assert found is not None
    assert found["idempotency_key"] == "ikey_unique"


def test_read_empty_ledger_returns_empty_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        entries = read_posting_ledger_entries(runtime_data_dir=tmpdir)
    assert entries == []


def test_ledger_report_shape():
    with tempfile.TemporaryDirectory() as tmpdir:
        report = build_posting_ledger_report(runtime_data_dir=tmpdir)
    assert "total_entries" in report
    assert "executed_verified_count" in report
    assert "executed_unverified_count" in report
    assert "blocked_count" in report
    assert "failed_count" in report


def test_record_posting_execution_executed_verified():
    posting_plan = {
        "frame_id": "frame_001",
        "posting_plan_id": "pp_001",
        "invoice_id": "INV-001",
        "invoice_number": "INV-001",
        "supplier_name": "Acme",
    }
    action = {
        "action_id": "pa_001",
        "target_register": "invoice_register",
        "tool": "sheet/write_rows",
        "profile": "controlled_live_write",
        "approved_by": "op1",
        "worker_identity": {"worker_id": "w1"},
        "idempotency_key": "ikey_test",
        "prepared_payload_hash": "hash_test",
        "rollback_plan": {"rollback_id": "rp1"},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_entry = record_posting_execution(
            posting_plan=posting_plan,
            action=action,
            execution_result={"executed": True},
            verification={"verified": True},
            runtime_data_dir=tmpdir,
        )
        entries = read_posting_ledger_entries(runtime_data_dir=tmpdir)
    assert ledger_entry["status"] == STATUS_EXECUTED_VERIFIED
    assert len(entries) == 1


def test_record_posting_execution_blocked():
    posting_plan = {"frame_id": "f1", "posting_plan_id": "pp1", "invoice_id": "INV-001", "invoice_number": "INV-001", "supplier_name": "Acme"}
    action = {"action_id": "pa_2", "target_register": "invoice_register", "approved_by": "op1", "worker_identity": {}, "idempotency_key": "ikey_b", "prepared_payload_hash": "h", "rollback_plan": {}}
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_entry = record_posting_execution(
            posting_plan=posting_plan,
            action=action,
            execution_result={"executed": False, "blocked": True},
            verification={"verified": False},
            runtime_data_dir=tmpdir,
        )
    assert ledger_entry["status"] == STATUS_BLOCKED
