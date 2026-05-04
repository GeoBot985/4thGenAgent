from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.operator_scenario_runner import run_scenario


class DemoScenarioRunnerTests(unittest.TestCase):
    def test_run_customer_status_happy_path_scenario_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scenario("customer_status_happy_path", runtime_data_dir=tmp, reset_dataset=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"], "WAITING_FOR_EXECUTE")
            self.assertEqual(result["scenario_validation"]["verdict"], "PASS")
            self.assertEqual(result["approval_pack"]["pending_action_count"], 1)

    def test_run_wrong_customer_scenario_passes_as_negative_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scenario("customer_status_wrong_customer_order", runtime_data_dir=tmp, reset_dataset=True)
            self.assertTrue(result["ok"])
            self.assertTrue(str(result["state"]).startswith("FAILED"))
            self.assertEqual(result["scenario_validation"]["verdict"], "PASS")
            self.assertEqual(result["approval_pack"]["pending_action_count"], 0)

    def test_run_approve_execute_dry_run_scenario_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scenario("customer_status_approve_execute_dry_run", runtime_data_dir=tmp, reset_dataset=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"], "COMPLETED")
            self.assertEqual(result["scenario_validation"]["verdict"], "PASS")
            self.assertEqual(result["snapshot"]["executed_actions"][0]["status"], "EXECUTED")

    def test_run_report_generation_scenario_creates_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scenario("report_generation_happy_path", runtime_data_dir=tmp, reset_dataset=True, generate_report=True)
            self.assertTrue(result["report_result"]["ok"])
            self.assertTrue(Path(result["report_result"]["markdown_path"]).is_file())

    def test_run_dataset_validation_scenario_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scenario("dataset_validation_seed_ok", runtime_data_dir=tmp, reset_dataset=True)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dataset_validation"]["ok"])
            self.assertEqual(result["scenario_validation"]["verdict"], "PASS")

    def test_unknown_scenario_returns_error_shape(self):
        result = run_scenario("missing", runtime_data_dir="runtime_data")
        self.assertFalse(result["ok"])
        self.assertNotEqual(result["error"], "")

    def test_scenario_runner_always_uses_dry_run_true(self):
        seen = []

        def fake_handle(event, dry_run=True):
            seen.append(dry_run)
            raise RuntimeError("stop")

        with patch("runtime.runtime_engine.RuntimeEngine.handle_event", side_effect=fake_handle):
            run_scenario("customer_status_happy_path", runtime_data_dir="runtime_data", reset_dataset=True)
        self.assertTrue(seen)
        self.assertTrue(all(seen))

    def test_scenario_runner_does_not_expose_live_execution(self):
        from src import operator_scenario_runner as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        for text in ("dry_run=False", "execute_live_approved", "confirm_live", "approve_and_execute"):
            self.assertNotIn(text, source)


if __name__ == "__main__":
    unittest.main()
