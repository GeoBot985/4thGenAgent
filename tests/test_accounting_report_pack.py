from __future__ import annotations

from pathlib import Path

from src.operator_scenario_runner import run_scenario

from tests.test_accounting_approval_dry_run import _fake_adapter, _scenario_by_id, _patch_sheet_reads


def test_accounting_report_generation_creates_markdown_html_and_evidence_bundle(monkeypatch, tmp_path):
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
    assert result["report_result"]["ok"] is True
    assert Path(result["report_result"]["markdown_path"]).is_file()
    assert Path(result["report_result"]["html_path"]).is_file()
    assert Path(result["report_result"]["evidence_bundle_path"]).is_file()


def test_accounting_report_contains_manifest_id(monkeypatch, tmp_path):
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
    markdown = Path(result["report_result"]["markdown_path"]).read_text(encoding="utf-8")
    assert "accounting.payment_reconciliation" in markdown


def test_accounting_report_contains_recon_run_id(monkeypatch, tmp_path):
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
    markdown = Path(result["report_result"]["markdown_path"]).read_text(encoding="utf-8")
    assert "RECON-" in markdown


def test_accounting_report_contains_exception_count(monkeypatch, tmp_path):
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
    markdown = Path(result["report_result"]["markdown_path"]).read_text(encoding="utf-8")
    assert "exception_count" in markdown or "Exception" in markdown


def test_accounting_report_contains_llm_exception_summary(monkeypatch, tmp_path):
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
    bundle_text = Path(result["report_result"]["evidence_bundle_path"]).read_text(encoding="utf-8")
    assert "exception_summary" in bundle_text


def test_accounting_report_contains_pending_sheet_writes(monkeypatch, tmp_path):
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
    bundle_text = Path(result["report_result"]["evidence_bundle_path"]).read_text(encoding="utf-8")
    assert "pending_actions" in bundle_text


def test_accounting_report_contains_executed_sheet_writes_after_dry_run(monkeypatch, tmp_path):
    _patch_sheet_reads(monkeypatch)
    monkeypatch.setattr("src.operator_scenario_runner.get_scenario", lambda scenario_id: _scenario_by_id(scenario_id))
    result = run_scenario(
        "accounting_payment_reconciliation_approve_execute_dry_run",
        runtime_data_dir=str(tmp_path),
        reset_dataset=False,
        generate_report=True,
        llm_adapter=_fake_adapter(),
        allow_test_fake_llm=True,
    )
    assert result["state"] == "COMPLETED"
    bundle_text = Path(result["report_result"]["evidence_bundle_path"]).read_text(encoding="utf-8")
    assert "executed_actions" in bundle_text


def test_accounting_evidence_bundle_contains_outputs_tool_calls_llm_calls_actions(monkeypatch, tmp_path):
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
    bundle_text = Path(result["report_result"]["evidence_bundle_path"]).read_text(encoding="utf-8")
    assert "outputs" in bundle_text
    assert "tool_calls" in bundle_text
    assert "llm_calls" in bundle_text
    assert "pending_actions" in bundle_text
    assert "executed_actions" in bundle_text
