from __future__ import annotations

import unittest

from runtime.live_side_effect_contract import (
    ALL_ERROR_CODES,
    DUPLICATE_SIDE_EFFECT_BLOCKED,
    IDEMPOTENCY_KEY_REQUIRED,
    LIVE_EVIDENCE_WRITE_FAILED,
    LIVE_GUARDRAIL_FAILED,
    LIVE_MANIFEST_NOT_ALLOWED,
    LIVE_PROFILE_NOT_ALLOWED,
    LIVE_SIDE_EFFECT_EXECUTION_POLICY,
    LIVE_SIDE_EFFECTS_DISABLED,
    LIVE_TOOL_NOT_ALLOWED,
    PENDING_ACTION_NOT_APPROVED,
    TYPED_CONFIRMATION_REQUIRED,
    LIVE_CAPABLE_PENDING_ACTION_FIELDS,
    DEFAULT_MANIFEST_LIVE_ALLOWLIST,
    mark_pending_action_live_capable,
    mark_pending_action_live_executed,
    mark_pending_action_dry_run_executed,
    normalize_live_capable_pending_action,
    normalize_live_side_effect_policy,
    normalize_manifest_live_allowlist,
    manifest_live_allowlist_allows_tool,
    manifest_live_allowlist_allows_action,
    manifest_live_max_actions,
    profile_allows_live_side_effects,
    build_live_executed_audit_event,
    build_live_blocked_audit_event,
)


class TestErrorCodes(unittest.TestCase):
    def test_all_error_codes_defined(self):
        expected = {
            "LIVE_SIDE_EFFECTS_DISABLED",
            "LIVE_PROFILE_NOT_ALLOWED",
            "LIVE_TOOL_NOT_ALLOWED",
            "LIVE_MANIFEST_NOT_ALLOWED",
            "PENDING_ACTION_NOT_APPROVED",
            "IDEMPOTENCY_KEY_REQUIRED",
            "DUPLICATE_SIDE_EFFECT_BLOCKED",
            "LIVE_GUARDRAIL_FAILED",
            "TYPED_CONFIRMATION_REQUIRED",
            "LIVE_EVIDENCE_WRITE_FAILED",
        }
        self.assertEqual(set(ALL_ERROR_CODES), expected)

    def test_error_code_constants_are_strings(self):
        for code in ALL_ERROR_CODES:
            self.assertIsInstance(code, str)
            self.assertTrue(code)


