from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.failure_summary import build_failure_summary
from runtime.llm_adapter import FakeLLMAdapter
from runtime.runtime_engine import RuntimeEngine


class FailureSummaryTests(unittest.TestCase):
    def _failed_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(
                llm_adapter=FakeLLMAdapter(
                    {
                        "extract_order_ref": '{"order_ref": "ORD-10044", "confidence": "high", "reason": "Detected explicit order reference."}',
                        "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                        "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10044 has shipped and is currently in transit.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                        "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
                    }
                ),
                runtime_data_dir=runtime_dir,
                manifest_dir="manifests",
            )
            frame = engine.handle_event(
                create_event(
                    "manual.customer_status_llm_e2e",
                    "operator_ui",
                    payload={"customer_id": "CUST-1001", "message": "Where is order ORD-10044?", "channel": "callcenter"},
                ),
                dry_run=True,
            )
            return frame

    def test_build_failure_summary_for_failed_validation(self):
        frame = self._failed_frame()
        summary = build_failure_summary(frame.__dict__ if hasattr(frame, "__dict__") else frame)
        self.assertTrue(summary["ok"])
        self.assertTrue(summary["state"].startswith("FAILED"))
        self.assertNotEqual(summary["failed_step_id"], "")
        self.assertNotEqual(summary["failure_message"], "")
        self.assertEqual(summary["pending_action_count"], 0)
        self.assertEqual(summary["executed_action_count"], 0)

    def test_build_failure_summary_for_successful_frame(self):
        summary = build_failure_summary({"state": "COMPLETED", "pending_actions": [], "executed_actions": []})
        self.assertEqual(summary["failure_type"], "")
        self.assertEqual(summary["failure_message"], "")
        self.assertEqual(summary["blocking_errors"], [])

    def test_failure_summary_preserves_validation_details(self):
        frame = self._failed_frame()
        summary = build_failure_summary(frame.__dict__ if hasattr(frame, "__dict__") else frame)
        self.assertTrue(summary["failed_validations"])

    def test_failure_summary_tolerates_partial_frame(self):
        for value in ({}, {"state": "FAILED_VALIDATION"}, {"errors": [{"message": "boom"}]}):
            summary = build_failure_summary(value)
            self.assertIsInstance(summary, dict)


if __name__ == "__main__":
    unittest.main()
