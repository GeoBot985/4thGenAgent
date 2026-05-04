import json
import tempfile
import unittest
from pathlib import Path

from runtime.completion_gate import apply_completion_result, evaluate_completion
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe


def write_manifest(tmpdir: Path, data: dict, filename: str = "manifest.manifest.json") -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def make_manifest(tmpdir: Path, completion: dict, validations: list | None = None) -> Path:
    return write_manifest(
        tmpdir,
        {
            "manifest_id": "completion.test",
            "name": "Completion Test",
            "version": 1,
            "trigger": {"type": "manual"},
            "inputs": [],
            "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
            "validations": validations or [],
            "completion": completion,
        },
    )


def make_pending_action(status: str = "PENDING_APPROVAL") -> dict:
    return {
        "action_id": "pa_1",
        "step_id": "stage_message",
        "tool": "wa/send",
        "namespace": "wa",
        "action": "send",
        "output_alias": "sent_msg",
        "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
        "status": status,
        "side_effect": True,
        "requires_approval": True,
        "created_at": "2026-05-01T00:00:00Z",
    }


class CompletionGateTests(unittest.TestCase):
    def test_completion_passes_when_required_output_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}, [{"id": "no_errors", "type": "no_errors"}])
            )
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = {"dry_run": True}
            frame.validations = [{"validation_id": "no_errors", "type": "no_errors", "ok": True, "message": "", "data": {}}]

            result = evaluate_completion(frame, manifest)

            self.assertTrue(result["ok"])
            self.assertEqual(result["final_state"], "COMPLETED")

    def test_completion_fails_when_required_output_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"

            result = evaluate_completion(frame, manifest)

            self.assertFalse(result["ok"])
            self.assertIn("unread_mail", result["missing_outputs"])

    def test_completion_returns_completed_for_non_empty_required_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = {"dry_run": True}

            result = evaluate_completion(frame, manifest)

            self.assertEqual(result["final_state"], "COMPLETED")

    def test_completion_returns_completed_no_data_for_acceptable_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(
                    Path(tmp),
                    {"success_outputs": ["unread_mail"], "acceptable_empty_outputs": ["unread_mail"]},
                )
            )
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = []

            result = evaluate_completion(frame, manifest)

            self.assertEqual(result["final_state"], "COMPLETED_NO_DATA")

    def test_completion_fails_for_empty_output_not_marked_acceptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = []

            result = evaluate_completion(frame, manifest)

            self.assertFalse(result["ok"])
            self.assertEqual(result["final_state"], "FAILED_COMPLETION")

    def test_completion_passes_when_required_pending_action_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(
                    Path(tmp),
                    {"success_pending_actions": ["sent_msg"], "allow_pending_approval": True},
                )
            )
            frame = create_taskframe(manifest)
            frame.state = "WAITING_FOR_EXECUTE"
            frame.pending_actions.append(
                {
                    "action_id": "pa_1",
                    "step_id": "stage_message",
                    "tool": "wa/send",
                    "namespace": "wa",
                    "action": "send",
                    "output_alias": "sent_msg",
                    "args": {"chat": "Cornelia"},
                    "status": "PENDING_APPROVAL",
                    "side_effect": True,
                    "requires_approval": True,
                    "created_at": "2026-05-01T00:00:00Z",
                }
            )

            result = evaluate_completion(frame, manifest)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "AWAITING_APPROVAL")
            self.assertEqual(result["final_state"], "WAITING_FOR_EXECUTE")

    def test_completion_returns_waiting_for_execute_for_pending_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(
                    Path(tmp),
                    {"success_pending_actions": ["sent_msg"], "allow_pending_approval": True},
                )
            )
            frame = create_taskframe(manifest)
            frame.state = "WAITING_FOR_EXECUTE"
            frame.pending_actions.append(
                {
                    "action_id": "pa_1",
                    "step_id": "stage_message",
                    "tool": "wa/send",
                    "namespace": "wa",
                    "action": "send",
                    "output_alias": "sent_msg",
                    "args": {"chat": "Cornelia"},
                    "status": "PENDING_APPROVAL",
                    "side_effect": True,
                    "requires_approval": True,
                    "created_at": "2026-05-01T00:00:00Z",
                }
            )

            result = evaluate_completion(frame, manifest)

            self.assertEqual(result["status"], "AWAITING_APPROVAL")

    def test_completion_fails_when_required_pending_action_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(Path(tmp), {"success_pending_actions": ["sent_msg"], "allow_pending_approval": True})
            )
            frame = create_taskframe(manifest)
            frame.state = "WAITING_FOR_EXECUTE"

            result = evaluate_completion(frame, manifest)

            self.assertFalse(result["ok"])
            self.assertIn("sent_msg", result["missing_pending_actions"])

    def test_completion_fails_when_a_step_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.steps[0].status = "FAILED"
            frame.outputs["unread_mail"] = {"dry_run": True}

            result = evaluate_completion(frame, manifest)

            self.assertFalse(result["ok"])

    def test_completion_fails_when_frame_has_runtime_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = {"dry_run": True}
            frame.errors.append({"type": "runtime", "message": "boom"})

            result = evaluate_completion(frame, manifest)

            self.assertFalse(result["ok"])

    def test_apply_completion_result_writes_completion_gate_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = {"dry_run": True}

            result = evaluate_completion(frame, manifest)
            apply_completion_result(frame, result)

            self.assertIsNotNone(frame.completion_gate_result)

    def test_apply_completion_result_transitions_to_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(make_manifest(Path(tmp), {"success_outputs": ["unread_mail"]}))
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = {"dry_run": True}

            result = evaluate_completion(frame, manifest)
            apply_completion_result(frame, result)

            self.assertEqual(frame.state, "COMPLETED")

    def test_apply_completion_result_transitions_to_completed_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(
                    Path(tmp),
                    {"success_outputs": ["unread_mail"], "acceptable_empty_outputs": ["unread_mail"]},
                )
            )
            frame = create_taskframe(manifest)
            frame.state = "VERIFYING"
            frame.outputs["unread_mail"] = []

            result = evaluate_completion(frame, manifest)
            apply_completion_result(frame, result)

            self.assertEqual(frame.state, "COMPLETED_NO_DATA")

    def test_apply_completion_result_leaves_staged_side_effect_frame_waiting_for_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                make_manifest(
                    Path(tmp),
                    {"success_pending_actions": ["sent_msg"], "allow_pending_approval": True},
                )
            )
            frame = create_taskframe(manifest)
            frame.state = "WAITING_FOR_EXECUTE"
            frame.pending_actions.append(
                {
                    "action_id": "pa_1",
                    "step_id": "stage_message",
                    "tool": "wa/send",
                    "namespace": "wa",
                    "action": "send",
                    "output_alias": "sent_msg",
                    "args": {"chat": "Cornelia"},
                    "status": "PENDING_APPROVAL",
                    "side_effect": True,
                    "requires_approval": True,
                    "created_at": "2026-05-01T00:00:00Z",
                }
            )

            result = evaluate_completion(frame, manifest)
            apply_completion_result(frame, result)

            self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")

    def test_completion_returns_waiting_for_execute_before_pending_action_approval(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "WAITING_FOR_EXECUTE"
        frame.pending_actions.append(make_pending_action("PENDING_APPROVAL"))

        result = evaluate_completion(frame, manifest)

        self.assertEqual(result["status"], "AWAITING_APPROVAL")
        self.assertEqual(result["final_state"], "WAITING_FOR_EXECUTE")

    def test_completion_returns_waiting_for_execute_after_approval_before_execution(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "WAITING_FOR_EXECUTE"
        frame.pending_actions.append(make_pending_action("APPROVED"))
        frame.pending_actions[0]["approved_by"] = "smoke"

        result = evaluate_completion(frame, manifest)

        self.assertEqual(result["status"], "APPROVED_WAITING_EXECUTION")
        self.assertEqual(result["final_state"], "WAITING_FOR_EXECUTE")

    def test_completion_returns_completed_after_approved_dry_run_execution(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "VERIFYING"
        frame.pending_actions.append(make_pending_action("EXECUTED"))
        frame.outputs["sent_msg"] = {
            "dry_run": True,
            "approved_execution": True,
            "tool": "wa/send",
            "function": "whatsapp_send",
            "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
        }
        frame.executed_actions.append(
            {
                "action_id": frame.pending_actions[0]["action_id"],
                "step_id": frame.pending_actions[0]["step_id"],
                "tool": "wa/send",
                "namespace": "wa",
                "action": "send",
                "output_alias": "sent_msg",
                "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
                "status": "EXECUTED",
                "dry_run": True,
                "result_type": "whatsapp_send_result",
                "executed_at": "2026-05-01T00:00:00Z",
            }
        )

        result = evaluate_completion(frame, manifest)

        self.assertTrue(result["ok"])
        self.assertEqual(result["final_state"], "COMPLETED")

    def test_completion_fails_if_success_executed_actions_missing(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "VERIFYING"
        frame.outputs["sent_msg"] = {"dry_run": True}

        result = evaluate_completion(frame, manifest)

        self.assertFalse(result["ok"])
        self.assertIn("sent_msg", result["missing_executed_actions"])

    def test_completion_fails_if_executed_action_exists_but_output_missing(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "VERIFYING"
        frame.pending_actions.append(make_pending_action("EXECUTED"))
        frame.executed_actions.append(
            {
                "action_id": frame.pending_actions[0]["action_id"],
                "step_id": frame.pending_actions[0]["step_id"],
                "tool": "wa/send",
                "namespace": "wa",
                "action": "send",
                "output_alias": "sent_msg",
                "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
                "status": "EXECUTED",
                "dry_run": True,
                "result_type": "whatsapp_send_result",
                "executed_at": "2026-05-01T00:00:00Z",
            }
        )

        result = evaluate_completion(frame, manifest)

        self.assertFalse(result["ok"])
        self.assertIn("sent_msg", result["missing_outputs"])

    def test_completion_passes_if_executed_action_and_output_exist(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "VERIFYING"
        frame.pending_actions.append(make_pending_action("EXECUTED"))
        frame.outputs["sent_msg"] = {
            "dry_run": True,
            "approved_execution": True,
            "tool": "wa/send",
            "function": "whatsapp_send",
            "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
        }
        frame.executed_actions.append(
            {
                "action_id": frame.pending_actions[0]["action_id"],
                "step_id": frame.pending_actions[0]["step_id"],
                "tool": "wa/send",
                "namespace": "wa",
                "action": "send",
                "output_alias": "sent_msg",
                "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
                "status": "EXECUTED",
                "dry_run": True,
                "result_type": "whatsapp_send_result",
                "executed_at": "2026-05-01T00:00:00Z",
            }
        )

        result = evaluate_completion(frame, manifest)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
