from __future__ import annotations

from pathlib import Path

from runtime.invoiceops_accounting_evidence_pack import build_accounting_evidence_pack
from runtime.invoiceops_posting_ledger import STATUS_EXECUTED_VERIFIED, append_posting_ledger_entry, build_posting_ledger_entry
from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_result


def _seed_posting_ledger(runtime_data_dir: Path) -> None:
    entry = build_posting_ledger_entry(
        frame_id="frame-report-001",
        posting_plan_id="plan-report-001",
        invoice_id="INV-INV-2024-001",
        invoice_number="INV-2024-001",
        supplier_name="Acme Supplies (Pty) Ltd",
        target_register="Ledger",
        action_id="action-report-001",
        approved_by="system",
        worker_identity={"worker_id": "service-worker-1"},
        idempotency_key="idem-report-001",
        payload_hash="hash-report-001",
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=False,
        rollback_plan={"rollback_id": "rbk-report-001", "rollback_type": "mark_reversed"},
    )
    append_posting_ledger_entry(entry, runtime_data_dir=runtime_data_dir)


def test_reconciliation_and_evidence_pack_reports_include_required_text(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime_data"
    runtime_data_dir.mkdir(parents=True, exist_ok=True)
    _seed_posting_ledger(runtime_data_dir)

    reconciliation = build_invoiceops_reconciliation_result(
        frame_id="frame-report-001",
        posting_plan_id="plan-report-001",
        invoice_number="INV-2024-001",
        runtime_data_dir=runtime_data_dir,
        profile="service",
        fixture_mode=True,
        write_report=True,
    )
    pack = build_accounting_evidence_pack(
        frame_id="frame-report-001",
        posting_plan_id="plan-report-001",
        invoice_number="INV-2024-001",
        runtime_data_dir=runtime_data_dir,
        profile="service",
        fixture_mode=True,
        write_report=True,
    )

    reconciliation_md = Path(reconciliation["report_paths"]["markdown"]).read_text(encoding="utf-8")
    pack_md = Path(pack["report_paths"]["markdown"]).read_text(encoding="utf-8")

    assert "InvoiceOps Post-Write Reconciliation" in reconciliation_md
    assert "Ledger" in reconciliation_md
    assert "Final Status" in reconciliation_md
    assert "read-only" in pack_md.lower()
    assert "Safety Statement" in pack_md
    assert "rollback" in pack_md.lower()
