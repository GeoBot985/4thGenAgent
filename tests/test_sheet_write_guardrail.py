from __future__ import annotations

import unittest

from runtime.live_guardrails import guardrail_sheet_write_rows, run_live_guardrail
from runtime.sheet_write_tool import build_sheet_write_pending_action


def _base_action(
    *,
    spreadsheet_id: str = "sheet-abc123",
    range_name: str = "ExceptionRegister!A:H",
    rows: list | None = None,
    write_mode: str = "append",
    business_ref: str = "INV-10042",
    idempotency_key: str = "idem-001",
    status: str = "APPROVED",
) -> dict:
    action = build_sheet_write_pending_action(
        action_id="pa-001",
        business_ref=business_ref,
        idempotency_key=idempotency_key,
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        rows=rows or [["INV-10042", "PO mismatch", "open"]],
        write_mode=write_mode,
    )
    action["status"] = status
    return action


def _live_tool_spec() -> dict:
    return {
        "side_effect": True,
        "requires_approval": True,
        "allow_live": True,
        "allow_live_side_effect": True,
        "live_guardrail": "sheet_write_rows_guardrail",
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


class TestGuardrailSheetWriteRowsBasic(unittest.TestCase):
    def test_all_checks_pass_returns_ok(self):
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=_enabled_config())
        self.assertTrue(result["ok"])
        self.assertEqual(result["guardrail"], "sheet_write_rows_guardrail")
        self.assertIsInstance(result["checks"], list)

    def test_result_has_expected_structure(self):
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=_enabled_config())
        self.assertIn("ok", result)
        self.assertIn("guardrail", result)
        self.assertIn("checks", result)

    def test_all_checks_have_name_ok_message(self):
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=_enabled_config())
        for check in result["checks"]:
            self.assertIn("name", check)
            self.assertIn("ok", check)
            self.assertIn("message", check)


class TestGuardrailActionApproval(unittest.TestCase):
    def test_approved_status_passes(self):
        result = guardrail_sheet_write_rows(_base_action(status="APPROVED"), _live_tool_spec(), config=_enabled_config())
        check = next(c for c in result["checks"] if c["name"] == "action_approved")
        self.assertTrue(check["ok"])

    def test_pending_status_fails(self):
        result = guardrail_sheet_write_rows(_base_action(status="PENDING_APPROVAL"), _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "action_approved")
        self.assertFalse(check["ok"])


class TestGuardrailToolCheck(unittest.TestCase):
    def test_correct_tool_passes(self):
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=_enabled_config())
        check = next(c for c in result["checks"] if c["name"] == "tool_is_sheet_write_rows")
        self.assertTrue(check["ok"])

    def test_wrong_tool_fails(self):
        action = _base_action()
        action["tool"] = "gmail/send"
        result = guardrail_sheet_write_rows(action, _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])


class TestGuardrailConfigEnabled(unittest.TestCase):
    def test_disabled_config_fails(self):
        disabled = {"sheet_write": {"enabled": False, "allow_append_mode": True, "max_rows_per_action": 50}}
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=disabled)
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "sheet_write_config_enabled")
        self.assertFalse(check["ok"])

    def test_no_config_fails(self):
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=None)
        self.assertFalse(result["ok"])


class TestGuardrailSpreadsheetAllowlist(unittest.TestCase):
    def test_allowlisted_spreadsheet_passes(self):
        result = guardrail_sheet_write_rows(_base_action(spreadsheet_id="sheet-abc123"), _live_tool_spec(), config=_enabled_config())
        check = next((c for c in result["checks"] if c["name"] == "spreadsheet_id_allowlisted"), None)
        if check:
            self.assertTrue(check["ok"])

    def test_non_allowlisted_spreadsheet_fails(self):
        result = guardrail_sheet_write_rows(_base_action(spreadsheet_id="sheet-unknown"), _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "spreadsheet_id_allowlisted")
        self.assertFalse(check["ok"])

    def test_no_allowlist_skips_check(self):
        config = {
            "sheet_write": {
                "enabled": True,
                "allowed_spreadsheets": [],
                "allowed_ranges": [],
                "max_rows_per_action": 50,
                "allow_append_mode": True,
                "allow_update_mode": False,
            }
        }
        result = guardrail_sheet_write_rows(_base_action(), _live_tool_spec(), config=config)
        check_names = [c["name"] for c in result["checks"]]
        self.assertNotIn("spreadsheet_id_allowlisted", check_names)


