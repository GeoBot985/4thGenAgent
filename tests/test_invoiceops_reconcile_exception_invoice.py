from __future__ import annotations

from runtime.invoiceops_posting_ledger import STATUS_BLOCKED, build_posting_ledger_entry
from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_result


def _exception_plan() -> dict:
    invoice = {
        "invoice_id": "INV-EXC-001",
        "supplier_id": "SUP-EXC-001",
        "supplier_name": "Gamma Industrial",
        "invoice_number": "INV-2026-002",
        "invoice_date": "2026-05-20",
        "po_number": "PO-2026-002",
        "currency": "ZAR",
        "subtotal": 1000.0,
        "tax_total": 150.0,
        "invoice_total": 1150.0,
    }
    match_result = {
        "match_id": "MATCH-EXC-001",
        "invoice_id": invoice["invoice_id"],
        "invoice_number": invoice["invoice_number"],
        "supplier_id": invoice["supplier_id"],
        "po_number": invoice["po_number"],
        "match_status": "exception",
        "exceptions": [
            {
                "exception_id": "EXC-EXC-001",
                "exception_type": "tax_mismatch",
                "severity": "medium",
                "invoice_id": invoice["invoice_id"],
                "po_number": invoice["po_number"],
                "message": "Tax mismatch.",
                "recommended_action": "Review tax.",
                "blocking": False,
            }
        ],
        "ledger_posting_allowed": False,
        "prepared_write_allowed": True,
    }
    exception_row = dict(match_result["exceptions"][0])
    entry = build_posting_ledger_entry(
        frame_id="frame-exc-001",
        posting_plan_id="plan-exc-001",
        invoice_id=invoice["invoice_id"],
        invoice_number=invoice["invoice_number"],
        supplier_name=invoice["supplier_name"],
        target_register="ExceptionRegister",
        action_id="action-exc-001",
        approved_by="system",
        worker_identity={"worker_id": "service-worker-1"},
        idempotency_key="idem-exc-001",
        payload_hash="hash-exc-001",
        status=STATUS_BLOCKED,
        side_effect_performed=False,
        rollback_plan={"rollback_id": "rbk-exc-001", "rollback_type": "delete_appended_rows"},
    )
    return {
        "ok": True,
        "profile": "service",
        "fixture_mode": True,
        "generated_at": "2026-05-24T00:00:00Z",
        "invoice_number": invoice["invoice_number"],
        "invoice_id": invoice["invoice_id"],
        "supplier_name": invoice["supplier_name"],
        "posting_plan_id": "plan-exc-001",
        "frame_id": "frame-exc-001",
        "match_status": "exception",
        "source_frame": {"frame_id": "frame-exc-001", "outputs": {"invoice": invoice, "match_result": match_result}},
        "source_invoice": invoice,
        "source_match_result": match_result,
        "source_exception": exception_row,
        "invoice_register_rows": [dict(invoice)],
        "match_register_rows": [match_result],
        "exception_register_rows": [exception_row],
        "ledger_rows": [],
        "posting_ledger_entry": entry,
        "rollback_plan": dict(entry["rollback_plan"]),
        "source_evidence": {"evidence_id": "EVD-EXC-001"},
        "posting_ledger_entries": [entry],
        "live_execution_ledger": [],
        "config_profile": {"name": "service"},
        "registers_checked": ["invoice_register", "match_register", "exception_register", "ledger_register", "posting_ledger"],
        "report_paths": {},
    }


def test_exception_invoice_reconciles_with_manual_review_flag(tmp_path) -> None:
    result = build_invoiceops_reconciliation_result(_exception_plan(), runtime_data_dir=tmp_path, profile="service", fixture_mode=True, write_report=True)

    assert result["status"] == "MANUAL_REVIEW_REQUIRED"
    assert result["ok"] is False
    assert any(check["section"] == "exception_register" and check["ok"] for check in result["checks"])
    assert any(check["section"] == "posting_ledger" for check in result["checks"])
    assert result["report_paths"]["json"].endswith("_reconciliation.json")

