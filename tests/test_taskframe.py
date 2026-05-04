import json
import unittest

from runtime.manifest_loader import load_manifest
from runtime.taskframe import (
    TASKFRAME_STATES,
    TaskFrameStateError,
    build_taskframe_summary,
    create_taskframe,
    json_safe,
    record_error,
    set_output,
    to_dict,
    transition_state,
)


class TaskFrameTests(unittest.TestCase):
    def test_create_taskframe_initializes_runtime_state(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        self.assertTrue(frame.frame_id)
        self.assertEqual(frame.manifest_id, "smoke.gmail_check")
        self.assertEqual(frame.state, "CREATED")
        self.assertEqual(len(frame.steps), 1)
        self.assertEqual(frame.steps[0].step_id, "check_mail")
        self.assertEqual(frame.steps[0].attempts, 0)
        self.assertEqual(frame.steps[0].max_attempts, 1)
        self.assertIsNone(frame.steps[0].timeout_seconds)
        self.assertEqual(frame.steps[0].started_at, "")
        self.assertEqual(frame.steps[0].ended_at, "")
        self.assertEqual(frame.steps[0].duration_ms, 0.0)
        self.assertEqual(frame.current_step_id, "check_mail")
        self.assertEqual(frame.outputs, {})
        self.assertEqual(frame.pending_actions, [])
        self.assertEqual(frame.attempts, [])
        self.assertTrue(frame.audit)
        self.assertEqual(frame.audit[0].event_type, "TASKFRAME_CREATED")

    def test_transition_created_to_validating_succeeds(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        transition_state(frame, "VALIDATING")
        self.assertEqual(frame.state, "VALIDATING")
        self.assertEqual(frame.audit[-1].event_type, "STATE_CHANGED")

    def test_transition_created_to_running_fails(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        with self.assertRaises(TaskFrameStateError):
            transition_state(frame, "RUNNING")

    def test_transition_to_unknown_state_fails(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        with self.assertRaises(TaskFrameStateError):
            transition_state(frame, "NOT_A_STATE")

    def test_record_error_adds_error_and_audit_event(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        starting_errors = len(frame.errors)
        starting_audit = len(frame.audit)

        record_error(frame, "validation_failed", "Missing output.")

        self.assertEqual(len(frame.errors), starting_errors + 1)
        self.assertEqual(frame.errors[-1]["type"], "validation_failed")
        self.assertEqual(len(frame.audit), starting_audit + 1)
        self.assertEqual(frame.audit[-1].event_type, "ERROR_RECORDED")

    def test_set_output_writes_to_frame_outputs(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        set_output(frame, "unread_mail", ["msg-1"])

        self.assertEqual(frame.outputs["unread_mail"], ["msg-1"])

    def test_to_dict_is_json_serializable(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        json.dumps(to_dict(frame))

    def test_to_dict_includes_attempts(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        data = to_dict(frame)

        self.assertIn("attempts", data)
        self.assertEqual(data["attempts"], [])

    def test_to_dict_serializes_timing_fields(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        frame = create_taskframe(manifest)

        data = to_dict(frame)

        self.assertEqual(data["steps"][0]["timeout_seconds"], 1.0)
        self.assertEqual(data["steps"][0]["started_at"], "")
        self.assertEqual(data["steps"][0]["ended_at"], "")
        self.assertEqual(data["steps"][0]["duration_ms"], 0.0)

    def test_build_taskframe_summary_returns_json_serializable_dict(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        summary = build_taskframe_summary(frame)

        json.dumps(summary)

    def test_build_taskframe_summary_counts_completed_failed_and_skipped(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.steps[0].status = "COMPLETED"
        frame.steps.append(frame.steps[0].__class__(step_id="s2", command="", kind="tool", namespace=None, action="", output_alias=None, status="FAILED"))
        frame.steps.append(frame.steps[0].__class__(step_id="s3", command="", kind="tool", namespace=None, action="", output_alias=None, status="SKIPPED"))

        summary = build_taskframe_summary(frame)

        self.assertEqual(summary["completed_steps"], 1)
        self.assertEqual(summary["failed_steps"], 1)
        self.assertEqual(summary["skipped_steps"], 1)

    def test_build_taskframe_summary_includes_pending_action_count_and_output_keys(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.pending_actions.append({"action_id": "pa_1"})
        frame.outputs["unread_mail"] = ["msg"]

        summary = build_taskframe_summary(frame)

        self.assertEqual(summary["pending_action_count"], 1)
        self.assertEqual(summary["output_keys"], ["unread_mail"])

    def test_json_safe_handles_unknown_object(self):
        class Unknown:
            def __str__(self):
                return "unknown-object"

        self.assertEqual(json_safe(Unknown()), "unknown-object")

    def test_state_constants_include_expected_values(self):
        self.assertIn("CREATED", TASKFRAME_STATES)
        self.assertIn("READY", TASKFRAME_STATES)


if __name__ == "__main__":
    unittest.main()
