from __future__ import annotations

import unittest

from runtime.live_guardrails import (
    guardrail_blocked,
    guardrail_sheet_create,
    guardrail_sheet_write,
    run_live_guardrail,
)
from runtime.live_side_effect_contract import (
    LIVE_GUARDRAIL_FAILED,
    run_live_side_effect_preflight,
)


def _make_action(args: dict | None = None) -> dict:
    return {
        "action_id": "pa_1",
        "tool": "sheet/create",
        "status": "APPROVED",
        "approved_by": "operator",
        "approved_at": "2026-05-20T10:00:00Z",
        "idempotency_key": "ikey_1",
        "live_executed": False,
        "args": args or {},
    }


class TestGuardrailInterface(unittest.TestCase):
    def test_guardrail_result_has_ok_field(self):
        result = run_live_guardrail("sheet_create", _make_action({"title": "Test"}), {})
        self.assertIn("ok", result)

    def test_guardrail_result_has_guardrail_field(self):
        result = run_live_guardrail("sheet_create", _make_action({"title": "Test"}), {})
        self.assertIn("guardrail", result)

    def test_guardrail_result_has_checks_list(self):
        result = run_live_guardrail("sheet_create", _make_action({"title": "Test"}), {})
        self.assertIsInstance(result.get("checks"), list)

    def test_unknown_guardrail_name_falls_back_to_blocked(self):
        result = run_live_guardrail("nonexistent_guardrail", _make_action(), {})
        self.assertFalse(result["ok"])

    def test_blocked_guardrail_always_fails(self):
        result = guardrail_blocked(_make_action(), {})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


class TestSheetCreateGuardrail(unittest.TestCase):
    def test_valid_title_passes(self):
        result = guardrail_sheet_create(_make_action({"title": "Invoice Report 2026"}), {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["guardrail"], "sheet_create")

    def test_missing_title_fails(self):
        result = guardrail_sheet_create(_make_action({"title": ""}), {})
        self.assertFalse(result["ok"])

    def test_title_too_long_fails(self):
        result = guardrail_sheet_create(_make_action({"title": "A" * 121}), {})
        self.assertFalse(result["ok"])

    def test_title_with_path_separator_fails(self):
        result = guardrail_sheet_create(_make_action({"title": "path/to/sheet"}), {})
        self.assertFalse(result["ok"])

    def test_title_starting_with_test_delete_fails(self):
        result = guardrail_sheet_create(_make_action({"title": "test-delete-my-sheet"}), {})
        self.assertFalse(result["ok"])

    def test_checks_list_contains_named_checks(self):
        result = guardrail_sheet_create(_make_action({"title": "Good Title"}), {})
        names = [c["name"] for c in result["checks"]]
        self.assertIn("title_present", names)
        self.assertIn("title_length", names)


class TestSheetWriteGuardrail(unittest.TestCase):
    def _valid_args(self) -> dict:
        return {
            "spreadsheet_id": "sheet_abc",
            "range_name": "Sheet1!A1:B2",
            "values_json": '[[\"a\", \"b\"]]',
            "mode": "append",
        }

    def test_valid_write_passes(self):
        result = guardrail_sheet_write(_make_action(self._valid_args()), {})
        self.assertTrue(result["ok"])

    def test_missing_spreadsheet_id_fails(self):
        args = {**self._valid_args(), "spreadsheet_id": ""}
        result = guardrail_sheet_write(_make_action(args), {})
        self.assertFalse(result["ok"])

    def test_invalid_values_json_fails(self):
        args = {**self._valid_args(), "values_json": "not json"}
        result = guardrail_sheet_write(_make_action(args), {})
        self.assertFalse(result["ok"])

    def test_invalid_mode_fails(self):
        args = {**self._valid_args(), "mode": "delete"}
        result = guardrail_sheet_write(_make_action(args), {})
        self.assertFalse(result["ok"])

    def test_too_many_rows_fails(self):
        rows = [["a", "b"]] * 101
        import json
        args = {**self._valid_args(), "values_json": json.dumps(rows)}
        result = guardrail_sheet_write(_make_action(args), {})
        self.assertFalse(result["ok"])


class TestGuardrailBlocksPreflightWhenToolHasBlockedGuardrail(unittest.TestCase):
    def test_blocked_guardrail_name_causes_preflight_to_fail(self):
        result = run_live_side_effect_preflight(
            pending_action={
                "action_id": "pa_1",
                "tool": "sheet/create",
                "status": "APPROVED",
                "approved_by": "operator",
                "approved_at": "2026-05-20T10:00:00Z",
                "idempotency_key": "ikey_1",
                "live_executed": False,
            },
            tool_spec={
                "side_effect": True,
                "requires_approval": True,
                "allow_live_side_effect": True,
                "live_guardrail": "blocked",
            },
            manifest_live_execution={"enabled": True, "allowed_tools": ["sheet/create"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            dry_run=False,
        )
        self.assertFalse(result["ok"])
        codes = [c["error_code"] for c in result["failed_checks"]]
        self.assertIn(LIVE_GUARDRAIL_FAILED, codes)


if __name__ == "__main__":
    unittest.main()
