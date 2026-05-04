from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import src.operator_cross_workflow_demo as cross_demo


class CrossWorkflowDemoPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_cross_workflow_pack_definition_lists_three_lanes(self):
        pack = cross_demo.get_demo_pack("cross_workflow_business_demo_v1")
        self.assertEqual(len(pack["workflow_sequence"]), 3)
        self.assertEqual([item["lane"] for item in pack["workflow_sequence"]], ["customer_support", "procurement", "accounting"])

    def test_cross_workflow_pack_runs_customer_procurement_accounting_in_order(self):
        calls: list[str] = []

        def fake_preflight(provider: str = "ollama", model: str = "granite3.3:8b") -> dict:
            return {"ok": True, "provider": provider, "model": model, "error": ""}

        def fake_run_scenario(scenario_id: str, **kwargs) -> dict:
            calls.append(scenario_id)
            return {
                "ok": True,
                "frame_id": f"frame-{scenario_id}",
                "manifest_id": scenario_id.replace("_approve_execute_dry_run", "").replace("customer_status", "customer.message_status_check").replace("procurement_low_stock", "procurement.low_stock_reorder").replace("accounting_payment_reconciliation", "accounting.payment_reconciliation"),
                "state": "COMPLETED",
                "snapshot": {"pending_actions": [], "executed_actions": [], "summary": {}, "llm_calls": [], "tool_calls": []},
                "summary": {"llm_calls": [], "tool_calls": []},
                "report_result": {"ok": True, "markdown_path": f"{scenario_id}.md", "html_path": f"{scenario_id}.html", "evidence_bundle_path": f"{scenario_id}.json"},
                "failure_summary": {},
                "scenario_validation": {"verdict": "PASS", "checks": []},
                "error": "",
            }

        original_preflight = cross_demo.check_llm_available
        original_run_scenario = cross_demo.run_scenario
        try:
            cross_demo.check_llm_available = fake_preflight  # type: ignore[assignment]
            cross_demo.run_scenario = fake_run_scenario  # type: ignore[assignment]
            result = cross_demo.run_cross_workflow_demo_pack(runtime_data_dir=str(self.runtime_dir), skip_llm_preflight=False)
        finally:
            cross_demo.check_llm_available = original_preflight  # type: ignore[assignment]
            cross_demo.run_scenario = original_run_scenario  # type: ignore[assignment]

        self.assertTrue(result["ok"])
        self.assertEqual(calls, [
            "customer_status_approve_execute_dry_run",
            "procurement_low_stock_approve_execute_dry_run",
            "accounting_payment_reconciliation_approve_execute_dry_run",
        ])
        self.assertEqual(result["summary"]["workflow_count"], 3)
        self.assertEqual(result["summary"]["completed_count"], 3)
        self.assertEqual(result["summary"]["failed_count"], 0)

    def test_cross_workflow_pack_stops_on_failure(self):
        calls: list[str] = []

        def fake_preflight(provider: str = "ollama", model: str = "granite3.3:8b") -> dict:
            return {"ok": True, "provider": provider, "model": model, "error": ""}

        def fake_run_scenario(scenario_id: str, **kwargs) -> dict:
            calls.append(scenario_id)
            if scenario_id == "procurement_low_stock_approve_execute_dry_run":
                return {
                    "ok": False,
                    "frame_id": "frame-failed",
                    "manifest_id": "procurement.low_stock_reorder",
                    "state": "FAILED_VALIDATION",
                    "snapshot": {"pending_actions": [], "executed_actions": [], "summary": {}, "llm_calls": [], "tool_calls": []},
                    "summary": {},
                    "report_result": {},
                    "failure_summary": {"failure_message": "blocked"},
                    "scenario_validation": {"verdict": "FAIL", "checks": []},
                    "error": "blocked",
                }
            return {
                "ok": True,
                "frame_id": f"frame-{scenario_id}",
                "manifest_id": scenario_id,
                "state": "COMPLETED",
                "snapshot": {"pending_actions": [], "executed_actions": [], "summary": {}, "llm_calls": [], "tool_calls": []},
                "summary": {"llm_calls": [], "tool_calls": []},
                "report_result": {"ok": True, "markdown_path": f"{scenario_id}.md", "html_path": f"{scenario_id}.html", "evidence_bundle_path": f"{scenario_id}.json"},
                "failure_summary": {},
                "scenario_validation": {"verdict": "PASS", "checks": []},
                "error": "",
            }

        original_preflight = cross_demo.check_llm_available
        original_run_scenario = cross_demo.run_scenario
        try:
            cross_demo.check_llm_available = fake_preflight  # type: ignore[assignment]
            cross_demo.run_scenario = fake_run_scenario  # type: ignore[assignment]
            result = cross_demo.run_cross_workflow_demo_pack(runtime_data_dir=str(self.runtime_dir), skip_llm_preflight=False)
        finally:
            cross_demo.check_llm_available = original_preflight  # type: ignore[assignment]
            cross_demo.run_scenario = original_run_scenario  # type: ignore[assignment]

        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_lane"], "procurement")
        self.assertEqual(calls, [
            "customer_status_approve_execute_dry_run",
            "procurement_low_stock_approve_execute_dry_run",
        ])
        self.assertEqual(result["summary"]["completed_count"], 1)
        self.assertEqual(result["summary"]["failed_count"], 1)
        self.assertEqual(result["summary"]["not_run_count"], 1)

    def test_cross_workflow_pack_result_contains_frame_ids(self):
        result = self._run_happy_path()
        frame_ids = [item["frame_id"] for item in result["workflow_results"]]
        self.assertTrue(all(frame_ids))

    def test_cross_workflow_pack_result_contains_manifest_ids(self):
        result = self._run_happy_path()
        manifest_ids = [item["manifest_id"] for item in result["workflow_results"]]
        self.assertIn("customer.message_status_check", manifest_ids[0])
        self.assertIn("procurement.low_stock_reorder", manifest_ids[1])
        self.assertIn("accounting.payment_reconciliation", manifest_ids[2])

    def test_cross_workflow_pack_result_contains_summary_counts(self):
        result = self._run_happy_path()
        self.assertEqual(result["summary"]["workflow_count"], 3)
        self.assertEqual(result["summary"]["completed_count"], 3)
        self.assertEqual(result["summary"]["failed_count"], 0)
        self.assertEqual(result["summary"]["not_run_count"], 0)

    def test_cross_workflow_pack_enforces_dry_run_only(self):
        result = self._run_happy_path()
        self.assertTrue(result["dry_run_only"])

    def test_cross_workflow_pack_requires_real_llm_by_default(self):
        pack = cross_demo.get_demo_pack("cross_workflow_business_demo_v1")
        self.assertTrue(pack["requires_real_llm"])

    def test_cross_workflow_pack_allows_fake_llm_only_when_test_flag_enabled(self):
        result = self._run_happy_path(allow_test_fake_llm=True, skip_llm_preflight=True)
        self.assertTrue(result["ok"])

    def test_cross_workflow_pack_fails_preflight_when_llm_unavailable(self):
        def fake_preflight(provider: str = "ollama", model: str = "granite3.3:8b") -> dict:
            return {"ok": False, "provider": provider, "model": model, "error": "Ollama model unavailable."}

        original_preflight = cross_demo.check_llm_available
        try:
            cross_demo.check_llm_available = fake_preflight  # type: ignore[assignment]
            result = cross_demo.run_cross_workflow_demo_pack(runtime_data_dir=str(self.runtime_dir), skip_llm_preflight=False)
        finally:
            cross_demo.check_llm_available = original_preflight  # type: ignore[assignment]
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_lane"], "preflight")

    def _run_happy_path(self, allow_test_fake_llm: bool = False, skip_llm_preflight: bool = True) -> dict:
        def fake_run_scenario(scenario_id: str, **kwargs) -> dict:
            return {
                "ok": True,
                "frame_id": f"frame-{scenario_id}",
                "manifest_id": {
                    "customer_status_approve_execute_dry_run": "customer.message_status_check",
                    "procurement_low_stock_approve_execute_dry_run": "procurement.low_stock_reorder",
                    "accounting_payment_reconciliation_approve_execute_dry_run": "accounting.payment_reconciliation",
                }[scenario_id],
                "state": "COMPLETED",
                "snapshot": {"pending_actions": [], "executed_actions": [], "summary": {}, "llm_calls": [], "tool_calls": []},
                "summary": {"llm_calls": [], "tool_calls": []},
                "report_result": {"ok": True, "markdown_path": f"{scenario_id}.md", "html_path": f"{scenario_id}.html", "evidence_bundle_path": f"{scenario_id}.json"},
                "failure_summary": {},
                "scenario_validation": {"verdict": "PASS", "checks": []},
                "error": "",
            }

        original_run_scenario = cross_demo.run_scenario
        try:
            cross_demo.run_scenario = fake_run_scenario  # type: ignore[assignment]
            return cross_demo.run_cross_workflow_demo_pack(
                runtime_data_dir=str(self.runtime_dir),
                skip_llm_preflight=skip_llm_preflight,
                allow_test_fake_llm=allow_test_fake_llm,
            )
        finally:
            cross_demo.run_scenario = original_run_scenario  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