class TestGuardrailRangeChecks(unittest.TestCase):
    def test_allowlisted_range_passes(self):
        result = guardrail_sheet_write_rows(_base_action(range_name="ExceptionRegister!A:H"), _live_tool_spec(), config=_enabled_config())
        check = next((c for c in result["checks"] if c["name"] == "range_allowlisted"), None)
        if check:
            self.assertTrue(check["ok"])

    def test_non_allowlisted_range_fails(self):
        result = guardrail_sheet_write_rows(_base_action(range_name="Ledger!A:I"), _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "range_allowlisted")
        self.assertFalse(check["ok"])

    def test_blocked_range_fails(self):
        config = {
            "sheet_write": {
                "enabled": True,
                "allowed_spreadsheets": [],
                "allowed_ranges": [],
                "blocked_ranges": ["Ledger!A:I"],
                "max_rows_per_action": 50,
                "allow_append_mode": True,
                "allow_update_mode": False,
            }
        }
        result = guardrail_sheet_write_rows(_base_action(range_name="Ledger!A:I"), _live_tool_spec(), config=config)
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "range_not_blocked")
        self.assertFalse(check["ok"])


class TestGuardrailWriteMode(unittest.TestCase):
    def test_append_mode_passes_when_enabled(self):
        result = guardrail_sheet_write_rows(_base_action(write_mode="append"), _live_tool_spec(), config=_enabled_config())
        check = next(c for c in result["checks"] if c["name"] == "write_mode_supported")
        self.assertTrue(check["ok"])

    def test_update_mode_fails_when_disabled(self):
        result = guardrail_sheet_write_rows(_base_action(write_mode="update"), _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "write_mode_supported")
        self.assertFalse(check["ok"])

    def test_unsupported_mode_fails(self):
        result = guardrail_sheet_write_rows(_base_action(write_mode="delete"), _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])


class TestGuardrailRowChecks(unittest.TestCase):
    def test_empty_rows_fails(self):
        action = _base_action()
        action["payload"]["rows"] = []
        result = guardrail_sheet_write_rows(action, _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "rows_not_empty")
        self.assertFalse(check["ok"])

    def test_row_count_within_limit_passes(self):
        rows = [["x"]] * 5
        result = guardrail_sheet_write_rows(_base_action(rows=rows), _live_tool_spec(), config=_enabled_config())
        check = next(c for c in result["checks"] if c["name"] == "row_count_within_limit")
        self.assertTrue(check["ok"])

    def test_row_count_exceeds_limit_fails(self):
        rows = [["x"]] * 51
        result = guardrail_sheet_write_rows(_base_action(rows=rows), _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "row_count_within_limit")
        self.assertFalse(check["ok"])


class TestGuardrailColumnHeaders(unittest.TestCase):
    def test_matching_column_count_passes(self):
        action = _base_action(rows=[["a", "b", "c"]])
        action["payload"]["expected_headers"] = ["H1", "H2", "H3"]
        result = guardrail_sheet_write_rows(action, _live_tool_spec(), config=_enabled_config())
        check = next((c for c in result["checks"] if c["name"] == "column_count_matches_headers"), None)
        if check:
            self.assertTrue(check["ok"])

    def test_mismatched_column_count_fails(self):
        action = _base_action(rows=[["a", "b"]])
        action["payload"]["expected_headers"] = ["H1", "H2", "H3"]
        result = guardrail_sheet_write_rows(action, _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "column_count_matches_headers")
        self.assertFalse(check["ok"])


class TestGuardrailBusinessRefAndIdempotency(unittest.TestCase):
    def test_missing_business_ref_fails(self):
        action = _base_action(business_ref="")
        result = guardrail_sheet_write_rows(action, _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "business_ref_exists")
        self.assertFalse(check["ok"])

    def test_missing_idempotency_key_fails(self):
        action = _base_action(idempotency_key="")
        result = guardrail_sheet_write_rows(action, _live_tool_spec(), config=_enabled_config())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "idempotency_key_present")
        self.assertFalse(check["ok"])


class TestGuardrailDispatcher(unittest.TestCase):
    def test_dispatched_by_run_live_guardrail(self):
        action = _base_action()
        spec = _live_tool_spec()
        result = run_live_guardrail("sheet_write_rows_guardrail", action, spec, config=_enabled_config())
        self.assertEqual(result["guardrail"], "sheet_write_rows_guardrail")

    def test_unknown_guardrail_returns_blocked(self):
        action = _base_action()
        spec = {"live_guardrail": "unknown_guardrail"}
        result = run_live_guardrail("unknown_guardrail", action, spec)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
