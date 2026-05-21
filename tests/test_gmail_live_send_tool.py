from __future__ import annotations

import unittest

from runtime.gmail_send_tool import (
    GMAIL_SEND_AUDIT_EVENT_BLOCKED,
    GMAIL_SEND_AUDIT_EVENT_EXECUTED,
    GMAIL_SEND_DEFAULT_CONFIG,
    GMAIL_SEND_TOOL_KEY,
    build_gmail_send_pending_action,
    gmail_send_dry_run,
    gmail_send_live_execute,
    normalize_gmail_send_config,
    validate_gmail_send_payload,
)


def _approved_action(
    *,
    to: list[str] | None = None,
    subject: str = "Test Subject",
    body: str = "Test body.",
    business_ref: str = "ref-001",
    idempotency_key: str = "idem-001",
) -> dict:
    return build_gmail_send_pending_action(
        action_id="pa-001",
        business_ref=business_ref,
        idempotency_key=idempotency_key,
        to=to or ["user@example.com"],
        subject=subject,
        body=body,
        approved_by="operator@example.com",
        approved_at="2026-01-01T00:00:00Z",
        status="APPROVED",
    )


def _live_tool_spec() -> dict:
    return {
        "side_effect": True,
        "requires_approval": True,
        "allow_live": True,
        "allow_live_side_effect": True,
        "live_guardrail": "gmail_send",
    }


def _live_manifest() -> dict:
    return {
        "enabled": True,
        "allowed_tools": ["gmail/send"],
        "allowed_actions": [],
        "max_live_actions": 1,
        "requires_operator_confirmation": True,
    }


class TestGmailSendToolKey(unittest.TestCase):
    def test_tool_key_is_gmail_send(self):
        self.assertEqual(GMAIL_SEND_TOOL_KEY, "gmail/send")


class TestGmailSendDefaultConfig(unittest.TestCase):
    def test_enabled_is_false_by_default(self):
        cfg = GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]
        self.assertFalse(cfg["enabled"])

    def test_max_recipients_default_is_5(self):
        cfg = GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]
        self.assertEqual(cfg["max_recipients"], 5)

    def test_allow_attachments_is_false_by_default(self):
        cfg = GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]
        self.assertFalse(cfg["allow_attachments"])

    def test_allowed_recipient_domains_empty_by_default(self):
        cfg = GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]
        self.assertEqual(cfg["allowed_recipient_domains"], [])

    def test_blocked_recipient_domains_empty_by_default(self):
        cfg = GMAIL_SEND_DEFAULT_CONFIG["gmail_send"]
        self.assertEqual(cfg["blocked_recipient_domains"], [])


class TestNormalizeGmailSendConfig(unittest.TestCase):
    def test_none_returns_defaults(self):
        cfg = normalize_gmail_send_config(None)
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["max_recipients"], 5)

    def test_partial_override_keeps_defaults(self):
        cfg = normalize_gmail_send_config({"gmail_send": {"max_recipients": 3}})
        self.assertEqual(cfg["max_recipients"], 3)
        self.assertFalse(cfg["enabled"])

    def test_missing_gmail_send_key_returns_defaults(self):
        cfg = normalize_gmail_send_config({"other_section": {}})
        self.assertFalse(cfg["enabled"])

    def test_unknown_keys_in_section_are_ignored(self):
        cfg = normalize_gmail_send_config({"gmail_send": {"unknown_key": "val", "max_recipients": 2}})
        self.assertEqual(cfg["max_recipients"], 2)
        self.assertNotIn("unknown_key", cfg)


