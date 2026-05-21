from __future__ import annotations

import unittest

from src.taskframe_cli import build_parser
from runtime.live_side_effect_contract import (
    TYPED_CONFIRMATION_REQUIRED,
    live_execute_confirmation_phrase,
)


class TestExecuteApprovedCliArgs(unittest.TestCase):
    def _parse(self, args: list[str]) -> object:
        parser = build_parser()
        return parser.parse_args(args)

    def test_execute_approved_accepts_dry_run_flag(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1", "--dry-run"])
        self.assertTrue(ns.dry_run)

    def test_execute_approved_accepts_live_flag(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1", "--live"])
        self.assertTrue(ns.live)

    def test_execute_approved_accepts_confirm_arg(self):
        ns = self._parse([
            "execute-approved",
            "--frame-id", "f1",
            "--action-id", "a1",
            "--live",
            "--confirm", "LIVE-EXECUTE",
        ])
        self.assertEqual(ns.confirm, "LIVE-EXECUTE")

    def test_execute_approved_default_is_not_live(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1"])
        self.assertFalse(ns.live)

    def test_execute_approved_default_dry_run_is_false(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1"])
        self.assertFalse(ns.dry_run)

    def test_execute_approved_default_confirm_is_empty(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1"])
        self.assertEqual(ns.confirm, "")

    def test_live_without_confirm_is_missing_phrase(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1", "--live"])
        self.assertEqual(ns.confirm, "")

    def test_dry_run_is_default_safe_path(self):
        ns = self._parse(["execute-approved", "--frame-id", "f1", "--action-id", "a1", "--dry-run"])
        self.assertFalse(ns.live)
        self.assertTrue(ns.dry_run)


class TestConfirmationPhrase(unittest.TestCase):
    def test_phrase_is_live_execute(self):
        self.assertEqual(live_execute_confirmation_phrase(), "LIVE-EXECUTE")

    def test_wrong_confirmation_fails_check(self):
        from runtime.live_side_effect_contract import check_typed_confirmation
        result = check_typed_confirmation("wrong")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], TYPED_CONFIRMATION_REQUIRED)

    def test_correct_confirmation_passes(self):
        from runtime.live_side_effect_contract import check_typed_confirmation
        result = check_typed_confirmation("LIVE-EXECUTE")
        self.assertTrue(result["ok"])

    def test_empty_confirmation_fails(self):
        from runtime.live_side_effect_contract import check_typed_confirmation
        result = check_typed_confirmation("")
        self.assertFalse(result["ok"])

    def test_case_sensitive_confirmation(self):
        from runtime.live_side_effect_contract import check_typed_confirmation
        result = check_typed_confirmation("live-execute")
        self.assertFalse(result["ok"])


class TestLiveExecutionWithoutExplicitFlag(unittest.TestCase):
    def test_preflight_fails_when_dry_run_not_false(self):
        from runtime.live_side_effect_contract import run_live_side_effect_preflight, LIVE_SIDE_EFFECTS_DISABLED
        result = run_live_side_effect_preflight(
            pending_action={
                "action_id": "pa_1",
                "tool": "sheet/create",
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
                "live_guardrail": "sheet_create",
            },
            manifest_live_execution={"enabled": True, "allowed_tools": ["sheet/create"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            dry_run=True,
        )
        self.assertFalse(result["ok"])
        codes = [c["error_code"] for c in result["failed_checks"]]
        self.assertIn(LIVE_SIDE_EFFECTS_DISABLED, codes)


if __name__ == "__main__":
    unittest.main()
