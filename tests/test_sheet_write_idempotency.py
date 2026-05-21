from __future__ import annotations

import unittest

from runtime.live_side_effect_contract import (
    DUPLICATE_SIDE_EFFECT_BLOCKED,
    IDEMPOTENCY_KEY_REQUIRED,
    check_idempotency_key_not_used,
    check_idempotency_key_present,
)
from runtime.sheet_write_tool import (
    build_sheet_write_pending_action,
    sheet_write_live_execute,
)


def _approved_action(
    *,
    action_id: str = "pa-001",
    idempotency_key: str = "idem-sheet-001",
    spreadsheet_id: str = "sheet-abc123",
    range_name: str = "ExceptionRegister!A:H",
) -> dict:
    return build_sheet_write_pending_action(
        action_id=action_id,
        business_ref="INV-10042",
        idempotency_key=idempotency_key,
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        rows=[["INV-10042", "PO mismatch", "open"]],
        write_mode="append",
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
    range_name = kwargs.get("range_name", "Sheet1!A:H")
    rows = kwargs.get("rows", [])
    return {
        "ok": True,
        "updated_range": f"{range_name.split('!')[0]}!A42:H{41 + len(rows)}",
        "row_count": len(rows),
    }


class TestIdempotencyKeyRequired(unittest.TestCase):
    def test_present_returns_ok(self):
        action = _approved_action(idempotency_key="idem-001")
        result = check_idempotency_key_present(action)
        self.assertTrue(result["ok"])

    def test_empty_string_returns_error(self):
        action = _approved_action(idempotency_key="")
        action["idempotency_key"] = ""
        result = check_idempotency_key_present(action)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_missing_key_returns_error(self):
        action = _approved_action()
        del action["idempotency_key"]
        result = check_idempotency_key_present(action)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)


class TestIdempotencyKeyNotUsed(unittest.TestCase):
    def test_no_executed_actions_returns_ok(self):
        action = _approved_action(idempotency_key="idem-fresh-001")
        result = check_idempotency_key_not_used(action, [])
        self.assertTrue(result["ok"])

    def test_different_key_in_executed_returns_ok(self):
        action = _approved_action(idempotency_key="idem-new-001")
        executed = [{"action_id": "pa-old", "idempotency_key": "idem-old-001", "status": "EXECUTED"}]
        result = check_idempotency_key_not_used(action, executed)
        self.assertTrue(result["ok"])

    def test_duplicate_key_in_executed_returns_blocked(self):
        action = _approved_action(action_id="pa-new", idempotency_key="idem-dup-001")
        executed = [{"action_id": "pa-old", "idempotency_key": "idem-dup-001", "status": "EXECUTED"}]
        result = check_idempotency_key_not_used(action, executed)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_same_action_id_does_not_block_self(self):
        action = _approved_action(action_id="pa-same", idempotency_key="idem-same-001")
        executed = [{"action_id": "pa-same", "idempotency_key": "idem-same-001", "status": "EXECUTED"}]
        result = check_idempotency_key_not_used(action, executed)
        self.assertTrue(result["ok"])

    def test_already_live_executed_action_blocks(self):
        action = _approved_action(idempotency_key="idem-exec-001")
        action["live_executed"] = True
        result = check_idempotency_key_not_used(action, [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)


class TestSheetWriteIdempotencyEnforcement(unittest.TestCase):
    def test_missing_idempotency_key_blocks_live_execute(self):
        action = _approved_action(idempotency_key="")
        action["idempotency_key"] = ""
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
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_duplicate_idempotency_key_blocks_live_execute(self):
        action = _approved_action(action_id="pa-new-001", idempotency_key="idem-dup-sheet-001")
        executed = [
            {
                "action_id": "pa-old-001",
                "idempotency_key": "idem-dup-sheet-001",
                "status": "EXECUTED",
            }
        ]
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            executed_actions=executed,
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_already_executed_action_blocks(self):
        action = _approved_action(idempotency_key="idem-already-001")
        action["live_executed"] = True
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
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_first_execute_succeeds_and_second_is_blocked(self):
        action1 = _approved_action(action_id="pa-001", idempotency_key="idem-once-001")
        result1 = sheet_write_live_execute(
            action1,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertTrue(result1["ok"])

        # Second attempt using the same action (already live_executed=True)
        result2 = sheet_write_live_execute(
            action1,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertFalse(result2["ok"])
        self.assertEqual(result2["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_unique_idempotency_key_allows_execute(self):
        action = _approved_action(action_id="pa-unique", idempotency_key="idem-unique-xyz-999")
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            executed_actions=[],
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=_mock_write_ok,
        )
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
