from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import src.operator_cross_workflow_demo as cross_demo


class CrossWorkflowDemoReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_cross_workflow_aggregate_report_is_created(self):
        result = self._run_happy_path()
        self.assertTrue(Path(result["aggregate_report"]["markdown_path"]).is_file())
        self.assertTrue(Path(result["aggregate_report"]["html_path"]).is_file())
        self.assertTrue(Path(result["aggregate_report"]["summary_json_path"]).is_file())

    def test_cross_workflow_aggregate_report_contains_three_workflows(self):
        result = self._run_happy_path()
        markdown = Path(result["aggregate_report"]["markdown_path"]).read_text(encoding="utf-8")
        self.assertIn("Workflow 1", markdown)
        self.assertIn("Workflow 2", markdown)
        self.assertIn("Workflow 3", markdown)

    def test_cross_workflow_aggregate_report_contains_frame_ids(self):
        result = self._run_happy_path()
        markdown = Path(result["aggregate_report"]["markdown_path"]).read_text(encoding="utf-8")
        self.assertIn("frame-customer_status_approve_execute_dry_run", markdown)
        self.assertIn("frame-procurement_low_stock_approve_execute_dry_run", markdown)
        self.assertIn("frame-accounting_payment_reconciliation_approve_execute_dry_run", markdown)

    def test_cross_workflow_aggregate_report_contains_manifest_ids(self):
        result = self._run_happy_path()
        markdown = Path(result["aggregate_report"]["markdown_path"]).read_text(encoding="utf-8")
        self.assertIn("customer.message_status_check", markdown)
        self.assertIn("procurement.low_stock_reorder", markdown)
        self.assertIn("accounting.payment_reconciliation", markdown)

    def test_cross_workflow_aggregate_report_contains_dry_run_statement(self):
        result = self._run_happy_path()
        markdown = Path(result["aggregate_report"]["markdown_path"]).read_text(encoding="utf-8").lower()
        self.assertIn("dry-run", markdown)

    def test_cross_workflow_aggregate_report_links_individual_reports(self):
        result = self._run_happy_path()
        markdown = Path(result["aggregate_report"]["markdown_path"]).read_text(encoding="utf-8")
        self.assertIn("customer_status_approve_execute_dry_run.md", markdown)
        self.assertIn("procurement_low_stock_approve_execute_dry_run.md", markdown)
        self.assertIn("accounting_payment_reconciliation_approve_execute_dry_run.md", markdown)

    def test_cross_workflow_summary_json_is_created(self):
        result = self._run_happy_path()
        summary_path = Path(result["aggregate_report"]["summary_json_path"])
        self.assertTrue(summary_path.is_file())
        summary = summary_path.read_text(encoding="utf-8")
        self.assertIn("cross_workflow_business_demo_v1", summary)

    def _run_happy_path(self) -> dict:
        def fake_run_scenario(scenario_id: str, **kwargs) -> dict:
            manifest_id = {
                "customer_status_approve_execute_dry_run": "customer.message_status_check",
                "procurement_low_stock_approve_execute_dry_run": "procurement.low_stock_reorder",
                "accounting_payment_reconciliation_approve_execute_dry_run": "accounting.payment_reconciliation",
            }[scenario_id]
            return {
                "ok": True,
                "frame_id": f"frame-{scenario_id}",
                "manifest_id": manifest_id,
                "state": "COMPLETED",
                "snapshot": {"pending_actions": [], "executed_actions": [], "summary": {}, "llm_calls": [], "tool_calls": []},
                "summary": {"llm_calls": [{"action": "demo"}], "tool_calls": [{"tool": "demo"}]},
                "report_result": {"ok": True, "markdown_path": f"{scenario_id}.md", "html_path": f"{scenario_id}.html", "evidence_bundle_path": f"{scenario_id}.json"},
                "failure_summary": {},
                "scenario_validation": {"verdict": "PASS", "checks": []},
                "error": "",
            }

        original_run_scenario = cross_demo.run_scenario
        original_preflight = cross_demo.check_llm_available
        try:
            cross_demo.run_scenario = fake_run_scenario  # type: ignore[assignment]
            cross_demo.check_llm_available = lambda provider="ollama", model="granite3.3:8b": {"ok": True, "provider": provider, "model": model, "error": ""}  # type: ignore[assignment]
            return cross_demo.run_cross_workflow_demo_pack(runtime_data_dir=str(self.runtime_dir), skip_llm_preflight=False)
        finally:
            cross_demo.run_scenario = original_run_scenario  # type: ignore[assignment]
            cross_demo.check_llm_available = original_preflight  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
