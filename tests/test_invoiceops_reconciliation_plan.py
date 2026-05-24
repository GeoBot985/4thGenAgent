from __future__ import annotations

import json
from pathlib import Path

from runtime.invoiceops_posting_ledger import STATUS_EXECUTED_VERIFIED, append_posting_ledger_entry, build_posting_ledger_entry
from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_plan


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "invoiceops"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / "reports" / name).read_text(encoding="utf-8"))


def test_reconciliation_plan_loads_fixture_rows_and_posting_ledger(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime_data"
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    entry = build_posting_ledger_entry(
        frame_id="frame-001",
        posting_plan_id="plan-001",
        invoice_id="INV-INV-2024-001",
        invoice_number="INV-2024-001",
        supplier_name="Acme Supplies (Pty) Ltd",
        target_register="Ledger",
        action_id="action-001",
        approved_by="system",
        worker_identity={"worker_id": "service-worker-1"},
        idempotency_key="idem-001",
        payload_hash="hash-001",
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=False,
        rollback_plan={"rollback_id": "rbk-001"},
    )
    append_posting_ledger_entry(entry, runtime_data_dir=runtime_data_dir)

    plan = build_invoiceops_reconciliation_plan(
        invoice_number="INV-2024-001",
        frame_id="frame-001",
        posting_plan_id="plan-001",
        runtime_data_dir=runtime_data_dir,
        profile="service",
        fixture_mode=True,
    )

    assert plan["ok"] is True
    assert plan["invoice_number"] == "INV-2024-001"
    assert plan["frame_id"] == "frame-001"
    assert plan["posting_plan_id"] == "plan-001"
    assert plan["invoice_register_rows"]
    assert plan["ledger_rows"]
    assert plan["posting_ledger_entry"]["posting_ledger_id"] == entry["posting_ledger_id"]
    assert plan["rollback_plan"]["rollback_id"] == "rbk-001"
    assert plan["registers_checked"] == [
        "invoice_register",
        "match_register",
        "exception_register",
        "ledger_register",
        "posting_ledger",
    ]


def test_reconciliation_plan_safe_for_missing_invoice(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime_data"
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    plan = build_invoiceops_reconciliation_plan(
        invoice_number="fake",
        runtime_data_dir=runtime_data_dir,
        profile="service",
        fixture_mode=True,
    )

    assert plan["ok"] is True
    assert plan["invoice_number"] == "fake"
    assert plan["invoice_register_rows"] == []
    assert plan["ledger_rows"] == []
