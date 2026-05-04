from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.llm_adapter import FakeLLMAdapter
from runtime.runtime_engine import RuntimeEngine
from runtime.manifest_loader import load_manifest_by_id
from runtime.taskframe_reload import load_taskframe


class CustomerStatusLLME2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _engine(self, responses: dict[str, str] | None = None) -> RuntimeEngine:
        return RuntimeEngine(
            llm_adapter=FakeLLMAdapter(responses or {}),
            runtime_data_dir=self.runtime_dir,
            manifest_dir="manifests",
        )

    def test_customer_status_llm_e2e_manifest_loads(self):
        manifest = load_manifest_by_id("customer.status_llm_e2e", "manifests")
        self.assertEqual(manifest.manifest_id, "customer.status_llm_e2e")
        self.assertGreaterEqual(len(manifest.steps), 10)
        self.assertIn("success_pending_actions", manifest.completion)

    def test_customer_status_llm_e2e_completes_to_waiting_for_execute_with_fake_llm(self):
        frame = self._engine(
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
            }
        ).handle_event(create_event("manual.customer_status_llm_e2e", "operator_ui", payload={"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcenter"}), dry_run=True)
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertEqual(frame.outputs["customer"]["customer_id"], "CUST-1001")
        self.assertEqual(frame.outputs["order"]["order_ref"], "ORD-10042")
        self.assertEqual(frame.outputs["shipment"]["order_ref"], "ORD-10042")
        for key in ("order_ref", "category", "customer", "order", "shipment", "order_context", "draft_reply", "reply_check"):
            self.assertIn(key, frame.outputs)

    def test_customer_status_llm_e2e_stages_customer_reply_not_live_send(self):
        frame = self._engine(
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
            }
        ).handle_event(create_event("manual.customer_status_llm_e2e", "operator_ui", payload={"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcenter"}), dry_run=True)
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertEqual(frame.pending_actions[0]["status"], "PENDING_APPROVAL")
        self.assertIn(frame.pending_actions[0]["tool"], {"wa/send", "cc/send"})
        self.assertEqual(frame.executed_actions, [])

    def test_customer_status_llm_e2e_records_llm_calls(self):
        frame = self._engine(
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
            }
        ).handle_event(create_event("manual.customer_status_llm_e2e", "operator_ui", payload={"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcenter"}), dry_run=True)
        self.assertGreaterEqual(len(frame.llm_calls), 4)
        actions = [call.get("action") for call in frame.llm_calls]
        for action in ("extract_order_ref", "classify_customer_message", "draft_customer_status_reply", "compare_reply_to_facts"):
            self.assertIn(action, actions)

    def test_customer_status_llm_e2e_fails_when_reply_check_fails(self):
        frame = self._engine(
            {
                "extract_order_ref": '{"order_ref": "ORD-10042", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": false, "matches_facts": false, "unsupported_claims": ["Promised refund not in facts."], "missing_required_facts": [], "reason": "Unsupported refund claim."}',
            }
        ).handle_event(create_event("manual.customer_status_llm_e2e", "operator_ui", payload={"customer_id": "CUST-1001", "message": "Where is my order ORD-10042?", "channel": "callcenter"}), dry_run=True)
        self.assertIn(frame.state, {"FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION"})
        self.assertFalse(frame.pending_actions)

    def test_customer_status_llm_e2e_fails_wrong_customer_order_pairing(self):
        frame = self._engine(
            {
                "extract_order_ref": '{"order_ref": "ORD-10044", "confidence": "high", "reason": "Detected explicit order reference."}',
                "classify_customer_message": '{"label": "order_status", "confidence": "high", "reason": "Customer asks where their order is."}',
                "draft_customer_status_reply": '{"reply": "Hi Alex, your order ORD-10044 has shipped and is currently in transit. Estimated delivery is 2026-05-03.", "tone": "professional", "included_order_ref": true, "included_status": true, "invented_compensation": false}',
                "compare_reply_to_facts": '{"ok": true, "matches_facts": true, "unsupported_claims": [], "missing_required_facts": [], "reason": "Reply matches the supplied order and shipment facts."}',
            }
        ).handle_event(create_event("manual.customer_status_llm_e2e", "operator_ui", payload={"customer_id": "CUST-1001", "message": "Where is order ORD-10044?", "channel": "callcenter"}), dry_run=True)
        self.assertNotEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertFalse(frame.pending_actions)


if __name__ == "__main__":
    unittest.main()
