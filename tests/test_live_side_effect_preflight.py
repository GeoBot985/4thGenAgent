from __future__ import annotations

import unittest

from runtime.live_side_effect_contract import (
    DUPLICATE_SIDE_EFFECT_BLOCKED,
    IDEMPOTENCY_KEY_REQUIRED,
    LIVE_GUARDRAIL_FAILED,
    LIVE_MANIFEST_NOT_ALLOWED,
    LIVE_PROFILE_NOT_ALLOWED,
    LIVE_SIDE_EFFECTS_DISABLED,
    LIVE_TOOL_NOT_ALLOWED,
    PENDING_ACTION_NOT_APPROVED,
    TYPED_CONFIRMATION_REQUIRED,
    run_live_side_effect_preflight,
)


def _approved_action(overrides: dict | None = None) -> dict:
    action = {
        "action_id": "pa_test_1",
        "tool": "gmail/send",
        "status": "APPROVED",
        "approved_by": "operator",
        "approved_at": "2026-05-20T10:00:00Z",
        "idempotency_key": "ikey_abc123",
        "business_ref": "inv-001",
        "live_executed": False,
    }
    if overrides:
        action.update(overrides)
    return action


def _live_tool_spec(overrides: dict | None = None) -> dict:
    spec = {
        "namespace": "gmail",
        "action": "send",
        "side_effect": True,
        "requires_approval": True,
        "allow_live": False,
        "allow_live_side_effect": True,
        "live_guardrail": "gmail_send_guardrail",
    }
    if overrides:
        spec.update(overrides)
    return spec


def _live_manifest_policy(overrides: dict | None = None) -> dict:
    policy = {
        "enabled": True,
        "allowed_tools": ["gmail/send"],
        "allowed_actions": [],
        "max_live_actions": 1,
        "requires_operator_confirmation": True,
    }
    if overrides:
        policy.update(overrides)
    return policy


def _run_passing_preflight(**kwargs) -> dict:
    defaults = dict(
        pending_action=_approved_action(),
        tool_spec=_live_tool_spec(),
        manifest_live_execution=_live_manifest_policy(),
        profile_name="live",
        profile_data={"allow_live_side_effects": True},
        executed_actions=[],
        dry_run=False,
        confirmation=None,
    )
    defaults.update(kwargs)
    return run_live_side_effect_preflight(**defaults)


class TestPreflightPassingCase(unittest.TestCase):
    def test_all_checks_pass_when_conditions_met(self):
        result = _run_passing_preflight()
        self.assertTrue(result["ok"])
        self.assertFalse(result["blocked"])
        self.assertIsNone(result["error_code"])

    def test_returns_tool_and_profile_in_result(self):
        result = _run_passing_preflight()
        self.assertEqual(result["tool"], "gmail/send")
        self.assertEqual(result["profile"], "live")


class TestPreflightDryRunCheck(unittest.TestCase):
    def test_dry_run_true_blocks_with_disabled_code(self):
        result = _run_passing_preflight(dry_run=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_SIDE_EFFECTS_DISABLED)

    def test_dry_run_none_blocks_with_disabled_code(self):
        result = _run_passing_preflight(dry_run=None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_SIDE_EFFECTS_DISABLED)

    def test_no_explicit_live_fails_with_disabled_code(self):
        result = run_live_side_effect_preflight(
            pending_action=_approved_action(),
            tool_spec=_live_tool_spec(),
            manifest_live_execution=_live_manifest_policy(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_SIDE_EFFECTS_DISABLED)


class TestPreflightProfileCheck(unittest.TestCase):
    def test_default_profile_blocks_live_side_effects(self):
        result = _run_passing_preflight(profile_name="demo", profile_data={"allow_live_side_effects": False})
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_PROFILE_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])

    def test_release_profile_blocks(self):
        result = _run_passing_preflight(profile_name="release", profile_data={"allow_live_side_effects": False})
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_PROFILE_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])

    def test_pilot_profile_blocks(self):
        result = _run_passing_preflight(profile_name="pilot", profile_data={"allow_live_side_effects": False})
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_PROFILE_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])


class TestPreflightManifestCheck(unittest.TestCase):
    def test_manifest_not_enabled_blocks(self):
        policy = _live_manifest_policy({"enabled": False})
        result = _run_passing_preflight(manifest_live_execution=policy)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_MANIFEST_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])

    def test_tool_not_in_manifest_allowlist_blocks(self):
        policy = _live_manifest_policy({"allowed_tools": ["sheet/create"]})
        result = _run_passing_preflight(manifest_live_execution=policy)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_MANIFEST_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])

    def test_none_manifest_blocks(self):
        result = _run_passing_preflight(manifest_live_execution=None)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_MANIFEST_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])


