from __future__ import annotations

import json
from pathlib import Path

from runtime.invoiceops_posting_ledger import STATUS_EXECUTED_VERIFIED, build_posting_ledger_entry
from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_result


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "invoiceops"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / "reports" / name).read_text(encoding="utf-8"))


def _matched_plan() -> dict:
    payload = _load("happy_match.json")
    invoice = dict(payload["invoice"])
    match_result = dict(payload["match_result"])
    ledger_rows = json.loads((FIXTURE_DIR / "sheets" / "ledger.json").read_text(encoding="utf-8"))
    invoice_rows = json.loads((FIXTURE_DIR / "sheets" / "invoice_register.json").read_text(encoding="utf-8"))
    entry = build_posting_ledger_entry(
        frame_id="frame-matched-001",
        posting_plan_id="plan-matched-001",
        invoice_id=invoice["invoice_id"],
        invoice_number=invoice["invoice_number"],
        supplier_name=invoice["supplier_name"],
        target_register="Ledger",
        action_id="action-matched-001",
        approved_by="system",
        worker_identity={"worker_id": "service-worker-1"},
        idempotency_key="idem-matched-001",
        payload_hash="hash-matched-001",
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=False,
        rollback_plan={"rollback_id": "rbk-matched-001", "rollback_type": "mark_reversed"},
    )
    return {
        "ok": True,
        "profile": "service",
        "fixture_mode": True,
        "generated_at": "2026-05-24T00:00:00Z",
        "invoice_number": invoice["invoice_number"],
        "invoice_id": invoice["invoice_id"],
        "supplier_name": invoice["supplier_name"],
        "posting_plan_id": "plan-matched-001",
        "frame_id": "frame-matched-001",
        "match_status": "matched",
        "source_frame": {"frame_id": "frame-matched-001", "outputs": {"invoice": invoice, "match_result": match_result}},
        "source_invoice": invoice,
        "source_match_result": match_result,
        "source_exception": {},
        "invoice_register_rows": invoice_rows,
        "match_register_rows": [match_result],
        "exception_register_rows": [],
        "ledger_rows": ledger_rows,
        "posting_ledger_entry": entry,
        "rollback_plan": dict(entry["rollback_plan"]),
        "source_evidence": {"evidence_id": "EVD-001"},
        "posting_ledger_entries": [entry],
        "live_execution_ledger": [],
        "config_profile": {"name": "service"},
        "registers_checked": ["invoice_register", "match_register", "exception_register", "ledger_register", "posting_ledger"],
        "report_paths": {},
    }


def test_matched_invoice_reconciles(tmp_path: Path) -> None:
    result = build_invoiceops_reconciliation_result(_matched_plan(), runtime_data_dir=tmp_path, profile="service", fixture_mode=True, write_report=True)

    assert result["ok"] is True
    assert result["status"] == "RECONCILED"
    assert result["invoice_number"] == "INV-2024-001"
    assert result["checks"]
    assert any(check["section"] == "ledger_register" and check["ok"] for check in result["checks"])
    assert any(check["section"] == "posting_ledger" and check["ok"] for check in result["checks"])
    assert result["report_paths"]["json"].endswith("_reconciliation.json")
    assert Path(result["report_paths"]["json"]).is_file()
    assert Path(result["report_paths"]["markdown"]).is_file()

