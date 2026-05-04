from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.customer_inbox import reset_customer_inbox
from runtime.events import create_event
from runtime.llm_adapter import FakeLLMAdapter
from runtime.runtime_engine import RuntimeEngine
from src.operator_customer_inbox_runner import process_customer_message


class NegativeCustomerStatusScenarioTests(unittest.TestCase):
    def _engine(self, responses: dict[str, str]) -> RuntimeEngine:
        return RuntimeEngine(llm_adapter=FakeLLMAdapter(responses), runtime_data_dir=self.runtime_dir, manifest_dir="manifests")

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _run(self, customer_id: str, message: str, responses: dict[str, str]) -> object:
        return self._engine(responses).handle_event(
            create_event(
                "manual.customer_status_llm_e2e",
                "operator_ui",
                payload={"customer_id": customer_id, "message": message, "channel": "callcenter"},
            ),
            dry_run=True,
        )

    def test_missing_customer_fails_without_pending_action(self):
        frame = self._run(
            "CUST-9999",
            "Where is my order ORD-99999?",
            {
                "extract_order_ref": '{"order_ref": "ORD-99999", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi, your order ORD-99999 has shipped.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_COMPLETION"})
        self.assertFalse(frame.pending_actions)
        self.assertFalse(frame.executed_actions)

    def test_missing_order_fails_without_pending_action(self):
        frame = self._run(
            "CUST-1001",
            "Where is my order ORD-99999?",
            {
                "extract_order_ref": '{"order_ref": "ORD-99999", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi, your order ORD-99999 has shipped.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_COMPLETION"})
        self.assertFalse(frame.pending_actions)

    def test_wrong_customer_order_pairing_fails_before_draft_or_stage(self):
        frame = self._run(
            "CUST-1001",
            "Where is order ORD-10044?",
            {
                "extract_order_ref": '{"order_ref": "ORD-10044", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10044 has shipped.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION"})
        self.assertFalse(frame.pending_actions)
        self.assertTrue(
            any(
                getattr(step, "step_id", "") in {"validate_customer_owns_order", "draft_reply"}
                and str(getattr(step, "status", "")).startswith("FAILED")
                for step in frame.steps
            )
        )

    def test_unsupported_intent_fails_before_order_status_reply(self):
        frame = self._run(
            "CUST-1002",
            "I want a refund for order ORD-10043.",
            {
                "extract_order_ref": '{"order_ref": "ORD-10043", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "refund", "confidence": "high", "reason": "Refund request."}',
                "draft_customer_status_reply": '{"reply": "Your order ORD-10043 is being processed.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION"})
        self.assertFalse(frame.pending_actions)

    def test_bad_llm_extraction_fails_schema_validation(self):
        frame = self._run(
            "CUST-1001",
            "Where is my order ORD-10042?",
            {
                "extract_order_ref": '{"order_ref": "10042", "confidence": "high", "reason": "Bad format test."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION"})
        self.assertFalse(frame.pending_actions)

    def test_bad_llm_classification_fails_schema_validation(self):
        frame = self._run(
            "CUST-1001",
            "Where is my order ORD-10042?",
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "random_label", "confidence": "high", "reason": "Bad label test."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION"})
        self.assertFalse(frame.pending_actions)

    def test_bad_llm_reply_fails_before_staging(self):
        frame = self._run(
            "CUST-1001",
            "Where is my order ORD-10042?",
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Your order ORD-10042 is delayed, so we will refund you 50%.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": true}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches facts."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION"})
        self.assertFalse(frame.pending_actions)

    def test_bad_fact_check_fails_before_staging(self):
        frame = self._run(
            "CUST-1001",
            "Where is my order ORD-10042?",
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": false, "matches_facts": false, "unsupported_claims": ["Promised refund not present in facts."], "missing_required_facts": [], "reason": "Reply contains unsupported compensation."}',
            },
        )
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION"})
        self.assertFalse(frame.pending_actions)


class NegativeInboxProcessingTests(unittest.TestCase):
    def test_process_missing_customer_message_marks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            result = process_customer_message("msg_004", runtime_data_dir=tmp, use_local_llm=False)
            self.assertIn(result["state"], {"FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_COMPLETION"})
            self.assertTrue(result["error"] or result.get("message"))

    def test_process_wrong_customer_message_marks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            result = process_customer_message("msg_005", runtime_data_dir=tmp, use_local_llm=False)
            self.assertIn(result["state"], {"FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_COMPLETION"})

    def test_failed_customer_message_can_be_reprocessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            first = process_customer_message("msg_004", runtime_data_dir=tmp, use_local_llm=False)
            second = process_customer_message("msg_004", runtime_data_dir=tmp, use_local_llm=False)
            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])


if __name__ == "__main__":
    unittest.main()
