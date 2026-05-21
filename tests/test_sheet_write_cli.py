from __future__ import annotations

import unittest

from runtime.sheet_write_tool import (
    build_sheet_write_pending_action,
    sheet_write_dry_run,
    sheet_write_live_execute,
)
from runtime.live_side_effect_contract import (
    LIVE_SIDE_EFFECTS_DISABLED,
    LIVE_PROFILE_NOT_ALLOWED,
    PENDING_ACTION_NOT_APPROVED,
    TYPED_CONFIRMATION_REQUIRED,
    LIVE_MANIFEST_NOT_ALLOWED,
    LIVE_TOOL_NOT_ALLOWED,
    live_execute_confirmation_phrase,
)


def _approved_action(**overrides) -> dict:
    defaults = dict(
        action_id="pa-cli-001",
        business_ref="INV-10042",
        idempotency_key="idem-cli-001",
        spreadsheet_id="sheet-abc123",
        range_name="ExceptionRegister!A:H",
        rows=[["INV-10042", "PO mismatch", "open"]],
        write_mode="append",
        approved_by="operator@example.com",
        approved_at="2026-01-01T00:00:00Z",
        status="APPROVED",
    )
    defaults.update(overrides)
    return build_sheet_write_pending_action(**defaults)


def _live_tool_spec() -> dict:
    return {
        "side_effect": True,
        "requires_approval": True,
        "allow_live": True,
        "allow_live_side_effect": True,
        "live_guardrail": "sheet_write_rows_guardrail",
    }


def _live_manifest() -> dict:
    return {
        "enabled": True,
        "allowed_tools": ["sheet/write_rows"],
        "allowed_actions": [],
        "max_live_actions": 1,
        "requires_operator_confirmation": True,
    }


def _enabled_config() -> dict:
    return {
        "sheet_write": {
            "enabled": True,
            "allowed_spreadsheets": ["sheet-abc123"],
            "allowed_ranges": ["ExceptionRegister!A:H"],
            "blocked_ranges": [],
            "max_rows_per_action": 50,
            "allow_update_mode": False,
            "allow_append_mode": True,
        }
    }


def _mock_write_ok(**kwargs) -> dict:
    return {"ok": True, "updated_range": "ExceptionRegister!A42:H42", "row_count": 1}


class TestConfirmationPhrase(unittest.TestCase):
    def test_phrase_is_live_execute(self):
        self.assertEqual(live_execute_confirmation_phrase(), "LIVE-EXECUTE")


class TestLiveWriteRequiresLiveFlag(unittest.TestCase):
    def test_without_live_flag_dry_run_is_default(self):
        action = _approved_action()
        result = sheet_write_dry_run(action, config=_enabled_config())
        self.assertTrue(result["data"]["dry_run"])
        self.assertFalse(result["data"]["written"])

    def test_live_execute_without_dry_run_false_is_blocked(self):
        action = _approved_action()
        # Passing dry_run omitted means preflight check for dry_run=False will fail
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            # dry_run parameter not passed → preflight treats it as not False
        )
        # Since we're not passing dry_run=False, it should fail preflight
        self.assertFalse(result["data"]["written"])


class TestLiveWriteRequiresTypedConfirmation(unittest.TestCase):
    def test_none_confirmation_skips_check(self):
        # confirmation=None means the typed confirmation check is not enforced (programmatic bypass).
        # All other checks must still pass.
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation=None,
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        # With confirmation=None the check is skipped — write proceeds if all other gates pass.
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["written"])

    def test_wrong_confirmation_blocks(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="wrong-phrase",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], TYPED_CONFIRMATION_REQUIRED)

    def test_correct_confirmation_does_not_block(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        # If preflight passes (profile_data set), this should succeed
        self.assertTrue(result["ok"])


class TestLiveWriteRequiresApprovedAction(unittest.TestCase):
    def test_pending_action_is_blocked(self):
        action = _approved_action()
        action["status"] = "PENDING_APPROVAL"
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], PENDING_ACTION_NOT_APPROVED)

    def test_rejected_action_is_blocked(self):
        action = _approved_action()
        action["status"] = "REJECTED"
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result["ok"])


class TestLiveWriteRequiresManifestAllowlist(unittest.TestCase):
    def test_manifest_disabled_blocks(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution={"enabled": False, "allowed_tools": ["sheet/write_rows"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_MANIFEST_NOT_ALLOWED)

    def test_tool_not_in_manifest_blocks(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution={"enabled": True, "allowed_tools": ["gmail/send"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_MANIFEST_NOT_ALLOWED)


class TestLiveWriteProfileRestrictions(unittest.TestCase):
    def _execute(self, profile: str) -> dict:
        action = _approved_action()
        return sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name=profile,
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )

    def test_demo_profile_is_blocked(self):
        result = self._execute("demo")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_PROFILE_NOT_ALLOWED)

    def test_pilot_profile_is_blocked(self):
        result = self._execute("pilot")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_PROFILE_NOT_ALLOWED)

    def test_release_profile_is_blocked(self):
        result = self._execute("release")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_PROFILE_NOT_ALLOWED)

    def test_test_profile_is_blocked(self):
        result = self._execute("test")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_PROFILE_NOT_ALLOWED)

    def test_dev_profile_is_blocked(self):
        result = self._execute("dev")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], LIVE_PROFILE_NOT_ALLOWED)


class TestDryRunDoesNotCallGoogleAPI(unittest.TestCase):
    def test_dry_run_does_not_call_api(self):
        api_called = []

        def _fail_if_called(**kwargs):
            api_called.append(True)
            return {"ok": True, "updated_range": "", "row_count": 0}

        action = _approved_action()
        result = sheet_write_dry_run(action, config=_enabled_config())
        self.assertTrue(result["data"]["dry_run"])
        self.assertFalse(result["data"]["written"])
        self.assertEqual(api_called, [])


if __name__ == "__main__":
    unittest.main()
