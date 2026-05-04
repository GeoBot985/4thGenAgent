from src.operator_scenario_runner import run_scenario


def test_procurement_approve_execute_dry_run_scenario_passes():
    result = run_scenario("procurement_low_stock_approve_execute_dry_run", runtime_data_dir="runtime_data", reset_dataset=True)
    assert result["ok"] is True
    assert result["state"] == "COMPLETED"
    assert result["scenario_validation"]["verdict"] == "PASS"


def test_procurement_report_generation_scenario_passes():
    result = run_scenario("procurement_low_stock_report_generation", runtime_data_dir="runtime_data", reset_dataset=True, generate_report=True)
    assert result["ok"] is True
    assert result["report_result"]["ok"] is True
    assert result["scenario_validation"]["verdict"] == "PASS"