class TestBuildGmailSendPendingAction(unittest.TestCase):
    def test_required_fields_present(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="Hello",
            body="World",
        )
        self.assertEqual(action["tool"], "gmail/send")
        self.assertEqual(action["operation"], "side_effect")
        self.assertTrue(action["live_capable"])
        self.assertFalse(action["live_executed"])
        self.assertFalse(action["dry_run_executed"])

    def test_payload_structure(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            cc=["c@d.com"],
            subject="Hi",
            body="Body",
        )
        payload = action["payload"]
        self.assertEqual(payload["to"], ["a@b.com"])
        self.assertEqual(payload["cc"], ["c@d.com"])
        self.assertEqual(payload["bcc"], [])
        self.assertEqual(payload["subject"], "Hi")
        self.assertEqual(payload["body"], "Body")
        self.assertEqual(payload["attachments"], [])

    def test_default_status_is_pending_approval(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        self.assertEqual(action["status"], "PENDING_APPROVAL")


class TestValidateGmailSendPayload(unittest.TestCase):
    def test_valid_payload_returns_ok(self):
        result = validate_gmail_send_payload(
            {"to": ["a@b.com"], "subject": "Hi", "body": "Body"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])

    def test_missing_to_fails(self):
        result = validate_gmail_send_payload({"subject": "S", "body": "B"})
        self.assertFalse(result["ok"])
        self.assertTrue(any("to" in e for e in result["errors"]))

    def test_missing_subject_fails(self):
        result = validate_gmail_send_payload({"to": ["a@b.com"], "body": "B"})
        self.assertFalse(result["ok"])
        self.assertTrue(any("subject" in e for e in result["errors"]))

    def test_missing_body_fails(self):
        result = validate_gmail_send_payload({"to": ["a@b.com"], "subject": "S"})
        self.assertFalse(result["ok"])
        self.assertTrue(any("body" in e for e in result["errors"]))

    def test_max_recipients_enforced(self):
        config = {"gmail_send": {"max_recipients": 2}}
        result = validate_gmail_send_payload(
            {"to": ["a@b.com", "c@b.com", "d@b.com"], "subject": "S", "body": "B"},
            config=config,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("recipients" in e for e in result["errors"]))

    def test_blocked_domain_rejected(self):
        config = {"gmail_send": {"blocked_recipient_domains": ["evil.com"]}}
        result = validate_gmail_send_payload(
            {"to": ["bad@evil.com"], "subject": "S", "body": "B"},
            config=config,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("blocked" in e for e in result["errors"]))

    def test_allowed_domain_enforced(self):
        config = {"gmail_send": {"allowed_recipient_domains": ["safe.com"]}}
        result = validate_gmail_send_payload(
            {"to": ["bad@unsafe.com"], "subject": "S", "body": "B"},
            config=config,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("allowlist" in e for e in result["errors"]))

    def test_allowed_domain_passes(self):
        config = {"gmail_send": {"allowed_recipient_domains": ["safe.com"]}}
        result = validate_gmail_send_payload(
            {"to": ["good@safe.com"], "subject": "S", "body": "B"},
            config=config,
        )
        self.assertTrue(result["ok"])

    def test_attachments_blocked_by_default(self):
        result = validate_gmail_send_payload(
            {"to": ["a@b.com"], "subject": "S", "body": "B", "attachments": ["file.pdf"]}
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("attachments" in e for e in result["errors"]))

    def test_attachments_allowed_when_config_enables(self):
        config = {"gmail_send": {"allow_attachments": True}}
        result = validate_gmail_send_payload(
            {"to": ["a@b.com"], "subject": "S", "body": "B", "attachments": ["file.pdf"]},
            config=config,
        )
        self.assertTrue(result["ok"])


class TestGmailSendDryRun(unittest.TestCase):
    def test_dry_run_returns_ok_for_valid_payload(self):
        action = _approved_action()
        result = gmail_send_dry_run(action)
        self.assertTrue(result["ok"])
        self.assertEqual(result["type"], "gmail_send_result")
        self.assertTrue(result["data"]["dry_run"])
        self.assertFalse(result["data"]["sent"])
        self.assertEqual(result["data"]["message_id"], "")

    def test_dry_run_marks_action_dry_run_executed(self):
        action = _approved_action()
        gmail_send_dry_run(action)
        self.assertTrue(action["dry_run_executed"])

    def test_dry_run_does_not_mark_live_executed(self):
        action = _approved_action()
        gmail_send_dry_run(action)
        self.assertFalse(action["live_executed"])

    def test_dry_run_fails_for_invalid_payload(self):
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=[],
            subject="",
            body="",
        )
        result = gmail_send_dry_run(action)
        self.assertFalse(result["ok"])
        self.assertTrue(result["data"]["dry_run"])


class TestGmailSendLiveExecuteBlocked(unittest.TestCase):
    def test_blocked_in_demo_profile(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="demo",
            confirmation="LIVE-EXECUTE",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertIn("error_code", result)

    def test_blocked_in_pilot_profile(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="pilot",
            confirmation="LIVE-EXECUTE",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_blocked_in_release_profile(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="release",
            confirmation="LIVE-EXECUTE",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_blocked_when_manifest_not_enabled(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution={"enabled": False, "allowed_tools": ["gmail/send"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_blocked_without_confirmation(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation=None,
        )
        self.assertFalse(result["ok"])

    def test_blocked_with_wrong_confirmation(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="wrong-phrase",
        )
        self.assertFalse(result["ok"])


class TestGmailSendLiveExecuteWithMock(unittest.TestCase):
    def _mock_send_ok(self, **kwargs):
        return {"ok": True, "message_id": "msg-abc", "thread_id": "thread-1"}

    def _mock_send_fail(self, **kwargs):
        return {"ok": False, "error": "API error", "message_id": ""}

    def test_live_execute_succeeds_with_mock(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=self._mock_send_ok,
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["blocked"])
        self.assertTrue(result["data"]["sent"])
        self.assertEqual(result["data"]["message_id"], "msg-abc")

    def test_live_execute_marks_action_live_executed(self):
        action = _approved_action()
        gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=self._mock_send_ok,
        )
        self.assertTrue(action["live_executed"])
        self.assertNotEqual(action["live_executed_at"], "")

    def test_live_execute_stores_message_id(self):
        action = _approved_action()
        gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=self._mock_send_ok,
        )
        self.assertEqual(action["message_id"], "msg-abc")

    def test_live_execute_api_failure_returns_not_ok(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=self._mock_send_fail,
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["data"]["sent"])

    def test_result_type_is_gmail_send_result(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=self._mock_send_ok,
        )
        self.assertEqual(result["type"], "gmail_send_result")


class TestAuditEventConstants(unittest.TestCase):
    def test_audit_event_executed_constant(self):
        self.assertEqual(GMAIL_SEND_AUDIT_EVENT_EXECUTED, "LIVE_EMAIL_SENT")

    def test_audit_event_blocked_constant(self):
        self.assertEqual(GMAIL_SEND_AUDIT_EVENT_BLOCKED, "LIVE_EMAIL_SEND_BLOCKED")


if __name__ == "__main__":
    unittest.main()
