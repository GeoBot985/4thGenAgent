from __future__ import annotations

import tempfile
from pathlib import Path

from runtime.run_report import generate_demo_run_report
from src.operator_scenario_runner import run_scenario
from src.operator_scenarios import get_scenario


def test_supplier_invoice_report_generation():
    result = run_scenario(
        "supplier_invoice_match_report_generation",
        runtime_data_dir="runtime_data",
        use_local_llm=False,
        allow_test_fake_llm=True,
    )
    report = result["report_result"]
    assert report["ok"] is True
    assert Path(report["markdown_path"]).is_file()
    assert Path(report["html_path"]).is_file()
    assert Path(report["evidence_bundle_path"]).is_file()


def test_supplier_invoice_report_contains_dedicated_section():
    result = run_scenario(
        "supplier_invoice_match_report_generation",
        runtime_data_dir="runtime_data",
        use_local_llm=False,
        allow_test_fake_llm=True,
    )
    report = generate_demo_run_report("runtime_data", result["frame_id"], scenario=get_scenario("supplier_invoice_match_report_generation"))
    markdown = Path(report["business_report_markdown_path"]).read_text(encoding="utf-8")
    assert "Supplier Invoice Matching Result" in markdown
    assert "Ledger Posting Decision" in markdown
    assert "Evidence" in markdown


def test_supplier_invoice_workflow_does_not_add_domain_logic_to_orchestrator():
    text = Path("runtime/orchestrator.py").read_text(encoding="utf-8")
    assert "supplier_invoice_match" not in text or "supplier invoice" not in text.lower()
