from __future__ import annotations

import tempfile
import unittest

from runtime.live_side_effect_execution import (
    V1_BLOCKED_TOOLS,
    V1_EXECUTABLE_TOOLS,
    TOOL_EXPLICITLY_BLOCKED,
    TOOL_NOT_V1_EXECUTABLE,
    build_live_side_effect_preflight,
)


def _live_write_profile_data() -> dict:
    return {"allow_live_side_effects": True}


class TestV1BlockedToolsNotExecutable(unittest.TestCase):
    def _preflight(self, tool: str, tmpdir: str) -> dict:
        return build_live_side_effect_preflight(
            pending_action={
                "frame_id": "f1",
                "action_id": "a1",
                "tool": tool,
                "status": "APPROVED",
                "approved_by": "op",
                "approved_at": "2026-05-20T10:00:00Z",
                "worker_identity": "worker_1",
                "idempotency_key": "ikey_1",
                "prepared_payload_hash": "abc123",
                "target_ref": "spreadsheet_1",
                "business_ref": "inv-001",
                "rollback_plan": {"note": "delete rows A2:D10"},
            },
            profile_name="controlled_live_write",
            profile_data=_live_write_profile_data(),
            runtime_data_dir=tmpdir,
        )

    def test_gmail_send_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("gmail/send", tmp)
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(TOOL_EXPLICITLY_BLOCKED, codes)

    def test_gmail_draft_send_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("gmail/draft_send", tmp)
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(TOOL_EXPLICITLY_BLOCKED, codes)

    def test_calendar_create_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("calendar/create", tmp)
            self.assertFalse(result["ok"])

    def test_calendar_update_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("calendar/update", tmp)
            self.assertFalse(result["ok"])

    def test_calendar_delete_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("calendar/delete", tmp)
            self.assertFalse(result["ok"])

    def test_rpa_run_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("rpa/run", tmp)
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(TOOL_EXPLICITLY_BLOCKED, codes)

    def test_rpa_click_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("rpa/click", tmp)
            self.assertFalse(result["ok"])

    def test_rpa_type_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("rpa/type", tmp)
            self.assertFalse(result["ok"])

    def test_rpa_navigate_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("rpa/navigate", tmp)
            self.assertFalse(result["ok"])

    def test_unknown_tool_not_v1_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("sheet/delete_rows", tmp)
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(TOOL_NOT_V1_EXECUTABLE, codes)

    def test_sheet_write_rows_is_v1_executable(self):
        self.assertIn("sheet/write_rows", V1_EXECUTABLE_TOOLS)

    def test_v1_blocked_tools_contains_gmail_send(self):
        self.assertIn("gmail/send", V1_BLOCKED_TOOLS)

    def test_v1_blocked_tools_contains_rpa_tools(self):
        for tool in ("rpa/run", "rpa/click", "rpa/type", "rpa/navigate"):
            self.assertIn(tool, V1_BLOCKED_TOOLS, f"{tool} should be in V1_BLOCKED_TOOLS")

    def test_blocked_result_has_correct_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight("gmail/send", tmp)
            self.assertIn("ok", result)
            self.assertIn("blocked", result)
            self.assertIn("checks", result)
            self.assertIn("failed_checks", result)
            self.assertTrue(result["blocked"])


if __name__ == "__main__":
    unittest.main()
