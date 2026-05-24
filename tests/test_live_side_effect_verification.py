from __future__ import annotations

import unittest

from runtime.live_side_effect_execution import verify_live_side_effect_result


def _sheet_exec_result(**overrides) -> dict:
    base = {
        "ok": True,
        "type": "sheet_write_rows",
        "tool": "sheet/write_rows",
        "rows_written": 3,
        "target_ref": "spreadsheet_id_abc",
    }
    base.update(overrides)
    return base


def _action(tool: str = "sheet/write_rows", target_ref: str = "spreadsheet_id_abc") -> dict:
    return {
        "action_id": "a1",
        "tool": tool,
        "target_ref": target_ref,
        "status": "EXECUTED",
    }


class TestVerifySheetWriteRowsPass(unittest.TestCase):
    def test_passing_verification(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(),
            pending_action=_action(),
        )
        self.assertTrue(result["ok"])

    def test_result_has_checks(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(),
            pending_action=_action(),
        )
        self.assertIsInstance(result["checks"], list)

    def test_result_has_verified_at(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(),
            pending_action=_action(),
        )
        self.assertTrue(result.get("verified_at"))

    def test_zero_rows_written_passes(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(rows_written=0),
            pending_action=_action(),
        )
        self.assertTrue(result["ok"])


class TestVerifyExecutionNotOk(unittest.TestCase):
    def test_execution_not_ok_fails_verification(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(ok=False),
            pending_action=_action(),
        )
        self.assertFalse(result["ok"])
        failed = [c["name"] for c in result["failed_checks"]]
        self.assertIn("execution_ok", failed)


class TestVerifyToolMismatch(unittest.TestCase):
    def test_tool_mismatch_fails(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(tool="gmail/send"),
            pending_action=_action(tool="sheet/write_rows"),
        )
        self.assertFalse(result["ok"])
        failed = [c["name"] for c in result["failed_checks"]]
        self.assertIn("tool_matches", failed)

    def test_no_tool_in_result_passes_tool_check(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(tool=""),
            pending_action=_action(tool="sheet/write_rows"),
        )
        self.assertTrue(result["ok"])


class TestVerifyTargetRef(unittest.TestCase):
    def test_target_ref_mismatch_fails(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(target_ref="wrong_spreadsheet"),
            pending_action=_action(target_ref="spreadsheet_id_abc"),
        )
        self.assertFalse(result["ok"])
        failed = [c["name"] for c in result["failed_checks"]]
        self.assertIn("target_ref_matches", failed)

    def test_no_target_in_result_passes_target_check(self):
        exec_result = _sheet_exec_result()
        exec_result.pop("target_ref", None)
        result = verify_live_side_effect_result(
            execution_result=exec_result,
            pending_action=_action(target_ref="spreadsheet_id_abc"),
        )
        self.assertTrue(result["ok"])


class TestVerifyRowsWritten(unittest.TestCase):
    def test_negative_rows_fails(self):
        result = verify_live_side_effect_result(
            execution_result=_sheet_exec_result(rows_written=-1),
            pending_action=_action(),
        )
        self.assertFalse(result["ok"])
        failed = [c["name"] for c in result["failed_checks"]]
        self.assertIn("rows_written_non_negative", failed)

    def test_no_rows_written_field_passes(self):
        exec_result = _sheet_exec_result()
        exec_result.pop("rows_written", None)
        result = verify_live_side_effect_result(
            execution_result=exec_result,
            pending_action=_action(),
        )
        self.assertTrue(result["ok"])


class TestVerifyDryRunSimulation(unittest.TestCase):
    def test_dry_run_simulation_type_passes(self):
        result = verify_live_side_effect_result(
            execution_result={"ok": True, "type": "dry_run_simulation", "rows_written": 0},
            pending_action=_action(),
        )
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
