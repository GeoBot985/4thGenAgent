import json
import tempfile
import unittest
from pathlib import Path

from runtime.errors import ToolExecutionBlocked
from runtime.manifest_loader import load_manifest
from runtime.orchestrator import Orchestrator


def write_manifest(tmpdir: Path, data: dict, filename: str = "manifest.manifest.json") -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def make_two_step_manifest(tmpdir: Path) -> Path:
    return write_manifest(
        tmpdir,
        {
            "manifest_id": "test.two_step",
            "name": "Two Step Test",
            "version": 1,
            "trigger": {"type": "manual"},
            "inputs": [],
            "steps": [
                {"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"},
                {
                    "id": "stage_message",
                    "command": "[t:wa/send -> sent_msg] chat=\"Cornelia\"; message=\"Runtime smoke test\"",
                },
            ],
            "validations": [],
            "completion": {"success_outputs": ["unread_mail"]},
        },
    )


def make_validation_manifest(tmpdir: Path, completion: dict, validations: list | None = None) -> Path:
    return write_manifest(
        tmpdir,
        {
            "manifest_id": "test.validation",
            "name": "Validation Manifest",
            "version": 1,
            "trigger": {"type": "manual"},
            "inputs": [],
            "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
            "validations": validations or [],
            "completion": completion,
        },
    )


