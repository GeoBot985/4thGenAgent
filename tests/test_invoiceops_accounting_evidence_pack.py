from __future__ import annotations

from pathlib import Path

from runtime.invoiceops_accounting_evidence_pack import build_accounting_evidence_pack
from runtime.invoiceops_posting_ledger import STATUS_EXECUTED_VERIFIED, append_posting_ledger_entry, build_posting_ledger_entry


def _seed_posting_ledger(runtime_data_dir: Path) -> None:
    entry = build_posting_ledger_entry(
        frame_id="frame-evidence-001",
        posting_plan_id="plan-evidence-001",
        invoice_id="INV-INV-2024-001",
        invoice_number="INV-2024-001",
        supplier_name="Acme Supplies (Pty) Ltd",
        target_register="Ledger",
        action_id="action-evidence-001",
        approved_by="system",
        worker_identity={"worker_id": "service-worker-1"},
        idempotency_key="idem-evidence-001",
        payload_hash="hash-evidence-001",
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=False,
        rollback_plan={"rollback_id": "rbk-evidence-001", "rollback_type": "mark_reversed"},
    )
    append_posting_ledger_entry(entry, runtime_data_dir=runtime_data_dir)


def test_accounting_evidence_pack_includes_all_required_sections(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime_data"
    runtime_data_dir.mkdir(parents=True, exist_ok=True)
    _seed_posting_ledger(runtime_data_dir)

    pack = build_accounting_evidence_pack(
        frame_id="frame-evidence-001",
        posting_plan_id="plan-evidence-001",
        invoice_number="INV-2024-001",
        runtime_data_dir=runtime_data_dir,
        profile="service",
        fixture_mode=True,
        write_report=True,
    )

    assert pack["ok"] is True
    assert pack["status"] == "RECONCILED"
    assert set(pack["sections"]) == {
        "invoice_source",
        "extraction",
        "validation",
        "matching",
        "posting",
        "reconciliation",
        "rollback",
        "audit_trail",
    }
    assert pack["sections"]["invoice_source"]
    assert pack["sections"]["reconciliation"]
    assert pack["report_paths"]["json"].endswith("_accounting_evidence_pack.json")
    assert Path(pack["report_paths"]["json"]).is_file()
    assert Path(pack["report_paths"]["markdown"]).is_file()
