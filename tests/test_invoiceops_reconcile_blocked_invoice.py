from __future__ import annotations

import json
from pathlib import Path

from runtime.invoiceops_posting_ledger import STATUS_EXECUTED_VERIFIED, build_posting_ledger_entry
from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_result


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "invoiceops"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / "reports" / name).read_text(encoding="utf-8"))


def _blocked_plan() -> dict:
    payload = _load("blocked_match.json")
    invoice = dict(payload["invoice"])
    match_result = dict(payload["match_result"])
    entry = build_posting_ledger_entry(
        frame_id="frame-blocked-001",
        posting_plan_id="plan-blocked-001",
        invoice_id=invoice["invoice_id"],
        invoice_number=invoice["invoice_number"],
        supplier_name=invoice["supplier_name"],
        target_register="Ledger",
        action_id="action-blocked-001",
        approved_by="system",
        worker_identity={"worker_id": "service-worker-1"},
        idempotency_key="idem-blocked-001",
        payload_hash="hash-blocked-001",
        status=STATUS_EXECUTED_VERIFIED,
        side_effect_performed=False,
        rollback_plan={"rollback_id": "rbk-blocked-001", "rollback_type": "mark_reversed"},
    )
    return {
        "ok": True,
        "profile": "service",
        "fixture_mode": True,
        "generated_at": "2026-05-24T00:00:00Z",
        "invoice_number": invoice["invoice_number"],
        "invoice_id": invoice["invoice_id"],
        "supplier_name": invoice["supplier_name"],
        "posting_plan_id": "plan-blocked-001",
        "frame_id": "frame-blocked-001",
        "match_status": "blocked",
        "source_frame": {"frame_id": "frame-blocked-001", "outputs": {"invoice": invoice, "match_result": match_result}},
        "source_invoice": invoice,
        "source_match_result": match_result,
        "source_exception": dict(match_result["exceptions"][0]),
        "invoice_register_rows": [dict(invoice)],
        "match_register_rows": [match_result],
        "exception_register_rows": [dict(match_result["exceptions"][0])],
        "ledger_rows": [
            {
                "ledger_entry_id": "LED-BLOCKED-001",
                "source_type": "supplier_invoice",
                "source_ref": invoice["invoice_id"],
                "supplier_id": invoice["supplier_id"],
                "invoice_number": invoice["invoice_number"],
                "po_number": invoice["po_number"],
                "debit_account": "5000",
                "credit_account": "2000",
                "amount": invoice["invoice_total"],
                "currency": invoice["currency"],
                "status": "posted",
            }
        ],
        "posting_ledger_entry": entry,
        "rollback_plan": dict(entry["rollback_plan"]),
        "source_evidence": {"evidence_id": "EVD-BLOCKED-001"},
        "posting_ledger_entries": [entry],
        "live_execution_ledger": [],
        "config_profile": {"name": "service"},
        "registers_checked": ["invoice_register", "match_register", "exception_register", "ledger_register", "posting_ledger"],
        "report_paths": {},
    }


def test_blocked_invoice_fails_if_ledger_rows_exist(tmp_path: Path) -> None:
    result = build_invoiceops_reconciliation_result(_blocked_plan(), runtime_data_dir=tmp_path, profile="service", fixture_mode=True, write_report=True)

    assert result["status"] == "UNRECONCILED"
    assert result["ok"] is False
    assert any(check["section"] == "ledger_register" and not check["ok"] for check in result["checks"])
    assert any(check.get("critical") for check in result["checks"])

