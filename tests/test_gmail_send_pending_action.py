from __future__ import annotations

import unittest

from runtime.gmail_send_tool import (
    GMAIL_SEND_TOOL_KEY,
    build_gmail_send_pending_action,
)


class TestGmailSendPendingActionStructure(unittest.TestCase):
    def _build(self, **overrides) -> dict:
        defaults = dict(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["user@example.com"],
            subject="Hello",
            body="World",
        )
        defaults.update(overrides)
        return build_gmail_send_pending_action(**defaults)

    def test_tool_key_is_gmail_send(self):
        action = self._build()
        self.assertEqual(action["tool"], GMAIL_SEND_TOOL_KEY)
        self.assertEqual(action["tool"], "gmail/send")

    def test_operation_is_side_effect(self):
        action = self._build()
        self.assertEqual(action["operation"], "side_effect")

    def test_live_capable_is_true(self):
        action = self._build()
        self.assertTrue(action["live_capable"])

    def test_live_executed_default_false(self):
        action = self._build()
        self.assertFalse(action["live_executed"])

    def test_dry_run_executed_default_false(self):
        action = self._build()
        self.assertFalse(action["dry_run_executed"])

    def test_live_executed_at_empty_by_default(self):
        action = self._build()
        self.assertEqual(action["live_executed_at"], "")

    def test_guardrail_result_none_by_default(self):
        action = self._build()
        self.assertIsNone(action["guardrail_result"])

    def test_default_status_pending_approval(self):
        action = self._build()
        self.assertEqual(action["status"], "PENDING_APPROVAL")

    def test_custom_status(self):
        action = self._build(status="APPROVED")
        self.assertEqual(action["status"], "APPROVED")

    def test_approved_by_default_empty(self):
        action = self._build()
        self.assertEqual(action["approved_by"], "")

    def test_approved_at_default_empty(self):
        action = self._build()
        self.assertEqual(action["approved_at"], "")

    def test_approved_by_stored(self):
        action = self._build(approved_by="ops@example.com", approved_at="2026-01-01T00:00:00Z")
        self.assertEqual(action["approved_by"], "ops@example.com")
        self.assertEqual(action["approved_at"], "2026-01-01T00:00:00Z")


class TestGmailSendPendingActionPayload(unittest.TestCase):
    def test_to_is_list(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertIsInstance(action["payload"]["to"], list)
        self.assertEqual(action["payload"]["to"], ["a@b.com"])

    def test_cc_defaults_to_empty_list(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["payload"]["cc"], [])

    def test_bcc_defaults_to_empty_list(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["payload"]["bcc"], [])

    def test_attachments_defaults_to_empty_list(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["payload"]["attachments"], [])

    def test_cc_bcc_stored_correctly(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            cc=["c@b.com"],
            bcc=["d@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["payload"]["cc"], ["c@b.com"])
        self.assertEqual(action["payload"]["bcc"], ["d@b.com"])

    def test_body_stored_in_payload(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="Hello World",
        )
        self.assertEqual(action["payload"]["body"], "Hello World")

    def test_subject_stored_in_payload(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="My Subject",
            body="B",
        )
        self.assertEqual(action["payload"]["subject"], "My Subject")

    def test_idempotency_key_at_top_level(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="key-xyz",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["idempotency_key"], "key-xyz")

    def test_business_ref_at_top_level(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="biz-ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["business_ref"], "biz-ref-001")

    def test_multiple_to_recipients(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com", "c@b.com", "e@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(len(action["payload"]["to"]), 3)

    def test_to_list_is_copy(self):
        original_to = ["a@b.com"]
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=original_to,
            subject="S",
            body="B",
        )
        original_to.append("mutated@b.com")
        self.assertEqual(len(action["payload"]["to"]), 1)


class TestGmailSendPendingActionTransitionToApproved(unittest.TestCase):
    def test_status_can_be_set_to_approved(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
            approved_by="ops@example.com",
            approved_at="2026-01-01T00:00:00Z",
            status="APPROVED",
        )
        self.assertEqual(action["status"], "APPROVED")
        self.assertEqual(action["approved_by"], "ops@example.com")
        self.assertNotEqual(action["approved_at"], "")

    def test_approval_record_fields_are_present(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertIn("approved_by", action)
        self.assertIn("approved_at", action)


if __name__ == "__main__":
    unittest.main()
