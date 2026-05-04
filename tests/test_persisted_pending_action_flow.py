import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.inspection import RunInspector
from runtime.persistence import load_taskframe_dict, taskframe_exists
from runtime.run_ledger import find_ledger_record, read_ledger_records
from runtime.runtime_engine import RuntimeEngine


class PersistedPendingActionFlowTests(unittest.TestCase):
    def test_full_persisted_pending_action_approval_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            inspector = RunInspector(runtime_dir)

            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            self.assertEqual(target.state, "WAITING_FOR_EXECUTE")
            self.assertTrue(taskframe_exists(target.frame_id, runtime_dir))
            pending_action_id = target.pending_actions[0]["action_id"]

            pending = inspector.get_pending_actions(target.frame_id)
            self.assertTrue(pending.ok)
            self.assertEqual(pending.data["count"], 1)

            approval_frame = engine.handle_event(
                create_event(
                    "manual.approve_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": pending_action_id,
                        "approved_by": "manual_smoke",
                        "reason": "Dry-run approval test",
                    },
                ),
                dry_run=True,
            )
            self.assertNotEqual(approval_frame.frame_id, target.frame_id)
            self.assertTrue(taskframe_exists(approval_frame.frame_id, runtime_dir))
            self.assertEqual(approval_frame.outputs["approval_result"]["status"], "APPROVED")

            approved_target = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(approved_target["pending_actions"][0]["status"], "APPROVED")
            self.assertEqual(find_ledger_record(target.frame_id, runtime_dir)["state"], "WAITING_FOR_EXECUTE")

            execution_frame = engine.handle_event(
                create_event(
                    "manual.execute_approved_pending_actions",
                    "manual",
                    payload={"frame_id": target.frame_id},
                ),
                dry_run=True,
            )
            self.assertNotEqual(execution_frame.frame_id, target.frame_id)
            self.assertEqual(execution_frame.outputs["execution_result"]["target_frame_state"], "COMPLETED")

            executed_target = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(executed_target["state"], "COMPLETED")
            self.assertEqual(executed_target["pending_actions"][0]["status"], "EXECUTED")

            records = [record for record in read_ledger_records(runtime_dir) if record["frame_id"] == target.frame_id]
            self.assertGreaterEqual(len(records), 3)
            self.assertEqual(find_ledger_record(target.frame_id, runtime_dir)["state"], "COMPLETED")

            approval_records = [record for record in read_ledger_records(runtime_dir) if record["frame_id"] == approval_frame.frame_id]
            self.assertTrue(approval_records)

    def test_rejected_persisted_pending_action_cannot_be_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]

            reject_frame = engine.handle_event(
                create_event(
                    "manual.reject_pending_action",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "rejected_by": "manual_smoke",
                        "reason": "Wrong recipient",
                    },
                ),
                dry_run=True,
            )
            self.assertEqual(reject_frame.state, "COMPLETED")

            rejected_target = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(rejected_target["state"], "FAILED_COMPLETION")
            self.assertEqual(rejected_target["pending_actions"][0]["status"], "REJECTED")

            execute_after_reject = engine.handle_event(
                create_event(
                    "manual.execute_approved_pending_actions",
                    "manual",
                    payload={"frame_id": target.frame_id},
                ),
                dry_run=True,
            )
            self.assertEqual(execute_after_reject.state, "FAILED_EXECUTION")
            self.assertEqual(load_taskframe_dict(target.frame_id, runtime_dir)["state"], "FAILED_COMPLETION")

    def test_approve_and_execute_combined_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            target = engine.handle_event(create_event("manual.whatsapp_stage_send", "manual"), dry_run=True)
            action_id = target.pending_actions[0]["action_id"]

            flow = engine.handle_event(
                create_event(
                    "manual.reload_pending_action_flow",
                    "manual",
                    payload={
                        "frame_id": target.frame_id,
                        "action_id": action_id,
                        "approved_by": "manual_smoke",
                        "reason": "One-step dry-run approval flow",
                    },
                ),
                dry_run=True,
            )

            self.assertEqual(flow.state, "COMPLETED")
            self.assertEqual(flow.outputs["approval_execution_result"]["target_frame_state"], "COMPLETED")
            self.assertEqual(load_taskframe_dict(target.frame_id, runtime_dir)["state"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
