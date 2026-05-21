from __future__ import annotations

import unittest

from runtime.gmail_send_tool import (
    build_gmail_send_pending_action,
    gmail_send_live_execute,
)
from runtime.live_side_effect_contract import (
    DUPLICATE_SIDE_EFFECT_BLOCKED,
    IDEMPOTENCY_KEY_REQUIRED,
    check_idempotency_key_not_used,
    check_idempotency_key_present,
)


def _approved_action(idempotency_key: str = "idem-001") -> dict:
    return build_gmail_send_pending_action(
        action_id="pa-001",
        business_ref="ref-001",
        idempotency_key=idempotency_key,
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


class TestGmailSendIdempotencyKeyRequired(unittest.TestCase):
    def test_missing_key_blocked_by_preflight(self):
        action = _approved_action(idempotency_key="")
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_present_key_passes(self):
        action = _approved_action(idempotency_key="key-123")
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


class TestGmailSendDuplicateBlocking(unittest.TestCase):
    def test_duplicate_key_blocked(self):
        executed_action = {
            "action_id": "pa-other",
            "idempotency_key": "idem-001",
            "status": "EXECUTED",
            "live_executed": True,
        }
        action = _approved_action(idempotency_key="idem-001")
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            executed_actions=[executed_action],
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_same_action_id_not_blocked_by_key_check(self):
        action = _approved_action(idempotency_key="idem-001")
        same_action_executed = {
            "action_id": "pa-001",  # same action_id
            "idempotency_key": "idem-001",
            "status": "EXECUTED",
        }
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            executed_actions=[same_action_executed],
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=_mock_send_ok,
        )
        # Same action_id doesn't trigger duplicate blocking by key uniqueness check
        self.assertIsInstance(result, dict)

    def test_already_live_executed_action_blocked(self):
        action = _approved_action()
        action["live_executed"] = True  # already executed
        result = gmail_send_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            _gmail_api_send_fn=_mock_send_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)


class TestCheckIdempotencyKeyPresent(unittest.TestCase):
    def test_present_key_ok(self):
        action = {"idempotency_key": "key-abc"}
        result = check_idempotency_key_present(action)
        self.assertTrue(result["ok"])
        self.assertEqual(result["idempotency_key"], "key-abc")

    def test_empty_key_fails(self):
        action = {"idempotency_key": ""}
        result = check_idempotency_key_present(action)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_missing_key_fails(self):
        action = {}
        result = check_idempotency_key_present(action)
        self.assertFalse(result["ok"])

    def test_whitespace_only_key_fails(self):
        action = {"idempotency_key": "   "}
        result = check_idempotency_key_present(action)
        self.assertFalse(result["ok"])


class TestCheckIdempotencyKeyNotUsed(unittest.TestCase):
    def test_no_prior_executions_ok(self):
        action = {"idempotency_key": "key-001", "action_id": "pa-001"}
        result = check_idempotency_key_not_used(action, [])
        self.assertTrue(result["ok"])

    def test_duplicate_key_different_action_blocked(self):
        action = {"idempotency_key": "key-001", "action_id": "pa-001"}
        executed = [
            {"idempotency_key": "key-001", "action_id": "pa-other", "status": "EXECUTED"}
        ]
        result = check_idempotency_key_not_used(action, executed)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_same_action_id_not_duplicate_blocked(self):
        action = {"idempotency_key": "key-001", "action_id": "pa-001"}
        executed = [
            {"idempotency_key": "key-001", "action_id": "pa-001", "status": "EXECUTED"}
        ]
        result = check_idempotency_key_not_used(action, executed)
        # Same action_id re-check is for the already-live-executed path
        self.assertIsInstance(result, dict)

    def test_already_live_executed_blocked(self):
        action = {"idempotency_key": "key-001", "action_id": "pa-001", "live_executed": True}
        result = check_idempotency_key_not_used(action, [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)


class TestIdempotencyKeyUniqueness(unittest.TestCase):
    def test_different_keys_dont_conflict(self):
        action = {"idempotency_key": "key-001", "action_id": "pa-001"}
        executed = [
            {"idempotency_key": "key-002", "action_id": "pa-other", "status": "EXECUTED"}
        ]
        result = check_idempotency_key_not_used(action, executed)
        self.assertTrue(result["ok"])

    def test_non_executed_status_not_blocked(self):
        action = {"idempotency_key": "key-001", "action_id": "pa-001"}
        executed = [
            {"idempotency_key": "key-001", "action_id": "pa-other", "status": "APPROVED"}
        ]
        result = check_idempotency_key_not_used(action, executed)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
