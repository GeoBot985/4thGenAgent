import unittest

from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe
from runtime.tool_runner import ToolRunner


class ToolRunnerTests(unittest.TestCase):
    def test_read_only_tool_dry_run_writes_output_and_completes_step(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "RUNNING"
        runner = ToolRunner(dry_run=True)
        step = frame.steps[0]

        result = runner.run_step(frame, step)

        self.assertTrue(result.ok)
        self.assertEqual(result.type, "gmail_check_result")
        self.assertIn("unread_mail", frame.outputs)
        self.assertTrue(frame.outputs["unread_mail"]["dry_run"])
        self.assertEqual(step.status, "COMPLETED")
        self.assertEqual(len(frame.tool_calls), 1)
        self.assertTrue(frame.audit)

    def test_side_effect_tool_stages_pending_action(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "RUNNING"
        runner = ToolRunner(dry_run=True)
        step = frame.steps[0]

        result = runner.run_step(frame, step)

        self.assertTrue(result.ok)
        self.assertEqual(result.type, "pending_action")
        self.assertEqual(step.status, "STAGED")
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertEqual(frame.pending_actions[0]["status"], "PENDING_APPROVAL")
        self.assertNotIn("sent_msg", frame.outputs)

    def test_pending_command_always_stages_action(self):
        manifest = load_manifest("manifests/smoke_gobook_stage_booking.manifest.json")
        frame = create_taskframe(
            manifest,
            inputs={"date": "2026-05-01", "time_value": "18:00", "court": "Court 1"},
        )
        frame.state = "RUNNING"
        runner = ToolRunner(dry_run=True)
        step = frame.steps[0]

        result = runner.run_step(frame, step)

        self.assertTrue(result.ok)
        self.assertEqual(result.type, "pending_action")
        self.assertEqual(step.status, "STAGED")
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertEqual(frame.pending_actions[0]["tool"], "gb/book")

    def test_gobook_book_forces_confirm_false(self):
        manifest = load_manifest("manifests/smoke_gobook_stage_booking.manifest.json")
        frame = create_taskframe(
            manifest,
            inputs={"date": "2026-05-01", "time_value": "18:00", "court": "Court 1"},
        )
        frame.state = "RUNNING"
        frame.steps[0].command = '[pending:gb/book -> booking] date=$inputs.date; time_value=$inputs.time_value; court=$inputs.court; confirm=true; slowmo=100'
        runner = ToolRunner(dry_run=True)

        runner.run_step(frame, frame.steps[0])

        self.assertFalse(frame.pending_actions[0]["args"]["confirm"])

    def test_unknown_tool_fails_step(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "RUNNING"
        frame.steps[0].command = '[t:x/do -> out] value=1'
        frame.steps[0].namespace = "x"
        frame.steps[0].action = "do"
        runner = ToolRunner(dry_run=True)

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_missing_required_arg_fails_step(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "RUNNING"
        frame.steps[0].command = '[t:g/send -> sent] to="a@example.com"; subject="Hello"'
        frame.steps[0].namespace = "g"
        frame.steps[0].action = "send"
        frame.steps[0].output_alias = "sent"
        runner = ToolRunner(dry_run=True)

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_unresolved_arg_ref_fails_step(self):
        manifest = load_manifest("manifests/smoke_gobook_stage_booking.manifest.json")
        frame = create_taskframe(manifest, inputs={"date": "2026-05-01", "start": "17:00"})
        frame.state = "RUNNING"
        runner = ToolRunner(dry_run=True)
        step = frame.steps[0]

        result = runner.run_step(frame, step)

        self.assertFalse(result.ok)
        self.assertEqual(step.status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")


if __name__ == "__main__":
    unittest.main()

