from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.persistence import load_taskframe_dict
from src.operator_demo_runner import run_demo_manifest
from src.operator_reports import generate_report_for_frame


class OperatorRunReportTests(unittest.TestCase):
    def test_generate_operator_run_report_creates_markdown_html_and_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            self.assertTrue(report["ok"])
            self.assertTrue(Path(report["markdown_path"]).is_file())
            self.assertTrue(Path(report["html_path"]).is_file())
            self.assertTrue(Path(report["evidence_bundle_path"]).is_file())

    def test_run_report_markdown_contains_required_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            text = Path(report["markdown_path"]).read_text(encoding="utf-8")
            for section in ("# TaskFrame Run Report", "Executive Summary", "Trigger / Event", "Route and Manifest", "Step Timeline", "LLM Calls", "Tool Calls", "Outputs", "Evidence", "Validations", "Approval / Side-Effect Status", "Failure Summary", "Artifact Index"):
                self.assertIn(section, text)

    def test_run_report_for_staged_action_contains_approval_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            text = Path(report["markdown_path"]).read_text(encoding="utf-8")
            for section in ("Pending Action", "Human Summary", "Risk", "Requires Approval"):
                self.assertIn(section, text)

    def test_run_report_for_failed_run_contains_failure_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_wrong_customer_order", runtime_data_dir=tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            text = Path(report["markdown_path"]).read_text(encoding="utf-8")
            for section in ("Failure Summary", "failed_step_id", "failure_message", "FAILED"):
                self.assertIn(section, text)

    def test_run_report_html_is_valid_basic_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            text = Path(report["html_path"]).read_text(encoding="utf-8").lower()
            for section in ("<!doctype html>", "<html", "</html>", "taskframe run report"):
                self.assertIn(section, text)

    def test_run_report_does_not_mutate_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            before = load_taskframe_dict(result["frame_id"], tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            after = load_taskframe_dict(result["frame_id"], tmp)
            self.assertEqual(before.get("state"), after.get("state"))
            self.assertEqual(before.get("pending_actions"), after.get("pending_actions"))
            self.assertEqual(before.get("executed_actions"), after.get("executed_actions"))
            self.assertEqual(before.get("outputs"), after.get("outputs"))


if __name__ == "__main__":
    unittest.main()
