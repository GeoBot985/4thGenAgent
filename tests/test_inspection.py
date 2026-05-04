import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from runtime.inspection import RunInspector
from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, get_summary_path, load_taskframe_dict, save_taskframe
from runtime.taskframe import add_audit_event, create_taskframe


class RunInspectorTests(unittest.TestCase):
    def _create_saved_frame(self, runtime_dir: str | Path, manifest_path: str) -> tuple[object, dict]:
        manifest = load_manifest(manifest_path)
        frame = create_taskframe(manifest)
        frame.outputs["reply"] = {"label": "refund"}
        frame.outputs["category"] = {"label": "refund", "confidence": "high"}
        frame.pending_actions.append({"action_id": "pa_1", "tool": "wa/send"})
        frame.executed_actions.append({"action_id": "ea_1", "tool": "g/send"})
        frame.validations.extend(
            [
                {"validation_id": "ok_1", "ok": True, "message": "ok"},
                {"validation_id": "bad_1", "ok": False, "message": "bad"},
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
        add_audit_event(frame, "SAMPLE_AUDIT", "sample audit event", {"kind": "sample"})
        PersistenceManager(runtime_dir).save_snapshot(frame)
        return frame, load_taskframe_dict(frame.frame_id, runtime_dir)

    def test_list_runs_returns_latest_record_per_frame_id_and_applies_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")

            first = create_taskframe(manifest)
            first.state = "COMPLETED"
            PersistenceManager(tmp).save_snapshot(first)

            first.state = "FAILED_EXECUTION"
            PersistenceManager(tmp).save_snapshot(first)

            second = create_taskframe(manifest)
            second.state = "COMPLETED_NO_DATA"
            PersistenceManager(tmp).save_snapshot(second)

            result = inspector.list_runs(limit=1)

            self.assertTrue(result.ok)
            self.assertEqual(result.data["count"], 1)
            self.assertEqual(len(result.data["runs"]), 1)
            self.assertIn(result.data["runs"][0]["frame_id"], {first.frame_id, second.frame_id})

            all_runs = inspector.list_runs(limit=10)
            frame_ids = {item["frame_id"] for item in all_runs.data["runs"]}
            self.assertEqual(frame_ids, {first.frame_id, second.frame_id})
            self.assertEqual(
                next(item for item in all_runs.data["runs"] if item["frame_id"] == first.frame_id)["state"],
                "FAILED_EXECUTION",
            )

    def test_list_runs_returns_empty_when_no_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            result = inspector.list_runs()

            self.assertTrue(result.ok)
            self.assertEqual(result.data["count"], 0)
            self.assertEqual(result.data["runs"], [])

    def test_get_cleanup_reports_returns_empty_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            result = inspector.get_cleanup_reports()

            self.assertTrue(result.ok)
            self.assertEqual(result.data["count"], 0)
            self.assertEqual(result.data["cleanup_reports"], [])

    def test_get_run_summary_returns_summary_and_missing_frame_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            frame, _ = self._create_saved_frame(tmp, "manifests/smoke_gmail_check.manifest.json")

            summary = inspector.get_run_summary(frame.frame_id)
            self.assertTrue(summary.ok)
            self.assertEqual(summary.data["frame_id"], frame.frame_id)
            self.assertEqual(summary.data["manifest_id"], frame.manifest_id)
            self.assertEqual(summary.data["state"], frame.state)

            missing = inspector.get_run_summary("missing")
            self.assertFalse(missing.ok)
            self.assertEqual(missing.error, "TaskFrame artifact not found: missing")

    def test_get_taskframe_outputs_audit_validations_errors_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            frame, original_taskframe = self._create_saved_frame(tmp, "manifests/smoke_gmail_check.manifest.json")

            taskframe = inspector.get_taskframe(frame.frame_id)
            self.assertTrue(taskframe.ok)
            self.assertEqual(taskframe.data["frame_id"], frame.frame_id)
            self.assertEqual(taskframe.data["outputs"], frame.outputs)

            outputs = inspector.get_outputs(frame.frame_id)
            self.assertTrue(outputs.ok)
            self.assertEqual(outputs.data["frame_id"], frame.frame_id)
            self.assertEqual(outputs.data["output_keys"], sorted(frame.outputs.keys()))

            audit = inspector.get_audit(frame.frame_id, limit=1)
            self.assertTrue(audit.ok)
            self.assertEqual(audit.data["frame_id"], frame.frame_id)
            self.assertEqual(audit.data["count"], 1)

            validations = inspector.get_validations(frame.frame_id)
            self.assertTrue(validations.ok)
            self.assertEqual(validations.data["count"], 2)

            failed = inspector.get_validations(frame.frame_id, failed_only=True)
            self.assertTrue(failed.ok)
            self.assertTrue(failed.data["failed_only"])
            self.assertEqual(failed.data["count"], 1)

            errors = inspector.get_errors(frame.frame_id)
            self.assertTrue(errors.ok)
            self.assertEqual(errors.data["count"], 1)

            pending = inspector.get_pending_actions(frame.frame_id)
            self.assertTrue(pending.ok)
            self.assertEqual(pending.data["count"], 1)

            executed = inspector.get_executed_actions(frame.frame_id)
            self.assertTrue(executed.ok)
            self.assertEqual(executed.data["count"], 1)

            attempts = inspector.get_attempts(frame.frame_id)
            self.assertTrue(attempts.ok)
            self.assertEqual(attempts.data["count"], 1)

            tool_calls = inspector.get_tool_calls(frame.frame_id)
            self.assertTrue(tool_calls.ok)
            self.assertEqual(tool_calls.data["count"], 1)

            llm_calls = inspector.get_llm_calls(frame.frame_id)
            self.assertTrue(llm_calls.ok)
            self.assertEqual(llm_calls.data["count"], 1)

            after = load_taskframe_dict(frame.frame_id, tmp)
            self.assertEqual(original_taskframe, after)

    def test_missing_summary_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            frame, _ = self._create_saved_frame(tmp, "manifests/smoke_gmail_check.manifest.json")
            summary_path = get_summary_path(frame.frame_id, tmp)
            summary_path.unlink()

            result = inspector.get_run_summary(frame.frame_id)
            self.assertFalse(result.ok)
            self.assertEqual(result.error, f"TaskFrame artifact not found: {frame.frame_id}")

    def test_inspection_results_are_json_serializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            frame, _ = self._create_saved_frame(tmp, "manifests/smoke_gmail_check.manifest.json")

            result = inspector.get_outputs(frame.frame_id)
            json.dumps(asdict(result))

            result = inspector.list_runs()
            json.dumps(asdict(result))

    def test_get_cleanup_reports_returns_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspector = RunInspector(tmp)
            cleanup_dir = Path(tmp) / "cleanup"
            cleanup_dir.mkdir(parents=True, exist_ok=True)
            report_path = cleanup_dir / "cleanup_cln_123.json"
            report_path.write_text(
                json.dumps(
                    {
                        "cleanup_id": "cln_123",
                        "created_at": "2026-05-01T00:00:00Z",
                        "dry_run": True,
                        "summary": {
                            "candidate_count": 2,
                            "deleted_count": 0,
                            "error_count": 0,
                        },
                        "candidates": [{"candidate_id": "cc_1"}],
                        "protected": [],
                        "deleted": [],
                        "errors": [],
                    }
                ),
                encoding="utf-8",
            )

            result = inspector.get_cleanup_reports()

            self.assertTrue(result.ok)
            self.assertEqual(result.data["count"], 1)
            self.assertEqual(result.data["cleanup_reports"][0]["cleanup_id"], "cln_123")
            self.assertEqual(result.data["cleanup_reports"][0]["candidate_count"], 2)
            self.assertNotIn("candidates", result.data["cleanup_reports"][0])


if __name__ == "__main__":
    unittest.main()
