from __future__ import annotations

from src.operator_scenario_runner import run_scenario


def test_supplier_invoice_manifest_happy_path_waits_for_execute():
    result = run_scenario(
        "supplier_invoice_match_happy_path",
        runtime_data_dir="runtime_data",
        use_local_llm=False,
        allow_test_fake_llm=True,
    )
    assert result["state"] == "WAITING_FOR_EXECUTE"
    assert result["match_status"] == "matched"
    assert result["exception_count"] == 0
    assert len(result["pending_actions"]) == 2


def test_supplier_invoice_manifest_price_exception_waits_for_execute_without_ledger():
    result = run_scenario(
        "supplier_invoice_match_price_exception",
        runtime_data_dir="runtime_data",
        use_local_llm=False,
        allow_test_fake_llm=True,
    )
    assert result["state"] == "WAITING_FOR_EXECUTE"
    assert result["match_status"] == "exception"
    assert len(result["pending_actions"]) == 1
    assert result["ledger_decision"] == "exception_only"


def test_supplier_invoice_manifest_missing_po_fails_validation():
    result = run_scenario(
        "supplier_invoice_match_missing_po",
        runtime_data_dir="runtime_data",
        use_local_llm=False,
        allow_test_fake_llm=True,
    )
    assert result["state"] == "WAITING_FOR_EXECUTE"
    assert result["match_status"] == "exception"
    assert result["po_ref"] == "PO-9999"


def test_supplier_invoice_manifest_approve_execute_dry_run_completes():
    result = run_scenario(
        "supplier_invoice_match_approve_execute_dry_run",
        runtime_data_dir="runtime_data",
        use_local_llm=False,
        allow_test_fake_llm=True,
    )
    assert result["state"] == "COMPLETED"
    assert len(result["snapshot"]["executed_actions"]) == 2
    assert any(action.get("tool") == "supplier_invoice/execute_ledger_write" for action in result["snapshot"]["executed_actions"])