class OrchestratorTests(unittest.TestCase):
    def test_create_frame_from_manifest(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()

        frame = orch.create_frame_from_manifest(manifest)

        self.assertEqual(frame.manifest_id, "smoke.gmail_check")
        self.assertEqual(frame.audit[-1].event_type, "ORCHESTRATOR_FRAME_CREATED")

    def test_prepare_frame_moves_created_to_ready(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()

        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        self.assertEqual(frame.state, "READY")
        event_types = [event.event_type for event in frame.audit]
        self.assertEqual(
            event_types,
            [
                "TASKFRAME_CREATED",
                "ORCHESTRATOR_FRAME_CREATED",
                "STATE_CHANGED",
                "STATE_CHANGED",
                "FRAME_READY",
            ],
        )

    def test_prepare_frame_rejects_non_created_frame_if_called_twice(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()

        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        with self.assertRaises(ValueError):
            orch.prepare_frame(frame)

    def test_orchestrator_does_not_execute_tools_or_create_outputs(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()

        frame = orch.create_frame_from_manifest(manifest)

        self.assertEqual(frame.outputs, {})
        self.assertEqual(frame.tool_calls, [])
        self.assertEqual(frame.pending_actions, [])
        self.assertEqual(frame.executed_actions, [])

    def test_run_next_step_moves_ready_to_running_and_executes_read_only_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_two_step_manifest(Path(tmp)))
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "RUNNING")
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("unread_mail", frame.outputs)
            self.assertEqual(frame.current_step_id, "stage_message")

    def test_run_next_step_stages_side_effect_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_two_step_manifest(Path(tmp)))
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)
            frame = orch.run_next_step(frame, manifest, dry_run=True)
            frame = orch.run_next_step(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
            self.assertEqual(frame.steps[1].status, "STAGED")
            self.assertEqual(len(frame.pending_actions), 1)
            self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")
            self.assertEqual(frame.pending_actions[0]["status"], "PENDING_APPROVAL")
            self.assertNotIn("sent_msg", frame.outputs)

    def test_run_next_step_with_no_pending_steps_moves_running_to_verifying(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "VERIFYING")

    def test_run_next_step_does_not_call_real_external_tools(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertTrue(frame.outputs["unread_mail"]["dry_run"])
        self.assertEqual(frame.outputs["unread_mail"]["tool"], "g/check")

    def test_run_next_step_executes_validate_command(self):
        manifest = load_manifest("manifests/smoke_validate_step_output_exists.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[0].status, "COMPLETED")
        self.assertEqual(frame.steps[1].status, "PENDING")
        frame = orch.run_next_step(frame, manifest, dry_run=True)
        self.assertEqual(frame.steps[1].status, "COMPLETED")

    def test_run_next_step_fails_missing_validation_rule(self):
        manifest = load_manifest("tests/fixtures/smoke_manifests/smoke_validate_step_fail_fast.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[0].status, "FAILED")

    def test_verify_frame_completes_read_only_successful_frame(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_next_step(frame, manifest, dry_run=True)
        frame = orch.verify_frame(frame, manifest)

        self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})
        self.assertTrue(frame.completion_gate_result["ok"])

    def test_verify_frame_fails_frame_with_missing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_validation_manifest(
                    Path(tmp),
                    {"success_outputs": ["unread_mail"]},
                    [{"id": "no_errors", "type": "no_errors"}],
                )
            )
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame.state = "VERIFYING"
            frame.validations.append({"validation_id": "no_errors", "type": "no_errors", "ok": True, "message": "", "data": {}})

            frame = orch.verify_frame(frame, manifest)

            self.assertEqual(frame.state, "FAILED_COMPLETION")
            self.assertFalse(frame.completion_gate_result["ok"])

    def test_verify_frame_validates_staged_pending_action(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_next_step(frame, manifest, dry_run=True)

        frame = orch.verify_frame(frame, manifest)

        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertTrue(frame.completion_gate_result["ok"])
        self.assertEqual(frame.completion_gate_result["status"], "AWAITING_APPROVAL")

    def test_run_until_blocked_completes_smoke_gmail_check_in_dry_run(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})
        self.assertTrue(frame.completion_gate_result["ok"])
        self.assertIn("unread_mail", frame.outputs)

    def test_run_until_blocked_stages_smoke_whatsapp_stage_send_and_verifies_waiting_approval(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        self.assertTrue(frame.completion_gate_result["ok"])
        self.assertEqual(frame.completion_gate_result["status"], "AWAITING_APPROVAL")
        self.assertEqual(len(frame.pending_actions), 1)
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")

    def test_run_until_blocked_does_not_execute_real_tools(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertTrue(frame.outputs["unread_mail"]["dry_run"])
        self.assertEqual(frame.outputs["unread_mail"]["tool"], "g/check")

    def test_run_until_blocked_stops_on_failed_validation(self):
        manifest = load_manifest("tests/fixtures/smoke_manifests/smoke_validate_step_fail_fast.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[1].status, "PENDING")

    def test_orchestrator_approves_pending_action(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]

        frame = orch.approve_pending_action(frame, action_id, approved_by="smoke_test", reason="Approved")

        self.assertEqual(frame.pending_actions[0]["status"], "APPROVED")
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")

    def test_orchestrator_rejects_pending_action(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]

        frame = orch.reject_pending_action(frame, action_id, rejected_by="smoke_test", reason="Rejected")

        self.assertEqual(frame.pending_actions[0]["status"], "REJECTED")
        self.assertEqual(frame.state, "FAILED_COMPLETION")

    def test_execute_approved_pending_actions_requires_waiting_for_execute(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)

        with self.assertRaises(ValueError):
            orch.execute_approved_pending_actions(frame, manifest, dry_run=True)

    def test_execute_approved_pending_actions_moves_through_execution_and_verify(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]
        orch.approve_pending_action(frame, action_id, approved_by="smoke_test", reason="Approved")

        frame = orch.execute_approved_pending_actions(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.pending_actions[0]["status"], "EXECUTED")
        self.assertEqual(frame.executed_actions[0]["tool"], "wa/send")
        self.assertIn("sent_msg", frame.outputs)
        self.assertTrue(frame.outputs["sent_msg"]["dry_run"])

    def test_execute_approved_pending_actions_blocks_dry_run_false(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]
        orch.approve_pending_action(frame, action_id, approved_by="smoke_test", reason="Approved")

        with self.assertRaises(ToolExecutionBlocked):
            orch.execute_approved_pending_actions(frame, manifest, dry_run=False)

    def test_full_whatsapp_dry_run_approval_flow_completes(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]
        orch.approve_pending_action(frame, action_id, approved_by="smoke_test", reason="Approved")
        frame = orch.execute_approved_pending_actions(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertTrue(frame.completion_gate_result["ok"])
        self.assertEqual(frame.pending_actions[0]["status"], "EXECUTED")
        self.assertEqual(frame.executed_actions[0]["tool"], "wa/send")
        self.assertIn("sent_msg", frame.outputs)


    def test_full_gobook_dry_run_approval_flow_completes(self):
        manifest = load_manifest("manifests/smoke_gobook_stage_booking.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(
            manifest,
            inputs={"date": "2026-05-01", "time_value": "18:00", "court": "Court 1"},
        )
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]
        orch.approve_pending_action(frame, action_id, approved_by="smoke_test", reason="Approved")
        frame = orch.execute_approved_pending_actions(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.pending_actions[0]["status"], "EXECUTED")
        self.assertEqual(frame.executed_actions[0]["tool"], "gb/book")
        self.assertFalse(frame.executed_actions[0]["args"]["confirm"])
        self.assertIn("booking", frame.outputs)
        self.assertTrue(frame.outputs["booking"]["dry_run"])


if __name__ == "__main__":
    unittest.main()
