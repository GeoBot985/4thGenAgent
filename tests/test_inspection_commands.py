import tempfile
import unittest
from pathlib import Path

from runtime.command_parser import parse_command
from runtime.errors import CommandParseError
from runtime.inspection import RunInspector
from runtime.inspection_commands import InspectionCommandRunner
from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, load_taskframe_dict, save_taskframe
from runtime.taskframe import create_taskframe


class InspectionCommandTests(unittest.TestCase):
    def _create_source_frame(self, runtime_dir: str | Path):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "COMPLETED"
        frame.outputs["unread_mail"] = [{"id": "1", "subject": "Hello"}]
        frame.outputs["reply"] = {"body": "Thanks"}
        frame.outputs["category"] = {"label": "refund", "confidence": "high"}
        frame.pending_actions.append({"action_id": "pa_1", "tool": "wa/send"})
        frame.executed_actions.append({"action_id": "ea_1", "tool": "g/send"})
        frame.validations.extend(
            [
                {"validation_id": "good", "ok": True, "message": "good"},
                {"validation_id": "bad", "ok": False, "message": "bad"},
            ]
        )
        frame.errors.append({"type": "sample_error", "message": "boom", "data": {}})
        frame.attempts.append(
            {
                "step_id": "step_1",
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
                "timeout_seconds": None,
                "timed_out": False,
                "timestamp": "2026-04-30T20:00:01Z",
            }
        )
        frame.tool_calls.append({"step_id": "step_1", "tool": "g/check", "ok": True})
        frame.llm_calls.append({"step_id": "step_2", "action": "draft", "ok": True})
        PersistenceManager(runtime_dir).save_snapshot(frame)
        return frame

    def test_parser_accepts_inspection_commands(self):
        parsed = parse_command("[i:list_runs -> runs] limit=10")
        self.assertEqual(parsed.kind, "inspection")
        self.assertEqual(parsed.action, "list_runs")
        self.assertEqual(parsed.output_alias, "runs")

        parsed = parse_command("[i:summary -> summary] frame_id=$inputs.frame_id")
        self.assertEqual(parsed.action, "summary")
        self.assertEqual(parsed.output_alias, "summary")

        parsed = parse_command("[i:outputs -> outputs] frame_id=$inputs.frame_id")
        self.assertEqual(parsed.action, "outputs")

        parsed = parse_command("[i:audit -> audit] frame_id=$inputs.frame_id; limit=20")
        self.assertEqual(parsed.action, "audit")

        parsed = parse_command("[i:validations -> failed_validations] frame_id=$inputs.frame_id; failed_only=true")
        self.assertEqual(parsed.action, "validations")

        parsed = parse_command("[i:cleanup_reports -> cleanup_reports]")
        self.assertEqual(parsed.action, "cleanup_reports")

    def test_parser_rejects_invalid_inspection_commands(self):
        for command in [
            "[i]",
            "[i:summary]",
            "[i:summary ->]",
            "[i:/summary -> x]",
            '[i:delete -> x] frame_id="tf_abc"',
            '[i:resume -> x] frame_id="tf_abc"',
            '[i:approve -> x] frame_id="tf_abc"',
        ]:
            with self.subTest(command=command):
                with self.assertRaises(CommandParseError):
                    parse_command(command)

    def test_runner_writes_outputs_for_read_only_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            source = self._create_source_frame(runtime_dir)
            inspector = RunInspector(runtime_dir)
            runner = InspectionCommandRunner(inspector=inspector)
            inspection_manifest = load_manifest("manifests/smoke_inspect_run_summary.manifest.json")
            frame = create_taskframe(inspection_manifest, inputs={"frame_id": source.frame_id})

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("run_summary", frame.outputs)
            self.assertEqual(frame.outputs["run_summary"]["frame_id"], source.frame_id)
            self.assertIn("INSPECTION_COMMAND_STARTED", [event.event_type for event in frame.audit])
            self.assertIn("INSPECTION_COMMAND_COMPLETED", [event.event_type for event in frame.audit])

    def test_runner_supports_list_runs_and_argument_coercion(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            source = self._create_source_frame(runtime_dir)
            inspector = RunInspector(runtime_dir)
            runner = InspectionCommandRunner(inspector=inspector)
            inspection_manifest = load_manifest("manifests/smoke_inspect_recent_runs.manifest.json")
            frame = create_taskframe(inspection_manifest)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("runs", frame.outputs)
            self.assertGreaterEqual(frame.outputs["runs"]["count"], 1)
            self.assertTrue(any(item["frame_id"] == source.frame_id for item in frame.outputs["runs"]["runs"]))

    def test_runner_supports_outputs_audit_validations_and_bool_limit_coercion(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            source = self._create_source_frame(runtime_dir)
            inspector = RunInspector(runtime_dir)
            runner = InspectionCommandRunner(inspector=inspector)

            outputs_manifest = load_manifest("manifests/smoke_inspect_run_outputs.manifest.json")
            outputs_frame = create_taskframe(outputs_manifest, inputs={"frame_id": source.frame_id})
            outputs_result = runner.run_step(outputs_frame, outputs_frame.steps[0])
            self.assertTrue(outputs_result.ok)
            self.assertEqual(outputs_frame.outputs["run_outputs"]["frame_id"], source.frame_id)

            audit_manifest = load_manifest("manifests/smoke_inspect_run_summary.manifest.json")
            audit_frame = create_taskframe(audit_manifest, inputs={"frame_id": source.frame_id})
            audit_frame.steps[0].command = "[i:audit -> audit] frame_id=$inputs.frame_id; limit=1"
            audit_frame.steps[0].action = "audit"
            audit_frame.steps[0].output_alias = "audit"
            audit_result = runner.run_step(audit_frame, audit_frame.steps[0])
            self.assertTrue(audit_result.ok)
            self.assertEqual(audit_frame.outputs["audit"]["count"], 1)

            validations_manifest = load_manifest("manifests/smoke_inspect_run_summary.manifest.json")
            validations_frame = create_taskframe(validations_manifest, inputs={"frame_id": source.frame_id})
            validations_frame.steps[0].command = "[i:validations -> failed_validations] frame_id=$inputs.frame_id; failed_only=true"
            validations_frame.steps[0].action = "validations"
            validations_frame.steps[0].output_alias = "failed_validations"
            validations_result = runner.run_step(validations_frame, validations_frame.steps[0])
            self.assertTrue(validations_result.ok)
            self.assertEqual(validations_frame.outputs["failed_validations"]["count"], 1)
            self.assertTrue(validations_frame.outputs["failed_validations"]["failed_only"])

    def test_runner_supports_cleanup_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            cleanup_dir = runtime_dir / "cleanup"
            cleanup_dir.mkdir(parents=True, exist_ok=True)
            (cleanup_dir / "cleanup_cln_123.json").write_text(
                """
                {
                  "cleanup_id": "cln_123",
                  "created_at": "2026-05-01T00:00:00Z",
                  "dry_run": true,
                  "summary": {
                    "candidate_count": 1,
                    "deleted_count": 0,
                    "error_count": 0
                  },
                  "candidates": [],
                  "protected": [],
                  "deleted": [],
                  "errors": []
                }
                """.strip(),
                encoding="utf-8",
            )
            inspector = RunInspector(runtime_dir)
            runner = InspectionCommandRunner(inspector=inspector)
            manifest = load_manifest("manifests/smoke_inspect_recent_runs.manifest.json")
            frame = create_taskframe(manifest)
            frame.steps[0].command = "[i:cleanup_reports -> cleanup_reports]"
            frame.steps[0].action = "cleanup_reports"
            frame.steps[0].output_alias = "cleanup_reports"

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("cleanup_reports", frame.outputs)
            self.assertEqual(frame.outputs["cleanup_reports"]["count"], 1)

    def test_runner_marks_failed_inspection_as_failed_and_does_not_mutate_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            source = self._create_source_frame(runtime_dir)
            before = load_taskframe_dict(source.frame_id, runtime_dir)
            inspector = RunInspector(runtime_dir)
            runner = InspectionCommandRunner(inspector=inspector)
            inspection_manifest = load_manifest("manifests/smoke_inspect_run_summary.manifest.json")
            frame = create_taskframe(inspection_manifest, inputs={"frame_id": "missing"})

            result = runner.run_step(frame, frame.steps[0])

            self.assertFalse(result.ok)
            self.assertEqual(frame.steps[0].status, "FAILED")
            self.assertIn("INSPECTION_COMMAND_FAILED", [event.event_type for event in frame.audit])
            after = load_taskframe_dict(source.frame_id, runtime_dir)
            self.assertEqual(before, after)

    def test_runner_missing_frame_marks_step_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            inspector = RunInspector(runtime_dir)
            runner = InspectionCommandRunner(inspector=inspector)
            inspection_manifest = load_manifest("manifests/smoke_inspect_run_summary.manifest.json")
            frame = create_taskframe(inspection_manifest, inputs={"frame_id": "missing"})

            result = runner.run_step(frame, frame.steps[0])

            self.assertFalse(result.ok)
            self.assertEqual(frame.steps[0].status, "FAILED")
            self.assertEqual(result.frame_id, "missing")
            self.assertIn("TaskFrame artifact not found", result.error)


if __name__ == "__main__":
    unittest.main()
