import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.persistence import load_taskframe_dict, taskframe_exists
from runtime.runtime_engine import RuntimeEngine


class RuntimeInspectionIntegrationTests(unittest.TestCase):
    def test_runtime_engine_can_inspect_recent_runs_via_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            created = engine.handle_event(create_event("manual.gmail_check", "manual"), dry_run=True)
            created_snapshot = load_taskframe_dict(created.frame_id, runtime_dir)

            inspected = engine.handle_event(create_event("manual.inspect_recent_runs", "manual"), dry_run=True)

            self.assertNotEqual(created.frame_id, inspected.frame_id)
            self.assertIn("runs", inspected.outputs)
            self.assertTrue(any(item["frame_id"] == created.frame_id for item in inspected.outputs["runs"]["runs"]))
            self.assertTrue(taskframe_exists(inspected.frame_id, runtime_dir))
            self.assertEqual(load_taskframe_dict(created.frame_id, runtime_dir), created_snapshot)

    def test_runtime_engine_can_inspect_summary_outputs_and_pending_actions_via_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            created = engine.handle_event(
                create_event("manual.whatsapp_stage_send", "manual"),
                dry_run=True,
            )
            self.assertEqual(created.state, "WAITING_FOR_EXECUTE")

            summary = engine.handle_event(
                create_event("manual.inspect_run_summary", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )
            self.assertEqual(summary.outputs["run_summary"]["frame_id"], created.frame_id)
            self.assertEqual(summary.outputs["run_summary"]["state"], created.state)

            outputs = engine.handle_event(
                create_event("manual.inspect_run_outputs", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )
            self.assertEqual(outputs.outputs["run_outputs"]["frame_id"], created.frame_id)

            pending = engine.handle_event(
                create_event("manual.inspect_run_pending_actions", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )
            self.assertEqual(pending.outputs["run_pending_actions"]["count"], 1)
            self.assertEqual(pending.outputs["run_pending_actions"]["pending_actions"][0]["tool"], "wa/send")

    def test_runtime_engine_inspection_event_creates_own_persisted_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            created = engine.handle_event(create_event("manual.gmail_check", "manual"), dry_run=True)
            inspected = engine.handle_event(
                create_event("manual.inspect_run_summary", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )

            self.assertTrue(taskframe_exists(created.frame_id, runtime_dir))
            self.assertTrue(taskframe_exists(inspected.frame_id, runtime_dir))
            self.assertNotEqual(created.frame_id, inspected.frame_id)
            self.assertEqual(load_taskframe_dict(created.frame_id, runtime_dir)["frame_id"], created.frame_id)

    def test_runtime_engine_inspection_works_with_existing_artifacts_when_persist_runs_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            writer = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)
            created = writer.handle_event(create_event("manual.gmail_check", "manual"), dry_run=True)

            reader = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False)
            inspected = reader.handle_event(
                create_event("manual.inspect_run_summary", "manual", payload={"frame_id": created.frame_id}),
                dry_run=True,
            )

            self.assertEqual(inspected.outputs["run_summary"]["frame_id"], created.frame_id)
            self.assertFalse(taskframe_exists(inspected.frame_id, runtime_dir))
            self.assertTrue(taskframe_exists(created.frame_id, runtime_dir))

    def test_runtime_engine_unknown_frame_id_inspection_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            inspected = engine.handle_event(
                create_event("manual.inspect_run_summary", "manual", payload={"frame_id": "missing"}),
                dry_run=True,
            )

            self.assertEqual(inspected.state, "FAILED_EXECUTION")
            self.assertEqual(inspected.steps[0].status, "FAILED")
            self.assertIn("TaskFrame artifact not found", inspected.errors[-1]["message"])


if __name__ == "__main__":
    unittest.main()
