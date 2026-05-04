from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.operator_approval_actions import (
    approve_pending_action,
    execute_approved_pending_actions_dry_run,
    reject_pending_action,
    reload_operator_run,
)
from src.operator_demo_runner import run_demo_manifest
from runtime.runtime_engine import RuntimeEngine


class OperatorApprovalControlsTests(unittest.TestCase):
    def _run_staged_demo(self, runtime_root: Path) -> dict:
        return run_demo_manifest("customer_status_llm_e2e", runtime_data_dir=str(runtime_root))

    def test_operator_approve_pending_action_updates_target_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            result = self._run_staged_demo(runtime_root)
            frame_id = result["frame_id"]
            action_id = result["approval_pack"]["approval_packs"][0]["action_id"]

            op = approve_pending_action(frame_id, action_id, runtime_data_dir=str(runtime_root))
            reloaded = reload_operator_run(frame_id, runtime_data_dir=str(runtime_root))

            self.assertTrue(op["ok"])
            self.assertEqual(op["target_frame_id"], frame_id)
            self.assertNotEqual(op["command_frame_id"], "")
            self.assertNotEqual(op["command_frame_id"], frame_id)
            pack = reloaded["approval_pack"]
            self.assertEqual(pack["approval_packs"][0]["status"], "APPROVED")
            self.assertEqual(reloaded["target_frame_state"], "WAITING_FOR_EXECUTE")

    def test_operator_reject_pending_action_updates_target_frame_failed_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            result = self._run_staged_demo(runtime_root)
            frame_id = result["frame_id"]
            action_id = result["approval_pack"]["approval_packs"][0]["action_id"]

            op = reject_pending_action(frame_id, action_id, runtime_data_dir=str(runtime_root))
            reloaded = reload_operator_run(frame_id, runtime_data_dir=str(runtime_root))

            self.assertTrue(op["ok"])
            self.assertEqual(reloaded["approval_pack"]["approval_packs"][0]["status"], "REJECTED")
            self.assertEqual(reloaded["target_frame_state"], "FAILED_COMPLETION")

    def test_operator_execute_approved_pending_actions_dry_run_completes_target_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            result = self._run_staged_demo(runtime_root)
            frame_id = result["frame_id"]
            action_id = result["approval_pack"]["approval_packs"][0]["action_id"]

            approve_pending_action(frame_id, action_id, runtime_data_dir=str(runtime_root))
            op = execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=str(runtime_root))
            reloaded = reload_operator_run(frame_id, runtime_data_dir=str(runtime_root))

            self.assertTrue(op["ok"])
            self.assertEqual(reloaded["approval_pack"]["approval_packs"][0]["status"], "EXECUTED")
            self.assertGreaterEqual(int(reloaded["summary"].get("executed_action_count", 0)), 1)
            self.assertIn(reloaded["target_frame_state"], {"COMPLETED", "COMPLETED_NO_DATA"})

    def test_operator_execute_without_approval_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            result = self._run_staged_demo(runtime_root)
            frame_id = result["frame_id"]

            op = execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=str(runtime_root))
            reloaded = reload_operator_run(frame_id, runtime_data_dir=str(runtime_root))

            self.assertFalse(op["ok"])
            self.assertNotEqual(op["error"], "")
            self.assertEqual(reloaded["target_frame_state"], "WAITING_FOR_EXECUTE")
            self.assertEqual(reloaded["approval_pack"]["approval_packs"][0]["status"], "PENDING_APPROVAL")

    def test_operator_execute_after_reject_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            result = self._run_staged_demo(runtime_root)
            frame_id = result["frame_id"]
            action_id = result["approval_pack"]["approval_packs"][0]["action_id"]

            reject_pending_action(frame_id, action_id, runtime_data_dir=str(runtime_root))
            op = execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=str(runtime_root))
            reloaded = reload_operator_run(frame_id, runtime_data_dir=str(runtime_root))

            self.assertFalse(op["ok"])
            self.assertEqual(reloaded["target_frame_state"], "FAILED_COMPLETION")
            self.assertEqual(reloaded["approval_pack"]["approval_packs"][0]["status"], "REJECTED")

    def test_operator_approval_actions_always_use_dry_run_true(self):
        seen: list[bool] = []
        original = RuntimeEngine.handle_event

        def wrapped(self, event, dry_run=True):
            seen.append(dry_run)
            return original(self, event, dry_run=dry_run)

        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            result = self._run_staged_demo(runtime_root)
            frame_id = result["frame_id"]
            action_id = result["approval_pack"]["approval_packs"][0]["action_id"]
            with patch.object(RuntimeEngine, "handle_event", wrapped):
                approve_pending_action(frame_id, action_id, runtime_data_dir=str(runtime_root))
                execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=str(runtime_root))
            self.assertTrue(seen and all(item is True for item in seen))

    def test_operator_approval_actions_do_not_directly_mutate_pending_actions(self):
        source = Path("src/operator_approval_actions.py").read_text(encoding="utf-8")
        for text in ('pending_actions[0]["status"] =', '["status"] = "APPROVED"', '["status"] = "REJECTED"', '["status"] = "EXECUTED"'):
            self.assertNotIn(text, source)


if __name__ == "__main__":
    unittest.main()
