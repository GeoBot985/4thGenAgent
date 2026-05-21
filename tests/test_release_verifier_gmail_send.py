from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestGmailSendToolModuleExists(unittest.TestCase):
    def test_gmail_send_tool_module_exists(self):
        self.assertTrue((ROOT / "runtime" / "gmail_send_tool.py").is_file())

    def test_gmail_send_doc_exists(self):
        self.assertTrue((ROOT / "docs" / "live_gmail_send.md").is_file())


class TestGmailSendToolImports(unittest.TestCase):
    def test_gmail_send_tool_imports(self):
        from runtime.gmail_send_tool import (
            GMAIL_SEND_TOOL_KEY,
            GMAIL_SEND_DEFAULT_CONFIG,
            GMAIL_SEND_AUDIT_EVENT_EXECUTED,
            GMAIL_SEND_AUDIT_EVENT_BLOCKED,
            build_gmail_send_pending_action,
            gmail_send_dry_run,
            gmail_send_live_execute,
            validate_gmail_send_payload,
            normalize_gmail_send_config,
            build_gmail_send_report,
            write_gmail_send_report,
            build_gmail_send_audit_event,
        )
        self.assertEqual(GMAIL_SEND_TOOL_KEY, "gmail/send")

    def test_gmail_guardrail_importable(self):
        from runtime.live_guardrails import guardrail_gmail_send
        self.callable(guardrail_gmail_send)

    def callable(self, obj):
        self.assertTrue(callable(obj))


class TestGmailSendDefaultConfigSafety(unittest.TestCase):
    def test_gmail_send_disabled_by_default(self):
        from runtime.gmail_send_tool import GMAIL_SEND_DEFAULT_CONFIG
        self.assertFalse(GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]["enabled"])

    def test_max_recipients_is_5(self):
        from runtime.gmail_send_tool import GMAIL_SEND_DEFAULT_CONFIG
        self.assertEqual(GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]["max_recipients"], 5)

    def test_allow_attachments_false(self):
        from runtime.gmail_send_tool import GMAIL_SEND_DEFAULT_CONFIG
        self.assertFalse(GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]["allow_attachments"])

    def test_allowed_recipient_domains_empty(self):
        from runtime.gmail_send_tool import GMAIL_SEND_DEFAULT_CONFIG
        self.assertEqual(GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]["allowed_recipient_domains"], [])

    def test_blocked_recipient_domains_empty(self):
        from runtime.gmail_send_tool import GMAIL_SEND_DEFAULT_CONFIG
        self.assertEqual(GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]["blocked_recipient_domains"], [])


class TestGmailSendToolRegistryEntry(unittest.TestCase):
    def test_gmail_send_in_tool_registry(self):
        from runtime.tool_registry import TOOL_REGISTRY
        self.assertIn("gmail/send", TOOL_REGISTRY)

    def test_gmail_send_spec_side_effect_true(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("gmail/send", {})
        self.assertTrue(spec.get("side_effect"))

    def test_gmail_send_spec_requires_approval_true(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("gmail/send", {})
        self.assertTrue(spec.get("requires_approval"))

    def test_gmail_send_spec_allow_live_side_effect_true(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("gmail/send", {})
        self.assertTrue(spec.get("allow_live_side_effect"))

    def test_gmail_send_spec_live_guardrail_is_gmail_send(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("gmail/send", {})
        self.assertEqual(spec.get("live_guardrail"), "gmail_send")

    def test_gmail_send_spec_output_type(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("gmail/send", {})
        self.assertEqual(spec.get("output_type"), "gmail_send_result")


class TestGmailSendNeverEnabledInNonLiveProfiles(unittest.TestCase):
    def test_demo_profile_blocks_gmail_send(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("demo"))

    def test_pilot_profile_blocks_gmail_send(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("pilot"))

    def test_release_profile_blocks_gmail_send(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("release"))

    def test_test_profile_blocks_gmail_send(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("test"))

    def test_dev_profile_blocks_gmail_send(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("dev"))


class TestGmailSendAuditConstants(unittest.TestCase):
    def test_executed_event_name(self):
        from runtime.gmail_send_tool import GMAIL_SEND_AUDIT_EVENT_EXECUTED
        self.assertEqual(GMAIL_SEND_AUDIT_EVENT_EXECUTED, "LIVE_EMAIL_SENT")

    def test_blocked_event_name(self):
        from runtime.gmail_send_tool import GMAIL_SEND_AUDIT_EVENT_BLOCKED
        self.assertEqual(GMAIL_SEND_AUDIT_EVENT_BLOCKED, "LIVE_EMAIL_SEND_BLOCKED")


class TestGmailSendDocContent(unittest.TestCase):
    def _read_doc(self) -> str:
        doc = ROOT / "docs" / "live_gmail_send.md"
        if doc.is_file():
            return doc.read_text(encoding="utf-8")
        return ""

    def test_doc_mentions_spec_133(self):
        doc = self._read_doc()
        self.assertIn("133", doc)

    def test_doc_mentions_gmail_send_tool_key(self):
        doc = self._read_doc()
        self.assertIn("gmail/send", doc)

    def test_doc_mentions_disabled_by_default(self):
        doc = self._read_doc()
        self.assertIn("disabled", doc.lower())

    def test_doc_mentions_demo_profile_restriction(self):
        doc = self._read_doc()
        self.assertIn("demo", doc.lower())

    def test_doc_mentions_body_not_in_reports(self):
        doc = self._read_doc()
        self.assertIn("body", doc.lower())

    def test_doc_mentions_dry_run(self):
        doc = self._read_doc()
        self.assertIn("dry-run", doc.lower())

    def test_doc_mentions_live_execution_contract(self):
        doc = self._read_doc()
        self.assertIn("live_side_effect_execution_contract", doc)


class TestGmailSendGuardrailChecks(unittest.TestCase):
    def test_guardrail_dispatched_by_run_live_guardrail(self):
        from runtime.live_guardrails import run_live_guardrail
        from runtime.gmail_send_tool import build_gmail_send_pending_action
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["user@example.com"],
            subject="Test",
            body="Body",
            status="APPROVED",
        )
        spec = {
            "side_effect": True,
            "requires_approval": True,
            "allow_live_side_effect": True,
            "live_guardrail": "gmail_send",
        }
        result = run_live_guardrail("gmail_send", action, spec)
        self.assertEqual(result["guardrail"], "gmail_send")


if __name__ == "__main__":
    unittest.main()
