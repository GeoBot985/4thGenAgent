from __future__ import annotations

import unittest

from runtime.live_side_effect_contract import (
    DUPLICATE_SIDE_EFFECT_BLOCKED,
    IDEMPOTENCY_KEY_REQUIRED,
    check_idempotency_key_not_used,
    check_idempotency_key_present,
)


class TestIdempotencyKeyPresent(unittest.TestCase):
    def test_missing_key_fails(self):
        result = check_idempotency_key_present({"action_id": "pa_1"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_empty_string_key_fails(self):
        result = check_idempotency_key_present({"action_id": "pa_1", "idempotency_key": ""})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_whitespace_key_fails(self):
        result = check_idempotency_key_present({"action_id": "pa_1", "idempotency_key": "   "})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)

    def test_valid_key_passes(self):
        result = check_idempotency_key_present({"action_id": "pa_1", "idempotency_key": "ikey_abc"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["idempotency_key"], "ikey_abc")


class TestIdempotencyKeyNotUsed(unittest.TestCase):
    def _action(self, key: str = "ikey_1", action_id: str = "pa_new") -> dict:
        return {
            "action_id": action_id,
            "idempotency_key": key,
            "live_executed": False,
        }

    def test_no_executed_actions_passes(self):
        result = check_idempotency_key_not_used(self._action(), [])
        self.assertTrue(result["ok"])

    def test_different_key_in_executed_passes(self):
        executed = [{"action_id": "pa_old", "idempotency_key": "other_key", "status": "EXECUTED"}]
        result = check_idempotency_key_not_used(self._action("ikey_1"), executed)
        self.assertTrue(result["ok"])

    def test_same_key_different_action_id_blocks(self):
        executed = [{"action_id": "pa_old", "idempotency_key": "ikey_1", "status": "EXECUTED"}]
        result = check_idempotency_key_not_used(self._action("ikey_1", "pa_new"), executed)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_same_key_same_action_id_passes(self):
        # The same action re-checking itself is allowed (idempotent re-check)
        executed = [{"action_id": "pa_same", "idempotency_key": "ikey_1", "status": "EXECUTED"}]
        result = check_idempotency_key_not_used(self._action("ikey_1", "pa_same"), executed)
        self.assertTrue(result["ok"])

    def test_non_executed_status_does_not_block(self):
        executed = [{"action_id": "pa_other", "idempotency_key": "ikey_1", "status": "FAILED"}]
        result = check_idempotency_key_not_used(self._action("ikey_1"), executed)
        self.assertTrue(result["ok"])

    def test_already_live_executed_flag_blocks(self):
        action = self._action()
        action["live_executed"] = True
        result = check_idempotency_key_not_used(action, [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], DUPLICATE_SIDE_EFFECT_BLOCKED)

    def test_missing_key_in_action_fails_with_required_code(self):
        action = {"action_id": "pa_1", "idempotency_key": ""}
        result = check_idempotency_key_not_used(action, [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], IDEMPOTENCY_KEY_REQUIRED)


if __name__ == "__main__":
    unittest.main()