class TestPreflightToolRegistryCheck(unittest.TestCase):
    def test_tool_without_allow_live_side_effect_blocks(self):
        spec = _live_tool_spec({"allow_live_side_effect": False})
        result = _run_passing_preflight(tool_spec=spec)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_TOOL_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])

    def test_tool_without_side_effect_blocks(self):
        spec = _live_tool_spec({"side_effect": False})
        result = _run_passing_preflight(tool_spec=spec)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_TOOL_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])

    def test_tool_without_requires_approval_blocks(self):
        spec = _live_tool_spec({"requires_approval": False})
        result = _run_passing_preflight(tool_spec=spec)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_TOOL_NOT_ALLOWED, [c["error_code"] for c in result["failed_checks"]])


class TestPreflightApprovalCheck(unittest.TestCase):
    def test_pending_action_not_approved_blocks(self):
        action = _approved_action({"status": "PENDING_APPROVAL", "approved_by": "", "approved_at": ""})
        result = _run_passing_preflight(pending_action=action)
        self.assertFalse(result["ok"])
        self.assertIn(PENDING_ACTION_NOT_APPROVED, [c["error_code"] for c in result["failed_checks"]])

    def test_rejected_action_blocks(self):
        action = _approved_action({"status": "REJECTED", "approved_by": "", "approved_at": ""})
        result = _run_passing_preflight(pending_action=action)
        self.assertFalse(result["ok"])

    def test_missing_approved_by_blocks(self):
        action = _approved_action({"approved_by": ""})
        result = _run_passing_preflight(pending_action=action)
        self.assertFalse(result["ok"])

    def test_missing_approved_at_blocks(self):
        action = _approved_action({"approved_at": ""})
        result = _run_passing_preflight(pending_action=action)
        self.assertFalse(result["ok"])


class TestPreflightIdempotencyCheck(unittest.TestCase):
    def test_missing_idempotency_key_blocks(self):
        action = _approved_action({"idempotency_key": ""})
        result = _run_passing_preflight(pending_action=action)
        self.assertFalse(result["ok"])
        self.assertIn(IDEMPOTENCY_KEY_REQUIRED, [c["error_code"] for c in result["failed_checks"]])

    def test_duplicate_idempotency_key_blocks(self):
        action = _approved_action({"action_id": "pa_new", "idempotency_key": "shared_key"})
        executed = [{"action_id": "pa_old", "idempotency_key": "shared_key", "status": "EXECUTED"}]
        result = _run_passing_preflight(pending_action=action, executed_actions=executed)
        self.assertFalse(result["ok"])
        self.assertIn(DUPLICATE_SIDE_EFFECT_BLOCKED, [c["error_code"] for c in result["failed_checks"]])

    def test_already_live_executed_blocks(self):
        action = _approved_action({"live_executed": True})
        result = _run_passing_preflight(pending_action=action)
        self.assertFalse(result["ok"])
        self.assertIn(DUPLICATE_SIDE_EFFECT_BLOCKED, [c["error_code"] for c in result["failed_checks"]])


class TestPreflightGuardrailCheck(unittest.TestCase):
    def test_blocked_guardrail_name_fails(self):
        spec = _live_tool_spec({"live_guardrail": "blocked"})
        result = _run_passing_preflight(tool_spec=spec)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_GUARDRAIL_FAILED, [c["error_code"] for c in result["failed_checks"]])

    def test_empty_guardrail_name_fails(self):
        spec = _live_tool_spec({"live_guardrail": ""})
        result = _run_passing_preflight(tool_spec=spec)
        self.assertFalse(result["ok"])
        self.assertIn(LIVE_GUARDRAIL_FAILED, [c["error_code"] for c in result["failed_checks"]])


class TestPreflightTypedConfirmation(unittest.TestCase):
    def test_wrong_confirmation_blocks(self):
        result = _run_passing_preflight(confirmation="wrong-phrase")
        self.assertFalse(result["ok"])
        self.assertIn(TYPED_CONFIRMATION_REQUIRED, [c["error_code"] for c in result["failed_checks"]])

    def test_correct_confirmation_passes(self):
        result = _run_passing_preflight(confirmation="LIVE-EXECUTE")
        self.assertTrue(result["ok"])

    def test_no_confirmation_supplied_passes_gate(self):
        # When confirmation is None, the check is skipped (caller handles it separately)
        result = _run_passing_preflight(confirmation=None)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
