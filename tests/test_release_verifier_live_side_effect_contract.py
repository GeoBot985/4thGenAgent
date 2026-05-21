from __future__ import annotations

import unittest
from pathlib import Path

from runtime.live_side_effect_contract import (
    ALL_ERROR_CODES,
    LIVE_SIDE_EFFECT_EXECUTION_POLICY,
    profile_allows_live_side_effects,
    run_live_side_effect_preflight,
)
from runtime.live_execution import normalize_live_execution_policy
from runtime.runtime_environment import (
    list_runtime_profiles,
    load_runtime_profile,
)


ROOT = Path(__file__).resolve().parents[1]


class TestContractFileExists(unittest.TestCase):
    def test_contract_module_exists(self):
        self.assertTrue((ROOT / "runtime" / "live_side_effect_contract.py").is_file())

    def test_reports_module_exists(self):
        self.assertTrue((ROOT / "runtime" / "live_execution_reports.py").is_file())

    def test_contract_doc_exists(self):
        self.assertTrue((ROOT / "docs" / "live_side_effect_execution_contract.md").is_file())


class TestDefaultPolicyBlocksLiveSideEffects(unittest.TestCase):
    def test_policy_enabled_is_false(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        self.assertFalse(policy["enabled"])

    def test_policy_default_dry_run_is_true(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        self.assertTrue(policy["default_dry_run"])

    def test_policy_only_allows_live_profile(self):
        policy = LIVE_SIDE_EFFECT_EXECUTION_POLICY["live_side_effect_execution"]
        self.assertEqual(policy["allowed_profiles"], ["live"])


class TestProfilesBlockLiveSideEffects(unittest.TestCase):
    def _profile_data(self, name: str) -> dict:
        return load_runtime_profile(profile_name=name)

    def test_demo_profile_blocks_live_side_effects(self):
        profile = self._profile_data("demo")
        self.assertFalse(profile.get("allow_live_side_effects"))
        self.assertFalse(profile_allows_live_side_effects("demo", profile))

    def test_release_profile_blocks_live_side_effects(self):
        profile = self._profile_data("release")
        self.assertFalse(profile.get("allow_live_side_effects"))
        self.assertFalse(profile_allows_live_side_effects("release", profile))

    def test_pilot_profile_blocks_live_side_effects(self):
        profile = self._profile_data("pilot")
        self.assertFalse(profile.get("allow_live_side_effects"))
        self.assertFalse(profile_allows_live_side_effects("pilot", profile))

    def test_all_non_live_profiles_block_live_side_effects(self):
        profiles = list_runtime_profiles()
        for p in profiles:
            if p["profile"] != "live":
                self.assertFalse(
                    profile_allows_live_side_effects(p["profile"], p),
                    f"Profile {p['profile']} should block live side effects",
                )


class TestPreflightRequiresExplicitLive(unittest.TestCase):
    def _base_kwargs(self) -> dict:
        return dict(
            pending_action={
                "action_id": "pa_1",
                "tool": "gmail/send",
                "status": "APPROVED",
                "approved_by": "op",
                "approved_at": "2026-05-20T10:00:00Z",
                "idempotency_key": "ikey_1",
                "live_executed": False,
            },
            tool_spec={
                "side_effect": True,
                "requires_approval": True,
                "allow_live_side_effect": True,
                "live_guardrail": "gmail_send_guardrail",
            },
            manifest_live_execution={"enabled": True, "allowed_tools": ["gmail/send"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            executed_actions=[],
        )

    def test_live_execution_fails_without_explicit_live_flag(self):
        kwargs = self._base_kwargs()
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_live_execution_fails_when_dry_run_true(self):
        kwargs = {**self._base_kwargs(), "dry_run": True}
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_live_execution_fails_without_typed_confirmation(self):
        kwargs = {**self._base_kwargs(), "dry_run": False, "confirmation": "wrong"}
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_live_execution_fails_when_manifest_does_not_allow_tool(self):
        kwargs = {
            **self._base_kwargs(),
            "dry_run": False,
            "manifest_live_execution": {"enabled": True, "allowed_tools": ["sheet/create"]},
        }
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_live_execution_fails_when_tool_registry_blocks(self):
        kwargs = {
            **self._base_kwargs(),
            "dry_run": False,
            "tool_spec": {
                "side_effect": True,
                "requires_approval": True,
                "allow_live_side_effect": False,
                "live_guardrail": "gmail_send_guardrail",
            },
        }
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_live_execution_fails_when_idempotency_key_missing(self):
        kwargs = {
            **self._base_kwargs(),
            "dry_run": False,
            "pending_action": {
                "action_id": "pa_1",
                "tool": "gmail/send",
                "status": "APPROVED",
                "approved_by": "op",
                "approved_at": "2026-05-20T10:00:00Z",
                "idempotency_key": "",
                "live_executed": False,
            },
        }
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_duplicate_idempotency_key_is_blocked(self):
        kwargs = {
            **self._base_kwargs(),
            "dry_run": False,
            "executed_actions": [
                {"action_id": "pa_old", "idempotency_key": "ikey_1", "status": "EXECUTED"}
            ],
        }
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])

    def test_guardrail_failure_blocks_execution(self):
        kwargs = {
            **self._base_kwargs(),
            "dry_run": False,
            "tool_spec": {
                "side_effect": True,
                "requires_approval": True,
                "allow_live_side_effect": True,
                "live_guardrail": "blocked",
            },
        }
        result = run_live_side_effect_preflight(**kwargs)
        self.assertFalse(result["ok"])


class TestManifestLiveAllowlistContract(unittest.TestCase):
    def test_default_manifest_policy_disabled(self):
        policy = normalize_live_execution_policy(None)
        self.assertFalse(policy["enabled"])

    def test_manifest_requires_operator_confirmation_default_true(self):
        policy = normalize_live_execution_policy(None)
        self.assertTrue(policy["requires_operator_confirmation"])

    def test_manifest_max_live_actions_default_one(self):
        policy = normalize_live_execution_policy(None)
        self.assertEqual(policy["max_live_actions"], 1)


class TestNoDefaultDemoWorkflowPerformsLiveSideEffects(unittest.TestCase):
    def test_demo_profile_does_not_allow_live_side_effects(self):
        demo_profile = load_runtime_profile(profile_name="demo")
        self.assertFalse(demo_profile.get("allow_live_side_effects"))

    def test_all_error_codes_present(self):
        self.assertEqual(len(ALL_ERROR_CODES), 10)

    def test_live_execution_reports_dir_structure(self):
        reports_module = ROOT / "runtime" / "live_execution_reports.py"
        content = reports_module.read_text(encoding="utf-8")
        self.assertIn("live_execution", content)
        self.assertIn("write_live_execution_report", content)
        self.assertIn("append_live_audit_event", content)


if __name__ == "__main__":
    unittest.main()
