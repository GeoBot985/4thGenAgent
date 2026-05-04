from __future__ import annotations

from pathlib import Path

from src.operator_scenario_runner import run_scenario

from tests.test_accounting_approval_dry_run import _fake_adapter, _scenario_by_id, _patch_sheet_reads


def test_accounting_approve_execute_dry_run_scenario_passes(monkeypatch, tmp_path):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _scenario_by_id(scenario_id))
    result = run_scenario(
        "accounting_payment_reconciliation_approve_execute_dry_run",
        runtime_data_dir=str(tmp_path),
        reset_dataset=False,
        llm_adapter=_fake_adapter(),
        allow_test_fake_llm=True,
    )
    assert result["ok"] is True
    assert result["state"] == "COMPLETED"
    assert result["scenario_validation"]["verdict"] == "PASS"


def test_accounting_report_generation_scenario_passes(monkeypatch, tmp_path):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _scenario_by_id(scenario_id))
    result = run_scenario(
        "accounting_payment_reconciliation_report_generation",
        runtime_data_dir=str(tmp_path),
        reset_dataset=False,
        generate_report=True,
        llm_adapter=_fake_adapter(),
        allow_test_fake_llm=True,
    )
    assert result["ok"] is True
    assert result["report_result"]["ok"] is True
    assert result["scenario_validation"]["verdict"] == "PASS"
