from __future__ import annotations

import importlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.events import intake_and_run_event as runtime_intake_and_run_event
from runtime.persistence import load_taskframe_dict

from src import operator_actions
from src.operator_data import build_operator_snapshot
from src.operator_reports import generate_report_for_frame
from src.operator_demo_runner import list_demo_manifests, run_demo_manifest


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = ROOT / "src" / "operator_ui.py"
BUSINESS_SOURCE = ROOT / "runtime_data" / "business"


def seed_business_data(runtime_root: Path) -> None:
    target = runtime_root / "business"
    shutil.copytree(BUSINESS_SOURCE, target)


class OperatorDemoExecutionTests(unittest.TestCase):
    def test_demo_runner_lists_demo_manifests(self):
        demos = list_demo_manifests()
        self.assertGreaterEqual(len(demos), 1)
        for demo in demos:
            self.assertIn("label", demo)
            self.assertIn("event_type", demo)
            self.assertIn("source", demo)
        self.assertTrue(any(demo.get("label") == "Customer Status - LLM Assisted E2E" for demo in demos))
        self.assertTrue(any("Missing Customer" in demo.get("label", "") for demo in demos))
        self.assertTrue(any("Wrong Customer/Order Pairing" in demo.get("label", "") for demo in demos))
        self.assertTrue(any("Bad LLM Reply" in demo.get("label", "") for demo in demos))
        self.assertTrue(any("Unsupported Intent" in demo.get("label", "") for demo in demos))

    def test_demo_runner_lists_negative_scenarios(self):
        demos = list_demo_manifests()
        labels = [demo.get("label", "") for demo in demos]
        self.assertTrue(any("Missing Customer" in label for label in labels))
        self.assertTrue(any("Missing Order" in label for label in labels))
        self.assertTrue(any("Wrong Customer" in label for label in labels))
        self.assertTrue(any("Bad LLM Reply" in label for label in labels))
        self.assertTrue(any("Unsupported Intent" in label for label in labels))

    def test_demo_runner_executes_customer_status_demo_dry_run(self):
        result = run_demo_manifest("customer_message_status_check")
        self.assertTrue(result["ok"])
        self.assertTrue(result["frame_id"].startswith("frame_"))
        self.assertIn(result["state"], {"COMPLETED", "COMPLETED_NO_DATA", "WAITING_FOR_EXECUTE", "FAILED_VALIDATION"})
        self.assertTrue(result["summary"])
        self.assertTrue(result["timeline"])

    def test_demo_runner_executes_customer_status_llm_e2e_fake_llm(self):
        result = run_demo_manifest("customer_status_llm_e2e")
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "WAITING_FOR_EXECUTE")
        self.assertTrue(result["approval_pack"]["pending_action_count"] == 1)
        step_ids = [item.get("step_id") for item in result["timeline"] if isinstance(item, dict)]
        self.assertIn("draft_status_reply", step_ids)
        self.assertIn("prepare_pending_send", step_ids)

    def test_demo_runner_never_uses_live_mode(self):
        from runtime.runtime_engine import RuntimeEngine

        seen = {}
        original = RuntimeEngine.handle_event

        def wrapped(self, event, dry_run=True):
            seen["dry_run"] = dry_run
            return original(self, event, dry_run=dry_run)

        with patch.object(RuntimeEngine, "handle_event", wrapped):
            run_demo_manifest("customer_message_status_check")

        self.assertTrue(seen["dry_run"])

    def test_demo_runner_failure_returns_error_shape(self):
        result = run_demo_manifest("missing-selection")
        self.assertFalse(result["ok"])
        self.assertNotEqual(result["error"], "")
        self.assertEqual(result["timeline"], [])
        self.assertEqual(result["summary"], {})

    def test_demo_runner_returns_approval_pack(self):
        result = run_demo_manifest("customer_message_status_check")
        self.assertIn("approval_pack", result)
        self.assertTrue(result["approval_pack"]["ok"])

    def test_demo_runner_negative_scenario_returns_failure_summary(self):
        result = run_demo_manifest("customer_status_wrong_customer_order")
        self.assertTrue(result["ok"])
        self.assertTrue(str(result["state"]).startswith("FAILED"))
        self.assertIn("failure_summary", result)
        self.assertNotEqual(result["failure_summary"]["failure_message"], "")
        self.assertEqual(result["approval_pack"]["pending_action_count"], 0)

    def test_staged_whatsapp_demo_returns_pending_action_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            seed_business_data(runtime_root)

            def run_in_temp_runtime(event_data):
                return runtime_intake_and_run_event(event_data, runtime_data_dir=runtime_root)

            original_intake = operator_actions.intake_and_run_event
            original_loader = operator_actions._load_frame_dict
            operator_actions.intake_and_run_event = run_in_temp_runtime
            operator_actions._load_frame_dict = lambda frame_id: load_taskframe_dict(frame_id, runtime_root)
            try:
                result = operator_actions.run_demo_customer_message(make_unique_event_id=True)
            finally:
                operator_actions.intake_and_run_event = original_intake
                operator_actions._load_frame_dict = original_loader

            self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")
            self.assertIn("pending_actions", result)
            self.assertGreaterEqual(len(result["pending_actions"]), 1)
            self.assertEqual(result["pending_actions"][0]["action_type"], "send_customer_message")
            self.assertTrue(result["pending_actions"][0]["status"] in {"PENDING_APPROVAL", "APPROVED", "EXECUTED"})
            self.assertTrue(result["pending_actions"][0].get("body"))

    def test_operator_action_adapter_imports(self):
        module = importlib.import_module("src.operator_actions")

        self.assertTrue(hasattr(module, "run_demo_customer_message"))
        self.assertTrue(hasattr(module, "load_demo_event"))

    def test_unique_demo_event_id_generated(self):
        event = operator_actions.load_demo_event(make_unique_event_id=True)

        self.assertTrue(str(event["event_id"]).startswith("evt-ui-demo-"))
        self.assertNotEqual(event["event_id"], "evt-demo-customer-001")

    def test_fixed_demo_event_can_still_be_loaded(self):
        event = operator_actions.load_demo_event(make_unique_event_id=False)

        self.assertEqual(event["event_id"], "evt-demo-customer-001")
        self.assertEqual(event["source"], "callcenter")
        self.assertEqual(event["event_type"], "customer_message")
        self.assertIn("ORD-10042", event["payload"]["message"])

    def test_ui_source_contains_demo_button(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        self.assertIn("Run selected demo", source)
        self.assertIn("Start over", source)

    def test_ui_does_not_directly_call_runtime_execution(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        for text in ("intake_event(", "intake_and_run_event(", "execute_pending", "send_customer_message"):
            self.assertNotIn(text, source)

    def test_demo_run_reaches_pending_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            seed_business_data(runtime_root)

            def run_in_temp_runtime(event_data):
                return runtime_intake_and_run_event(event_data, runtime_data_dir=runtime_root)

            original_intake = operator_actions.intake_and_run_event
            original_loader = operator_actions._load_frame_dict
            operator_actions.intake_and_run_event = run_in_temp_runtime
            operator_actions._load_frame_dict = lambda frame_id: load_taskframe_dict(frame_id, runtime_root)
            try:
                result = operator_actions.run_demo_customer_message(make_unique_event_id=True)
            finally:
                operator_actions.intake_and_run_event = original_intake
                operator_actions._load_frame_dict = original_loader

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")
            self.assertIsNotNone(result["frame_id"])
            self.assertIn("draft_reply", result["outputs"])
            self.assertIn("business_lookups", result["outputs"])
            self.assertGreaterEqual(len(result["pending_actions"]), 1)
            self.assertEqual(result["pending_actions"][0]["action_type"], "send_customer_message")
            self.assertEqual(result["pending_actions"][0]["status"], "PENDING_APPROVAL")

    def test_snapshot_after_demo_run_preserves_pending_action_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            seed_business_data(runtime_root)

            def run_in_temp_runtime(event_data):
                return runtime_intake_and_run_event(event_data, runtime_data_dir=runtime_root)

            original_intake = operator_actions.intake_and_run_event
            original_loader = operator_actions._load_frame_dict
            operator_actions.intake_and_run_event = run_in_temp_runtime
            operator_actions._load_frame_dict = lambda frame_id: load_taskframe_dict(frame_id, runtime_root)
            try:
                result = operator_actions.run_demo_customer_message(make_unique_event_id=True)
                self.assertTrue(result["ok"])
                snapshot = build_operator_snapshot(tmp)
            finally:
                operator_actions.intake_and_run_event = original_intake
                operator_actions._load_frame_dict = original_loader

            self.assertEqual(snapshot["active_frame"]["state"], "WAITING_FOR_EXECUTE")
            self.assertGreaterEqual(len(snapshot["pending_actions"]), 1)
            self.assertEqual(snapshot["pending_actions"][0]["status"], "PENDING_APPROVAL")
            self.assertFalse(snapshot["active_frame"].get("executed_actions"))
            self.assertTrue(any("business_lookup" in str(item) for item in snapshot["active_frame"].get("evidence", [])))

    def test_demo_runner_result_can_generate_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=tmp)
            report = generate_report_for_frame(result["frame_id"], tmp)
            self.assertTrue(report["ok"])
            self.assertTrue(Path(report["markdown_path"]).is_file())
            self.assertTrue(Path(report["html_path"]).is_file())
            self.assertTrue(Path(report["evidence_bundle_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
