from __future__ import annotations

import unittest

from runtime.live_side_effect_contract import (
    check_typed_confirmation,
    live_execute_confirmation_phrase,
)
from runtime.gmail_send_tool import (
    build_gmail_send_pending_action,
    gmail_send_live_execute,
)


def _approved_action() -> dict:
    return build_gmail_send_pending_action(
        action_id="pa-001",
        business_ref="ref-001",
        idempotency_key="idem-001",
        to=["user@example.com"],
        subject="Test",
        body="Body",
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


def _mock_send_ok(**kwargs) -> dict:
    return {"ok": True, "message_id": "msg-abc", "thread_id": "thread-1"}


class TestLiveExecuteConfirmationPhrase(unittest.TestCase):
    def test_phrase_is_live_execute(self):
        self.assertEqual(live_execute_confirmation_phrase(), "LIVE-EXECUTE")

    def test_phrase_is_string(self):
        self.assertIsInstance(live_execute_confirmation_phrase(), str)

    def test_phrase_is_uppercase(self):
        phrase = live_execute_confirmation_phrase()
        self.assertEqual(phrase, phrase.upper())


class TestCheckTypedConfirmation(unittest.TestCase):
    def test_correct_phrase_ok(self):
        result = check_typed_confirmation("LIVE-EXECUTE")
        self.assertTrue(result["ok"])

    def test_wrong_phrase_fails(self):
        result = check_typed_confirmation("live-execute")
        self.assertFalse(result["ok"])

    def test_empty_phrase_fails(self):
        result = check_typed_confirmation("")
        self.assertFalse(result["ok"])

    def test_partial_phrase_fails(self):
        result = check_typed_confirmation("LIVE")
        self.assertFalse(result["ok"])

    def test_none_fails(self):
        result = check_typed_confirmation(None)
        self.assertFalse(result["ok"])

    def test_failure_includes_expected_field(self):
        result = check_typed_confirmation("wrong")
        self.assertIn("expected", result)
        self.assertEqual(result["expected"], "LIVE-EXECUTE")

    def test_failure_includes_received_field(self):
        result = check_typed_confirmation("wrong-phrase")
        self.assertIn("received", result)

    def test_whitespace_trimmed_passes(self):
        # implementation strips whitespace, so padded phrase is accepted
        result = check_typed_confirmation("  LIVE-EXECUTE  ")
        self.assertTrue(result["ok"])


class TestGmailSendCLIConfirmationEnforced(unittest.TestCase):
    def test_no_confirmation_skips_check(self):
        # confirmation=None skips the typed confirmation check (optional gate)
        # execution proceeds if all other checks pass
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation=None,
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertIsInstance(result, dict)

    def test_wrong_confirmation_blocks_execution(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="i-confirm",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertFalse(result["ok"])

    def test_correct_confirmation_allows_execution(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertTrue(result["ok"])

    def test_lowercase_confirmation_rejected(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="live-execute",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertFalse(result["ok"])

    def test_empty_string_confirmation_rejected(self):
        action = _approved_action()
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertFalse(result["ok"])


class TestGmailSendCLIProfileBlocking(unittest.TestCase):
    """CLI-level profile restrictions: demo/pilot/release must never send live."""

    def _attempt_send(self, profile: str) -> dict:
        action = _approved_action()
        return gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name=profile,
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=_mock_send_ok,
        )

    def test_demo_profile_blocked(self):
        result = self._attempt_send("demo")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_pilot_profile_blocked(self):
        result = self._attempt_send("pilot")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_release_profile_blocked(self):
        result = self._attempt_send("release")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_test_profile_blocked(self):
        result = self._attempt_send("test")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_dev_profile_blocked(self):
        result = self._attempt_send("dev")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])


class TestGmailSendDryRunCLIPath(unittest.TestCase):
    def test_dry_run_needs_no_confirmation(self):
        from runtime.gmail_send_tool import gmail_send_dry_run
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        result = gmail_send_dry_run(action)
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["dry_run"])

    def test_dry_run_returns_sent_false(self):
        from runtime.gmail_send_tool import gmail_send_dry_run
        action = build_gmail_send_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            to=["a@b.com"],
            subject="S",
            body="B",
        )
        result = gmail_send_dry_run(action)
        self.assertFalse(result["data"]["sent"])


if __name__ == "__main__":
    unittest.main()