class TestDefaultPolicy(unittest.TestCase):
    def test_policy_enabled_is_false_by_default(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        self.assertFalse(policy["enabled"])

    def test_policy_default_dry_run(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        self.assertTrue(policy["default_dry_run"])

    def test_policy_allowed_profiles_is_live_only(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        self.assertEqual(policy["allowed_profiles"], ["live"])

    def test_policy_all_safety_flags_true(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        for key in (
            "require_operator_approval",
            "require_typed_confirmation",
            "require_idempotency_key",
            "require_guardrail",
            "require_manifest_allowlist",
            "require_tool_allowlist",
        ):
            self.assertTrue(policy[key], key)

    def test_normalize_policy_with_none_returns_default(self):
        policy = normalize_live_side_effect_policy(None)
        self.assertFalse(policy["enabled"])

    def test_normalize_policy_ignores_unknown_keys(self):
        policy = normalize_live_side_effect_policy({"live_side_effect_execution": {"unknown_key": True, "enabled": False}})
        self.assertNotIn("unknown_key", policy)


class TestProfileAllowance(unittest.TestCase):
    def test_demo_blocks_live_side_effects(self):
        self.assertFalse(profile_allows_live_side_effects("demo"))

    def test_release_blocks_live_side_effects(self):
        self.assertFalse(profile_allows_live_side_effects("release"))

    def test_pilot_blocks_live_side_effects(self):
        self.assertFalse(profile_allows_live_side_effects("pilot"))

    def test_dev_blocks_live_side_effects(self):
        self.assertFalse(profile_allows_live_side_effects("dev"))

    def test_test_blocks_live_side_effects(self):
        self.assertFalse(profile_allows_live_side_effects("test"))

    def test_live_profile_name_alone_returns_true(self):
        self.assertTrue(profile_allows_live_side_effects("live"))

    def test_live_profile_with_flag_false_returns_false(self):
        self.assertFalse(profile_allows_live_side_effects("live", {"allow_live_side_effects": False}))

    def test_live_profile_with_flag_true_returns_true(self):
        self.assertTrue(profile_allows_live_side_effects("live", {"allow_live_side_effects": True}))


class TestManifestLiveAllowlist(unittest.TestCase):
    def test_default_allowlist_disabled(self):
        policy = normalize_manifest_live_allowlist(None)
        self.assertFalse(policy["enabled"])

    def test_default_allowlist_max_live_actions_is_one(self):
        policy = normalize_manifest_live_allowlist(None)
        self.assertEqual(policy["max_live_actions"], 1)

    def test_default_requires_operator_confirmation(self):
        policy = normalize_manifest_live_allowlist(None)
        self.assertTrue(policy["requires_operator_confirmation"])

    def test_allows_tool_when_enabled_and_listed(self):
        live = {"enabled": True, "allowed_tools": ["gmail/send"]}
        self.assertTrue(manifest_live_allowlist_allows_tool(live, "gmail/send"))

    def test_blocks_tool_when_not_listed(self):
        live = {"enabled": True, "allowed_tools": ["sheet/create"]}
        self.assertFalse(manifest_live_allowlist_allows_tool(live, "gmail/send"))

    def test_blocks_tool_when_disabled(self):
        live = {"enabled": False, "allowed_tools": ["gmail/send"]}
        self.assertFalse(manifest_live_allowlist_allows_tool(live, "gmail/send"))

    def test_allows_action_when_listed(self):
        live = {"enabled": True, "allowed_actions": ["send_customer_reply"]}
        self.assertTrue(manifest_live_allowlist_allows_action(live, "send_customer_reply"))

    def test_blocks_action_when_not_listed(self):
        live = {"enabled": True, "allowed_actions": ["send_customer_reply"]}
        self.assertFalse(manifest_live_allowlist_allows_action(live, "other_action"))

    def test_allows_any_action_when_allowed_actions_empty(self):
        live = {"enabled": True, "allowed_tools": ["sheet/create"], "allowed_actions": []}
        self.assertTrue(manifest_live_allowlist_allows_action(live, "any_action_id"))

    def test_max_live_actions_default(self):
        self.assertEqual(manifest_live_max_actions(None), 1)

    def test_max_live_actions_custom(self):
        self.assertEqual(manifest_live_max_actions({"max_live_actions": 3}), 3)

    def test_legacy_requires_approval_maps_to_requires_operator_confirmation(self):
        live = {"requires_approval": True}
        policy = normalize_manifest_live_allowlist(live)
        self.assertTrue(policy["requires_operator_confirmation"])


class TestPendingActionLiveFields(unittest.TestCase):
    def test_normalize_adds_all_required_fields(self):
        action = {"action_id": "pa_1", "tool": "sheet/create", "status": "APPROVED"}
        normalized = normalize_live_capable_pending_action(action)
        for key in LIVE_CAPABLE_PENDING_ACTION_FIELDS:
            self.assertIn(key, normalized)

    def test_normalize_does_not_overwrite_existing_fields(self):
        action = {"action_id": "pa_1", "live_capable": True, "idempotency_key": "ikey_123"}
        normalized = normalize_live_capable_pending_action(action)
        self.assertTrue(normalized["live_capable"])
        self.assertEqual(normalized["idempotency_key"], "ikey_123")

    def test_mark_live_capable_sets_flag(self):
        action = {"action_id": "pa_1"}
        mark_pending_action_live_capable(action)
        self.assertTrue(action["live_capable"])

    def test_mark_live_executed_sets_flags(self):
        action = {"action_id": "pa_1", "live_executed": False}
        mark_pending_action_live_executed(action, guardrail_result={"ok": True})
        self.assertTrue(action["live_executed"])
        self.assertTrue(action["live_executed_at"])
        self.assertEqual(action["guardrail_result"], {"ok": True})

    def test_mark_dry_run_executed(self):
        action = {"action_id": "pa_1"}
        mark_pending_action_dry_run_executed(action)
        self.assertTrue(action["dry_run_executed"])


class TestAuditEventBuilders(unittest.TestCase):
    def test_executed_event_has_correct_type(self):
        event = build_live_executed_audit_event(
            frame_id="frame_1",
            action_id="pa_1",
            tool="sheet/create",
            idempotency_key="ikey_1",
            approved_by="operator",
            guardrail_result={"ok": True},
        )
        self.assertEqual(event["event_type"], "LIVE_SIDE_EFFECT_EXECUTED")

    def test_executed_event_contains_all_required_fields(self):
        event = build_live_executed_audit_event(
            frame_id="frame_1",
            action_id="pa_1",
            tool="sheet/create",
            idempotency_key="ikey_1",
            approved_by="operator",
            guardrail_result={"ok": True},
        )
        for field in ("frame_id", "action_id", "tool", "idempotency_key", "approved_by", "executed_at", "guardrail_result"):
            self.assertIn(field, event)

    def test_blocked_event_has_correct_type(self):
        event = build_live_blocked_audit_event(
            frame_id="frame_1",
            action_id="pa_1",
            tool="sheet/create",
            reason="Profile does not allow.",
            error_code=LIVE_PROFILE_NOT_ALLOWED,
        )
        self.assertEqual(event["event_type"], "LIVE_SIDE_EFFECT_BLOCKED")

    def test_blocked_event_contains_error_code(self):
        event = build_live_blocked_audit_event(
            frame_id="frame_1",
            action_id="pa_1",
            tool="sheet/create",
            reason="blocked",
            error_code=LIVE_SIDE_EFFECTS_DISABLED,
        )
        self.assertEqual(event["error_code"], LIVE_SIDE_EFFECTS_DISABLED)


if __name__ == "__main__":
    unittest.main()
