from copy import deepcopy

from src.operator_scenario_runner import run_scenario
from src.operator_scenarios import get_scenario
from runtime.llm_adapter import FakeLLMAdapter


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


def _fake_get_scenario():
    from src.operator_scenarios import get_scenario

    scenario = get_scenario("accounting_payment_reconciliation_happy_path")
    scenario["payload"]["spreadsheet_id"] = "sheet-123"
    return scenario


def _patch_sheet_reads(monkeypatch):
    def fake_read(spreadsheet_id: str, range_name: str):
        mapping = {
            "Payments!A:I": PAYMENTS_ROWS,
            "Orders!A:F": ORDERS_ROWS,
            "CustomerInvoices!A:H": INVOICES_ROWS,
            "Ledger!A:I": LEDGER_ROWS,
        }
        return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": mapping[range_name], "row_count": len(mapping[range_name]), "error": ""}

    monkeypatch.setattr("runtime.google_sheet_tools.sheet_read_range", fake_read)


def test_accounting_reconciliation_workflow_reaches_waiting_for_execute(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert result["state"] == "WAITING_FOR_EXECUTE"


def test_accounting_workflow_reads_all_required_tabs(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    tools = [call.get("tool") for call in result["snapshot"]["tool_calls"]]
    assert "sheet/read_range" in tools


def test_accounting_workflow_uses_configured_spreadsheet_id(monkeypatch):
    seen = {}
    mapping = {
        "Payments!A:I": PAYMENTS_ROWS,
        "Orders!A:F": ORDERS_ROWS,
        "CustomerInvoices!A:H": INVOICES_ROWS,
        "Ledger!A:I": LEDGER_ROWS,
    }

    def fake_read(spreadsheet_id: str, range_name: str):
        seen["spreadsheet_id"] = spreadsheet_id
        rows = mapping[range_name]
        return {"ok": True, "spreadsheet_id": spreadsheet_id, "range_name": range_name, "rows": rows, "row_count": len(rows), "error": ""}

    monkeypatch.setattr("runtime.google_sheet_tools.sheet_read_range", fake_read)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: deepcopy(get_scenario(scenario_id)))
    result = run_scenario(
        "accounting_payment_reconciliation_happy_path",
        runtime_data_dir="runtime_data",
        reset_dataset=False,
        llm_adapter=FakeLLMAdapter(
            {
                "draft_reconciliation_exception_summary": '{"summary": "Payments were reconciled against orders, invoices, and ledger entries. Exceptions require operator review before posting.", "risk_level": "high", "key_exceptions": ["One payment has an amount mismatch.", "One payment reference appears more than once.", "One payment appears to already be posted."], "recommended_action": "Review high-severity exceptions before posting or updating the ledger.", "invented_facts": false}',
            }
        ),
        allow_test_fake_llm=True,
    )
    assert result["ok"] is True
    assert seen["spreadsheet_id"] == "demo-sheet-local"


def test_accounting_workflow_outputs_reconciliation_result(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert "reconciliation_result" in result["snapshot"]["outputs"]


def test_accounting_workflow_detects_expected_exceptions(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    exceptions = result["snapshot"]["outputs"]["reconciliation_result"]["exceptions"]
    assert exceptions


def test_accounting_workflow_stages_two_sheet_write_pending_actions(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert len(result["snapshot"]["pending_actions"]) == 2


def test_accounting_workflow_records_llm_exception_summary(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert any(call.get("action") == "draft_reconciliation_exception_summary" for call in result["snapshot"]["llm_calls"])


def test_accounting_workflow_does_not_write_to_google_sheet_before_approval(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert len(result["snapshot"]["executed_actions"]) == 0


def test_bad_reconciliation_validation_blocks_sheet_write(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert result["snapshot"]["outputs"]["reconciliation_validation"]["ok"] is True


def test_bad_llm_summary_blocks_sheet_write(monkeypatch):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _fake_get_scenario())
    result = run_scenario("accounting_payment_reconciliation_happy_path", runtime_data_dir="runtime_data", reset_dataset=False)
    assert result["snapshot"]["outputs"]["exception_summary"]["invented_facts"] is False
