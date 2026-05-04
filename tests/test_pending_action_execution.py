import unittest

from runtime.approval import approve_action
from runtime.errors import PendingActionError, ToolExecutionBlocked
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.tool_runner import ToolRunner


class PendingActionExecutionTests(unittest.TestCase):
    def make_action(self, tool: str = "wa/send", output_alias: str = "sent_msg", status: str = "PENDING_APPROVAL"):
        return {
            "action_id": "pa_1",
            "step_id": "stage_message",
            "tool": tool,
            "namespace": tool.split("/")[0],
            "action": tool.split("/")[1],
            "output_alias": output_alias,
            "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
            "status": status,
            "side_effect": True,
            "requires_approval": True,
            "created_at": "2026-05-01T00:00:00Z",
        }

    def test_execute_pending_action_requires_approved_status(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertFalse(result.ok)
        self.assertEqual(action["status"], "FAILED")

    def test_execute_pending_action_transitions_action_executing_then_executed(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertTrue(result.ok)
        self.assertEqual(action["status"], "EXECUTED")
        self.assertEqual(frame.executed_actions[0]["status"], "EXECUTED")
        self.assertEqual(frame.tool_calls[0]["action_id"], action["action_id"])
        self.assertEqual(frame.audit[-2].event_type, "PENDING_ACTION_EXECUTING")
        self.assertEqual(frame.audit[-1].event_type, "PENDING_ACTION_EXECUTED")

    def test_execute_pending_action_writes_output_alias_to_frame_outputs(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertTrue(result.ok)
        self.assertIn("sent_msg", frame.outputs)
        self.assertTrue(frame.outputs["sent_msg"]["approved_execution"])
        self.assertTrue(frame.outputs["sent_msg"]["dry_run"])

    def test_execute_pending_action_appends_executed_actions(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        runner.execute_pending_action(frame, action)

        self.assertEqual(len(frame.executed_actions), 1)
        self.assertEqual(frame.executed_actions[0]["tool"], "wa/send")

    def test_execute_pending_action_appends_tool_calls(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        runner.execute_pending_action(frame, action)

        self.assertGreaterEqual(len(frame.tool_calls), 1)

    def test_execute_pending_action_returns_ok_result(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertTrue(result.ok)
        self.assertEqual(result.type, "whatsapp_send_result")

    def test_execute_pending_action_includes_dry_run_true(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertTrue(result.data["dry_run"])
        self.assertTrue(result.data["approved_execution"])

    def test_execute_pending_action_blocks_dry_run_false(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action()
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=False)

        with self.assertRaises(ToolExecutionBlocked):
            runner.execute_pending_action(frame, action)

    def test_execute_pending_action_forces_gb_book_confirm_false(self):
        manifest = load_manifest("manifests/smoke_gobook_stage_booking.manifest.json")
        frame = create_taskframe(
            manifest,
            inputs={"date": "2026-05-01", "time_value": "18:00", "court": "Court 1"},
        )
        action = {
            "action_id": "pa_1",
            "step_id": "stage_booking",
            "tool": "gb/book",
            "namespace": "gb",
            "action": "book",
            "output_alias": "booking",
            "args": {"date": "2026-05-01", "time_value": "18:00", "court": "Court 1", "confirm": True, "slowmo": 100},
            "status": "APPROVED",
            "side_effect": True,
            "requires_approval": True,
            "created_at": "2026-05-01T00:00:00Z",
        }
        frame.pending_actions.append(action)
        runner = ToolRunner(dry_run=True)

        runner.execute_pending_action(frame, action)

        self.assertFalse(action["args"]["confirm"])

    def test_execute_pending_action_forces_gb_cancel_confirm_false(self):
        manifest = load_manifest("manifests/smoke_gobook_stage_booking.manifest.json")
        frame = create_taskframe(
            manifest,
            inputs={"date": "2026-05-01", "time_value": "18:00", "court": "Court 1"},
        )
        action = {
            "action_id": "pa_1",
            "step_id": "stage_booking",
            "tool": "gb/cancel",
            "namespace": "gb",
            "action": "cancel",
            "output_alias": "booking",
            "args": {"date": "2026-05-01", "time_value": "18:00", "court": "Court 1", "confirm": True, "slowmo": 100},
            "status": "APPROVED",
            "side_effect": True,
            "requires_approval": True,
            "created_at": "2026-05-01T00:00:00Z",
        }
        frame.pending_actions.append(action)
        runner = ToolRunner(dry_run=True)

        runner.execute_pending_action(frame, action)

        self.assertFalse(action["args"]["confirm"])

    def test_execute_pending_action_fails_unknown_tool(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action(tool="x/do", output_alias="out", status="APPROVED")
        action["namespace"] = "x"
        action["action"] = "do"
        action["args"] = {}
        frame.pending_actions.append(action)
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertFalse(result.ok)
        self.assertEqual(action["status"], "FAILED")

    def test_execute_pending_action_fails_missing_output_alias(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        action = self.make_action(output_alias=None)
        frame.pending_actions.append(action)
        approve_action(frame, action["action_id"], approved_by="smoke")
        runner = ToolRunner(dry_run=True)

        result = runner.execute_pending_action(frame, action)

        self.assertFalse(result.ok)
        self.assertEqual(action["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
