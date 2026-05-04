import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from runtime.errors import UnknownValidationTypeError
from runtime.manifest_loader import load_manifest
from runtime.models import TaskFrame
from runtime.taskframe import create_taskframe
from runtime.validation import run_manifest_validations, run_validation


def write_manifest(tmpdir: Path, data: dict, filename: str = "manifest.manifest.json") -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def make_frame() -> TaskFrame:
    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.trigger = {"date": "2026-05-01", "kind": "manual"}
    frame.inputs = {"date": "2026-05-02", "start": "17:00"}
    frame.outputs = {
        "events": [
            {"id": "evt1", "title": "Squash"},
            {"id": "evt2", "title": "Dinner"},
        ],
        "chat": {"name": "Cornelia"},
        "empty_list": [],
        "empty_dict": {},
        "empty_text": "",
    }
    frame.pending_actions = [
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
    ]
    frame.steps[0].status = "COMPLETED"
    return frame


class ValidationEngineTests(unittest.TestCase):
    def test_output_exists_passes_when_output_exists(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "output_exists", "output": "chat"})
        self.assertTrue(result.ok)

    def test_output_exists_fails_when_output_missing(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "output_exists", "output": "missing"})
        self.assertFalse(result.ok)

    def test_output_not_empty_passes_for_non_empty_list(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "output_not_empty", "output": "events"})
        self.assertTrue(result.ok)

    def test_output_not_empty_fails_for_empty_list(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "output_not_empty", "output": "empty_list"})
        self.assertFalse(result.ok)

    def test_pending_action_exists_passes_by_tool(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "pending_action_exists", "tool": "wa/send"})
        self.assertTrue(result.ok)

    def test_pending_action_exists_passes_by_output_alias(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "pending_action_exists", "output": "sent_msg"},
        )
        self.assertTrue(result.ok)

    def test_pending_action_exists_fails_when_missing(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "pending_action_exists", "tool": "gb/book"})
        self.assertFalse(result.ok)

    def test_step_completed_passes(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "step_completed", "step": "check_mail"})
        self.assertTrue(result.ok)

    def test_step_completed_fails_for_staged_step(self):
        frame = make_frame()
        frame.steps[0].status = "STAGED"
        result = run_validation(frame, {"id": "v1", "type": "step_completed", "step": "check_mail"})
        self.assertFalse(result.ok)

    def test_step_staged_passes(self):
        frame = make_frame()
        frame.steps[0].status = "STAGED"
        result = run_validation(frame, {"id": "v1", "type": "step_staged", "step": "check_mail"})
        self.assertTrue(result.ok)

    def test_step_staged_fails_for_completed_step(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "step_staged", "step": "check_mail"})
        self.assertFalse(result.ok)

    def test_step_status_passes_for_completed(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "step_status", "step": "check_mail", "status": "COMPLETED"},
        )
        self.assertTrue(result.ok)

    def test_step_status_passes_for_skipped(self):
        frame = make_frame()
        frame.steps[0].status = "SKIPPED"
        result = run_validation(
            frame,
            {"id": "v1", "type": "step_status", "step": "check_mail", "status": "SKIPPED"},
        )
        self.assertTrue(result.ok)

    def test_step_status_fails_wrong_status(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "step_status", "step": "check_mail", "status": "SKIPPED"},
        )
        self.assertFalse(result.ok)

    def test_step_status_fails_missing_step(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "step_status", "step": "missing", "status": "SKIPPED"},
        )
        self.assertFalse(result.ok)

    def test_step_duration_under_passes(self):
        frame = make_frame()
        frame.steps[0].duration_ms = 100.0
        result = run_validation(
            frame,
            {"id": "v1", "type": "step_duration_under", "step": "check_mail", "max_ms": 200.0},
        )
        self.assertTrue(result.ok)

    def test_step_duration_under_fails(self):
        frame = make_frame()
        frame.steps[0].duration_ms = 300.0
        result = run_validation(
            frame,
            {"id": "v1", "type": "step_duration_under", "step": "check_mail", "max_ms": 200.0},
        )
        self.assertFalse(result.ok)

    def test_step_timed_out_passes(self):
        frame = make_frame()
        frame.attempts.append(
            {
                "step_id": "check_mail",
                "attempt": 1,
                "max_attempts": 1,
                "status": "FAILED",
                "retryable": False,
                "error_type": "StepTimeoutExceeded",
                "error_tag": "timeout",
                "message": "timeout",
                "started_at": "2026-04-30T20:00:00Z",
                "ended_at": "2026-04-30T20:00:01Z",
                "duration_ms": 1000.0,
                "timeout_seconds": 1.0,
                "timed_out": True,
                "timestamp": "2026-04-30T20:00:01Z",
            }
        )
        result = run_validation(frame, {"id": "v1", "type": "step_timed_out", "step": "check_mail"})
        self.assertTrue(result.ok)

    def test_step_not_timed_out_passes(self):
        frame = make_frame()
        frame.attempts.append(
            {
                "step_id": "check_mail",
                "attempt": 1,
                "max_attempts": 1,
                "status": "COMPLETED",
                "retryable": False,
                "error_type": "",
                "error_tag": "",
                "message": "",
                "started_at": "2026-04-30T20:00:00Z",
                "ended_at": "2026-04-30T20:00:01Z",
                "duration_ms": 1000.0,
                "timeout_seconds": 1.0,
                "timed_out": False,
                "timestamp": "2026-04-30T20:00:01Z",
            }
        )
        result = run_validation(frame, {"id": "v1", "type": "step_not_timed_out", "step": "check_mail"})
        self.assertTrue(result.ok)

    def test_attempt_count_equals_passes(self):
        frame = make_frame()
        frame.attempts.append({"step_id": "check_mail"})
        frame.attempts.append({"step_id": "check_mail"})
        result = run_validation(
            frame,
            {"id": "v1", "type": "attempt_count_equals", "step": "check_mail", "count": 2},
        )
        self.assertTrue(result.ok)

    def test_attempt_count_equals_fails(self):
        frame = make_frame()
        frame.attempts.append({"step_id": "check_mail"})
        result = run_validation(
            frame,
            {"id": "v1", "type": "attempt_count_equals", "step": "check_mail", "count": 2},
        )
        self.assertFalse(result.ok)

    def test_attempt_count_less_than_or_equal_passes(self):
        frame = make_frame()
        frame.attempts.append({"step_id": "check_mail"})
        result = run_validation(
            frame,
            {"id": "v1", "type": "attempt_count_less_than_or_equal", "step": "check_mail", "count": 2},
        )
        self.assertTrue(result.ok)

    def test_attempt_count_less_than_or_equal_fails(self):
        frame = make_frame()
        frame.attempts.append({"step_id": "check_mail"})
        frame.attempts.append({"step_id": "check_mail"})
        result = run_validation(
            frame,
            {"id": "v1", "type": "attempt_count_less_than_or_equal", "step": "check_mail", "count": 1},
        )
        self.assertFalse(result.ok)

    def test_one_of_steps_completed_passes_exactly_one_completed(self):
        frame = make_frame()
        frame.steps.append(frame.steps[0].__class__(step_id="branch_2", command="", kind="tool", namespace=None, action="", output_alias=None, status="SKIPPED"))
        result = run_validation(
            frame,
            {"id": "v1", "type": "one_of_steps_completed", "steps": ["check_mail", "branch_2"]},
        )
        self.assertTrue(result.ok)

    def test_one_of_steps_completed_fails_zero_completed(self):
        frame = make_frame()
        frame.steps[0].status = "SKIPPED"
        frame.steps.append(frame.steps[0].__class__(step_id="branch_2", command="", kind="tool", namespace=None, action="", output_alias=None, status="SKIPPED"))
        result = run_validation(
            frame,
            {"id": "v1", "type": "one_of_steps_completed", "steps": ["check_mail", "branch_2"]},
        )
        self.assertFalse(result.ok)

    def test_one_of_steps_completed_fails_more_than_one_completed(self):
        frame = make_frame()
        frame.steps.append(frame.steps[0].__class__(step_id="branch_2", command="", kind="tool", namespace=None, action="", output_alias=None, status="COMPLETED"))
        result = run_validation(
            frame,
            {"id": "v1", "type": "one_of_steps_completed", "steps": ["check_mail", "branch_2"]},
        )
        self.assertFalse(result.ok)

    def test_one_of_steps_completed_fails_missing_step(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "one_of_steps_completed", "steps": ["check_mail", "missing"]},
        )
        self.assertFalse(result.ok)

    def test_at_least_one_step_completed_passes_one_completed(self):
        frame = make_frame()
        frame.steps.append(frame.steps[0].__class__(step_id="branch_2", command="", kind="tool", namespace=None, action="", output_alias=None, status="SKIPPED"))
        result = run_validation(
            frame,
            {"id": "v1", "type": "at_least_one_step_completed", "steps": ["check_mail", "branch_2"]},
        )
        self.assertTrue(result.ok)

    def test_at_least_one_step_completed_passes_more_than_one_completed(self):
        frame = make_frame()
        frame.steps.append(frame.steps[0].__class__(step_id="branch_2", command="", kind="tool", namespace=None, action="", output_alias=None, status="COMPLETED"))
        result = run_validation(
            frame,
            {"id": "v1", "type": "at_least_one_step_completed", "steps": ["check_mail", "branch_2"]},
        )
        self.assertTrue(result.ok)

    def test_at_least_one_step_completed_fails_zero_completed(self):
        frame = make_frame()
        frame.steps[0].status = "SKIPPED"
        frame.steps.append(frame.steps[0].__class__(step_id="branch_2", command="", kind="tool", namespace=None, action="", output_alias=None, status="SKIPPED"))
        result = run_validation(
            frame,
            {"id": "v1", "type": "at_least_one_step_completed", "steps": ["check_mail", "branch_2"]},
        )
        self.assertFalse(result.ok)

    def test_condition_true_validation_passes(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "amount_above_threshold",
                "type": "condition_true",
                "condition": {"input": "date", "equals": "2026-05-02"},
            },
        )
        self.assertTrue(result.ok)

    def test_condition_false_validation_passes(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "amount_not_above_threshold",
                "type": "condition_false",
                "condition": {"input": "date", "equals": "2026-05-03"},
            },
        )
        self.assertTrue(result.ok)

    def test_no_step_failed_passes(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "no_step_failed"})
        self.assertTrue(result.ok)

    def test_no_step_failed_fails(self):
        frame = make_frame()
        frame.steps[0].status = "FAILED"
        result = run_validation(frame, {"id": "v1", "type": "no_step_failed"})
        self.assertFalse(result.ok)

    def test_no_errors_passes(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "no_errors"})
        self.assertTrue(result.ok)

    def test_no_errors_fails(self):
        frame = make_frame()
        frame.errors.append({"type": "runtime", "message": "boom"})
        result = run_validation(frame, {"id": "v1", "type": "no_errors"})
        self.assertFalse(result.ok)

    def test_required_input_exists_passes(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "required_input_exists", "input": "date"})
        self.assertTrue(result.ok)

    def test_required_input_exists_fails(self):
        frame = make_frame()
        result = run_validation(frame, {"id": "v1", "type": "required_input_exists", "input": "missing"})
        self.assertFalse(result.ok)

    def test_required_event_field_exists_passes(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "required_event_field_exists", "field": "date"},
        )
        self.assertTrue(result.ok)

    def test_required_event_field_exists_fails(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "required_event_field_exists", "field": "missing"},
        )
        self.assertFalse(result.ok)

    def test_output_has_fields_passes(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "output_has_fields", "output": "chat", "fields": ["name"]},
        )
        self.assertTrue(result.ok)

    def test_output_field_equals_passes(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {"id": "v1", "type": "output_field_equals", "output": "chat", "field": "name", "value": "Cornelia"},
        )
        self.assertTrue(result.ok)

    def test_output_in_allowed_values_passes(self):
        frame = make_frame()
        result = run_validation(
            frame,
            {
                "id": "v1",
                "type": "output_in_allowed_values",
                "output": "chat",
                "field": "name",
                "allowed": ["Cornelia", "Johan"],
            },
        )
        self.assertTrue(result.ok)

    def test_llm_call_exists_passes(self):
        frame = make_frame()
        frame.llm_calls.append(
            {
                "step_id": "summarize_message",
                "action": "summarize",
                "output_alias": "summary",
                "args": {"text": "hello"},
                "ok": True,
                "result_type": "llm_summarize_result",
                "provider": "fake",
                "model": "fake",
                "error": "",
                "timestamp": "2026-05-01T00:00:00Z",
            }
        )
        result = run_validation(frame, {"id": "v1", "type": "llm_call_exists", "output": "summary"})
        self.assertTrue(result.ok)

    def test_llm_call_ok_passes(self):
        frame = make_frame()
        frame.llm_calls.append(
            {
                "step_id": "summarize_message",
                "action": "summarize",
                "output_alias": "summary",
                "args": {"text": "hello"},
                "ok": True,
                "result_type": "llm_summarize_result",
                "provider": "fake",
                "model": "fake",
                "error": "",
                "timestamp": "2026-05-01T00:00:00Z",
            }
        )
        result = run_validation(frame, {"id": "v1", "type": "llm_call_ok", "output": "summary"})
        self.assertTrue(result.ok)

    def test_unknown_validation_type_fails(self):
        frame = make_frame()
        with self.assertRaises(UnknownValidationTypeError):
            run_validation(frame, {"id": "v1", "type": "unknown"})

    def test_run_manifest_validations_writes_results_to_frame_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(
                write_manifest(
                    Path(tmp),
                    {
                        "manifest_id": "validation.test",
                        "name": "Validation Test",
                        "version": 1,
                        "trigger": {"type": "manual"},
                        "inputs": [],
                        "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                        "validations": [
                            {"id": "no_errors", "type": "no_errors"},
                            {"id": "output_exists", "type": "output_exists", "output": "chat"},
                            {"id": "output_has_fields", "type": "output_has_fields", "output": "chat", "fields": ["name"]},
                        ],
                        "completion": {"success_outputs": ["chat"]},
                    },
                )
            )
            frame = create_taskframe(manifest)
            frame.outputs["chat"] = {"name": "Cornelia"}

            results = run_manifest_validations(frame, manifest)

            self.assertEqual(len(results), 3)
            self.assertEqual(len(frame.validations), 3)
            self.assertEqual(frame.validations[0]["validation_id"], "no_errors")
            self.assertEqual(frame.audit[-3].event_type, "VALIDATION_PASSED")
            self.assertEqual(frame.audit[-2].event_type, "VALIDATION_PASSED")
            self.assertEqual(frame.audit[-1].event_type, "VALIDATION_PASSED")
            self.assertEqual(asdict(results[0])["validation_id"], "no_errors")


if __name__ == "__main__":
    unittest.main()
