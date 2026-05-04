from __future__ import annotations

import tempfile
from pathlib import Path

from runtime.events import create_event
from runtime.llm_adapter import FakeLLMAdapter
from runtime.persistence import load_taskframe_dict
from runtime.runtime_engine import RuntimeEngine


PAYMENTS_ROWS = [
    ["payment_id", "payment_ref", "order_ref", "customer_id", "amount", "currency", "payment_date", "status", "source"],
    ["PAY-1001", "EFT-9001", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1002", "EFT-9002", "ORD-10043", "CUST-1002", "450.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1003", "EFT-9003", "ORD-10044", "CUST-1003", "300.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1004", "EFT-9005", "ORD-10045", "CUST-1004", "500.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1005", "EFT-9005", "ORD-10046", "CUST-1005", "250.00", "ZAR", "2026-05-04", "received", "bank"],
]

ORDERS_ROWS = [
    ["order_ref", "customer_id", "order_total", "currency", "order_status", "invoice_id"],
    ["ORD-10042", "CUST-1001", "1250.00", "ZAR", "invoiced", "INV-10042"],
    ["ORD-10043", "CUST-1002", "500.00", "ZAR", "invoiced", "INV-10043"],
    ["ORD-10044", "CUST-1003", "300.00", "ZAR", "invoiced", "INV-10044"],
    ["ORD-10045", "CUST-1004", "500.00", "ZAR", "invoiced", "INV-10045"],
    ["ORD-10046", "CUST-1005", "250.00", "ZAR", "invoiced", "INV-10046"],
]

INVOICES_ROWS = [
    ["invoice_id", "order_ref", "customer_id", "invoice_total", "currency", "invoice_status", "issued_date", "due_date"],
    ["INV-10042", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10043", "ORD-10043", "CUST-1002", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10044", "ORD-10044", "CUST-1003", "300.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10045", "ORD-10045", "CUST-1004", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10046", "ORD-10046", "CUST-1005", "250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
]

LEDGER_ROWS = [
    ["ledger_entry_id", "source_type", "source_ref", "debit_account", "credit_account", "amount", "currency", "posted_date", "status"],
    ["LED-1001", "payment", "EFT-9001", "bank", "revenue", "1250.00", "ZAR", "2026-05-04", "posted"],
]


def _patch_sheet_reads(monkeypatch):
    def fake_read(spreadsheet_id: str, range_name: str):
        mapping = {
            "Payments!A:I": PAYMENTS_ROWS,
            "Orders!A:F": ORDERS_ROWS,
            "CustomerInvoices!A:H": INVOICES_ROWS,
            "Ledger!A:I": LEDGER_ROWS,
        }
        rows = mapping[range_name]
        return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": rows, "row_count": len(rows), "error": ""}

    monkeypatch.setattr("runtime.google_sheet_tools.sheet_read_range", fake_read)


def _fake_scenario():
    from src.operator_scenarios import get_scenario

    scenario = get_scenario("accounting_payment_reconciliation_happy_path")
    scenario["payload"]["spreadsheet_id"] = "sheet-123"
    return scenario


def _scenario_by_id(scenario_id: str):
    from src.operator_scenarios import get_scenario

    scenario = get_scenario(scenario_id)
    scenario["payload"]["spreadsheet_id"] = "sheet-123"
    return scenario


def _fake_adapter() -> FakeLLMAdapter:
    return FakeLLMAdapter(
        {
            "draft_reconciliation_exception_summary": '{"summary": "Payments were reconciled against orders, invoices, and ledger entries. Exceptions require operator review before posting.", "risk_level": "high", "key_exceptions": ["One payment has an amount mismatch.", "One payment reference appears more than once.", "One payment appears to already be posted."], "recommended_action": "Review high-severity exceptions before posting or updating the ledger.", "invented_facts": false}',
        }
    )


def _run_happy_path(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_scenario())
    from src.operator_scenario_runner import run_scenario

    return run_scenario(
        "accounting_payment_reconciliation_happy_path",
        runtime_data_dir="runtime_data",
        reset_dataset=False,
        llm_adapter=_fake_adapter(),
        allow_test_fake_llm=True,
    )


def test_accounting_pending_sheet_writes_can_all_be_approved(monkeypatch):
    result = _run_happy_path(monkeypatch)
    assert result["state"] == "WAITING_FOR_EXECUTE"
    frame_id = result["frame_id"]
    from src.operator_approval_actions import approve_all_pending_actions_command

    approve = approve_all_pending_actions_command(frame_id, approved_by="pytest", runtime_data_dir="runtime_data")
    assert approve["ok"] is True
    assert approve["approved_count"] == 2


def test_accounting_approved_sheet_writes_execute_dry_run(monkeypatch):
    from src.operator_approval_actions import approve_all_pending_actions_command, execute_approved_pending_actions_dry_run

    result = _run_happy_path(monkeypatch)
    frame_id = result["frame_id"]
    approve_result = approve_all_pending_actions_command(frame_id, runtime_data_dir="runtime_data")
    assert approve_result["ok"] is True
    execute_result = execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir="runtime_data")
    assert execute_result["ok"] is True


def test_accounting_approve_execute_reaches_completed(monkeypatch):
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _scenario_by_id(scenario_id))
    _patch_sheet_reads(monkeypatch)
    from src.operator_scenario_runner import run_scenario
    result = run_scenario(
        "accounting_payment_reconciliation_approve_execute_dry_run",
        runtime_data_dir="runtime_data",
        reset_dataset=False,
        llm_adapter=_fake_adapter(),
        allow_test_fake_llm=True,
    )
    assert result["state"] == "COMPLETED"
    frame = load_taskframe_dict(result["frame_id"])
    assert frame["state"] == "COMPLETED"


def test_accounting_dry_run_records_two_executed_actions(monkeypatch):
    from src.operator_approval_actions import approve_all_pending_actions_command, execute_approved_pending_actions_dry_run

    result = _run_happy_path(monkeypatch)
    frame_id = result["frame_id"]
    approve_all_pending_actions_command(frame_id, runtime_data_dir="runtime_data")
    execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir="runtime_data")
    frame = load_taskframe_dict(frame_id)
    assert len(frame["executed_actions"]) == 2
    assert all(action["tool"] == "sheet/write_rows" for action in frame["executed_actions"])


def test_accounting_dry_run_does_not_write_to_google_sheet(monkeypatch):
    from src.operator_approval_actions import approve_all_pending_actions_command, execute_approved_pending_actions_dry_run

    result = _run_happy_path(monkeypatch)
    frame_id = result["frame_id"]
    approve_all_pending_actions_command(frame_id, runtime_data_dir="runtime_data")
    execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir="runtime_data")
    frame = load_taskframe_dict(frame_id)
    assert frame["outputs"]["recon_run_write"]["written"] is False
    assert frame["outputs"]["recon_exception_write"]["written"] is False


def test_sheet_write_rows_live_mode_is_blocked(monkeypatch):
    from runtime.google_sheet_tools import sheet_write_rows

    result = sheet_write_rows("sheet-123", "ReconRuns!A:J", [["a"]], dry_run=False)
    assert result["ok"] is False
    assert result["error"]


def test_accounting_execute_requires_approved_actions(monkeypatch):
    from src.operator_approval_actions import execute_approved_pending_actions_dry_run

    result = _run_happy_path(monkeypatch)
    frame_id = result["frame_id"]
    execute_result = execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir="runtime_data")
    assert execute_result["ok"] is False
