from __future__ import annotations

import tempfile
import unittest

from runtime.live_side_effect_execution import (
    ROLLBACK_PLAN_MISSING,
    build_live_side_effect_preflight,
)
from runtime.live_execution_ledger import (
    LEDGER_STATUS_EXECUTED,
    append_ledger_entry,
    build_ledger_entry,
    get_ledger_entry,
)


def _full_action(**overrides) -> dict:
    base = {
        "frame_id": "f_rp",
        "action_id": "a_rp",
        "tool": "sheet/write_rows",
        "status": "APPROVED",
        "approved_by": "operator",
        "approved_at": "2026-05-20T10:00:00Z",
        "worker_identity": "worker_1",
        "idempotency_key": "ikey_rp_test",
        "prepared_payload_hash": "hash_rp",
        "target_ref": "spreadsheet_1",
        "business_ref": "inv-rp",
        "rollback_plan": {"action": "delete_rows", "range": "Sheet1!A2:D5", "note": "Undo write"},
    }
    base.update(overrides)
    return base


class TestRollbackPlanRequired(unittest.TestCase):
    def test_missing_rollback_plan_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_live_side_effect_preflight(
                pending_action=_full_action(rollback_plan=None),
                profile_name="controlled_live_write",
                profile_data={"allow_live_side_effects": True},
                runtime_data_dir=tmp,
            )
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(ROLLBACK_PLAN_MISSING, codes)

    def test_empty_dict_rollback_plan_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_live_side_effect_preflight(
                pending_action=_full_action(rollback_plan={}),
                profile_name="controlled_live_write",
                profile_data={"allow_live_side_effects": True},
                runtime_data_dir=tmp,
            )
            self.assertFalse(result["ok"])
            codes = [c["error_code"] for c in result["failed_checks"]]
            self.assertIn(ROLLBACK_PLAN_MISSING, codes)

    def test_non_empty_rollback_plan_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_live_side_effect_preflight(
                pending_action=_full_action(),
                profile_name="controlled_live_write",
                profile_data={"allow_live_side_effects": True},
                runtime_data_dir=tmp,
            )
            rollback_check = next(
                (c for c in result["checks"] if c["name"] == "rollback_plan_present"), None
            )
            self.assertIsNotNone(rollback_check)
            self.assertTrue(rollback_check["ok"])

    def test_rollback_plan_must_be_dict_not_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_live_side_effect_preflight(
                pending_action=_full_action(rollback_plan="delete rows"),
                profile_name="controlled_live_write",
                profile_data={"allow_live_side_effects": True},
                runtime_data_dir=tmp,
            )
            self.assertFalse(result["ok"])


class TestRollbackPlanStoredInLedger(unittest.TestCase):
    def test_rollback_plan_stored_in_ledger_entry(self):
        rollback = {"action": "delete_rows", "range": "A2:D5"}
        entry = build_ledger_entry(
            frame_id="f1",
            action_id="a1",
            tool="sheet/write_rows",
            idempotency_key="ikey_rp_ledger",
            business_ref="inv-001",
            target_ref="sp1",
            prepared_payload_hash="hash1",
            approved_by="op",
            worker_identity="w1",
            status=LEDGER_STATUS_EXECUTED,
            rollback_plan=rollback,
        )
        self.assertEqual(entry["rollback_plan"], rollback)

    def test_rollback_plan_retrievable_from_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            rollback = {"action": "delete_rows", "note": "undo"}
            entry = build_ledger_entry(
                frame_id="f1",
                action_id="a1",
                tool="sheet/write_rows",
                idempotency_key="ikey_rp_retrieve",
                business_ref="inv-001",
                target_ref="sp1",
                prepared_payload_hash="hash1",
                approved_by="op",
                worker_identity="w1",
                status=LEDGER_STATUS_EXECUTED,
                rollback_plan=rollback,
            )
            append_ledger_entry(entry, runtime_data_dir=tmp)
            found = get_ledger_entry("ikey_rp_retrieve", runtime_data_dir=tmp)
            self.assertIsNotNone(found)
            self.assertEqual(found["rollback_plan"], rollback)


class TestRollbackPlanDisplayOnly(unittest.TestCase):
    def test_no_auto_rollback_in_execution_module(self):
        import inspect
        from runtime import live_side_effect_execution as lse_mod
        src = inspect.getsource(lse_mod)
        self.assertNotIn("auto_rollback", src)
        self.assertNotIn("perform_rollback", src)

    def test_rollback_plan_is_metadata_only(self):
        import inspect
        from runtime import live_side_effect_execution as lse_mod
        src = inspect.getsource(lse_mod)
        self.assertIn("rollback_plan", src)
        self.assertIn("display", src.lower() or "display")


if __name__ == "__main__":
    unittest.main()
