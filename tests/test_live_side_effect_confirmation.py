from __future__ import annotations

import tempfile
import unittest

from runtime.live_side_effect_execution import (
    CONFIRMATION_PHRASE_WRONG,
    build_live_side_effect_preflight,
    live_side_effect_confirmation_phrase,
)


def _full_action(overrides: dict | None = None) -> dict:
    action = {
        "frame_id": "frame_abc",
        "action_id": "action_xyz",
        "tool": "sheet/write_rows",
        "status": "APPROVED",
        "approved_by": "operator",
        "approved_at": "2026-05-20T10:00:00Z",
        "worker_identity": "worker_1",
        "idempotency_key": "ikey_confirm_test",
        "prepared_payload_hash": "hash_abc123",
        "target_ref": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
        "business_ref": "inv-0042",
        "rollback_plan": {"action": "delete_rows", "range": "Sheet1!A2:D5"},
    }
    if overrides:
        action.update(overrides)
    return action


class TestConfirmationPhrase(unittest.TestCase):
    def test_phrase_format(self):
        phrase = live_side_effect_confirmation_phrase("frame_1", "action_2", "sheet/write_rows")
        self.assertEqual(phrase, "EXECUTE LIVE sheet/write_rows frame_1 action_2")

    def test_phrase_includes_tool(self):
        phrase = live_side_effect_confirmation_phrase("f", "a", "sheet/write_rows")
        self.assertIn("sheet/write_rows", phrase)

    def test_phrase_includes_frame_id(self):
        phrase = live_side_effect_confirmation_phrase("my_frame", "a", "sheet/write_rows")
        self.assertIn("my_frame", phrase)

    def test_phrase_includes_action_id(self):
        phrase = live_side_effect_confirmation_phrase("f", "my_action", "sheet/write_rows")
        self.assertIn("my_action", phrase)

    def test_phrase_starts_with_execute_live(self):
        phrase = live_side_effect_confirmation_phrase("f", "a", "sheet/write_rows")
        self.assertTrue(phrase.startswith("EXECUTE LIVE"))


class TestConfirmationCheck(unittest.TestCase):
    def _preflight_with_confirm(self, confirmation: str | None, tmpdir: str) -> dict:
        return build_live_side_effect_preflight(
            pending_action=_full_action(),
            profile_name="controlled_live_write",
            profile_data={"allow_live_side_effects": True},
            typed_confirmation=confirmation,
            runtime_data_dir=tmpdir,
        )

    def test_correct_confirmation_passes(self):
        phrase = live_side_effect_confirmation_phrase("frame_abc", "action_xyz", "sheet/write_rows")
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm(phrase, tmp)
            self.assertTrue(result["ok"])

    def test_wrong_confirmation_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm("wrong-phrase", tmp)
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(CONFIRMATION_PHRASE_WRONG, codes)

    def test_no_confirmation_skips_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm(None, tmp)
            check_names = [c["name"] for c in result.get("checks", [])]
            self.assertNotIn("typed_confirmation_matches", check_names)

    def test_empty_confirmation_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm("", tmp)
            self.assertFalse(result["ok"])

    def test_live_execute_old_phrase_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm("LIVE-EXECUTE", tmp)
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(CONFIRMATION_PHRASE_WRONG, codes)

    def test_case_sensitive_confirmation(self):
        phrase = live_side_effect_confirmation_phrase("frame_abc", "action_xyz", "sheet/write_rows")
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm(phrase.lower(), tmp)
            self.assertFalse(result["ok"])

    def test_preflight_result_includes_expected_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._preflight_with_confirm(None, tmp)
            expected = live_side_effect_confirmation_phrase("frame_abc", "action_xyz", "sheet/write_rows")
            self.assertEqual(result.get("confirmation_phrase"), expected)


if __name__ == "__main__":
    unittest.main()
