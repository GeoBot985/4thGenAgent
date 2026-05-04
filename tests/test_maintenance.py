import tempfile
import unittest
from pathlib import Path

from runtime.artifact_index import get_artifact_index_path
from runtime.maintenance import MaintenanceCommandRunner
from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager
from runtime.taskframe import create_taskframe


class MaintenanceCommandTests(unittest.TestCase):
    def _make_frame(self, manifest_path: str, runtime_dir: Path):
        manifest = load_manifest(manifest_path)
        frame = create_taskframe(manifest)
        PersistenceManager(runtime_dir).save_snapshot(frame)
        return frame

    def test_parser_parses_maintenance_commands(self):
        from runtime.command_parser import parse_command

        cases = [
            ("[mt:index_rebuild -> result]", "index_rebuild", "result"),
            ("[mt:cleanup_dry_run -> cleanup_plan] mode=\"derived_artifacts_only\"", "cleanup_dry_run", "cleanup_plan"),
            ("[mt:report_failed_runs -> report_result] limit=20; rebuild=true", "report_failed_runs", "report_result"),
            ("[mt:report_pending_runs -> report_result] limit=20; rebuild=true", "report_pending_runs", "report_result"),
            ("[mt:report_live_packs -> report_result] limit=20; rebuild=true", "report_live_packs", "report_result"),
            ("[mt:summary -> maintenance_summary] rebuild=true", "summary", "maintenance_summary"),
        ]
        for command, action, alias in cases:
            parsed = parse_command(command)
            self.assertEqual(parsed.kind, "maintenance")
            self.assertEqual(parsed.namespace, "mt")
            self.assertEqual(parsed.action, action)
            self.assertEqual(parsed.output_alias, alias)

    def test_parser_rejects_invalid_maintenance_commands(self):
        from runtime.command_parser import parse_command
        from runtime.errors import CommandParseError

        for command in [
            "[mt]",
            "[mt:index_rebuild]",
            "[mt:index_rebuild ->]",
            "[mt:/index_rebuild -> x]",
            "[mt:delete -> x]",
            "[mt:execute -> x]",
            "[mt:approve -> x]",
            "[mt:live -> x]",
        ]:
            with self.subTest(command=command):
                with self.assertRaises(CommandParseError):
                    parse_command(command)

    def test_runner_index_rebuild_writes_output_and_creates_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            runner = MaintenanceCommandRunner(runtime_dir)
            frame = create_taskframe(load_manifest("manifests/maintenance_rebuild_artifact_index.manifest.json"))
            PersistenceManager(runtime_dir).save_snapshot(frame)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("index_result", frame.outputs)
            self.assertTrue(get_artifact_index_path(runtime_dir).is_file())

    def test_runner_cleanup_dry_run_writes_output_and_forces_safe_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html>report</html>", encoding="utf-8")
            runner = MaintenanceCommandRunner(runtime_dir)
            frame = create_taskframe(
                load_manifest("manifests/maintenance_cleanup_dry_run.manifest.json"),
                inputs={"mode": "reports_only", "max_report_age_days": 0, "max_temp_age_days": 0},
            )
            PersistenceManager(runtime_dir).save_snapshot(frame)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertTrue(frame.outputs["cleanup_plan"]["dry_run"])
            self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_runner_report_failed_runs_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            frame.state = "FAILED_EXECUTION"
            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = MaintenanceCommandRunner(runtime_dir)
            manifest = load_manifest("manifests/maintenance_report_failed_runs.manifest.json")
            report_frame = create_taskframe(manifest, inputs={"limit": 20, "rebuild": True})
            PersistenceManager(runtime_dir).save_snapshot(report_frame)

            result = runner.run_step(report_frame, report_frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(report_frame.steps[0].status, "COMPLETED")
            self.assertIn("report_result", report_frame.outputs)
            self.assertGreaterEqual(report_frame.outputs["report_result"]["matched_count"], 1)

    def test_runner_report_pending_runs_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            frame.pending_actions.append({"action_id": "pa_1", "tool": "wa/send"})
            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = MaintenanceCommandRunner(runtime_dir)
            manifest = load_manifest("manifests/maintenance_report_pending_runs.manifest.json")
            report_frame = create_taskframe(manifest, inputs={"limit": 20, "rebuild": True})
            PersistenceManager(runtime_dir).save_snapshot(report_frame)

            result = runner.run_step(report_frame, report_frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(report_frame.steps[0].status, "COMPLETED")
            self.assertIn("report_result", report_frame.outputs)

    def test_runner_report_live_packs_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame = self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            pack_path = runtime_dir / "runs" / frame.frame_id / "approval_packs" / "pack.json"
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            pack_path.write_text('{"status":"USED"}', encoding="utf-8")
            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = MaintenanceCommandRunner(runtime_dir)
            manifest = load_manifest("manifests/maintenance_report_live_packs.manifest.json")
            report_frame = create_taskframe(manifest, inputs={"limit": 20, "rebuild": True})
            PersistenceManager(runtime_dir).save_snapshot(report_frame)

            result = runner.run_step(report_frame, report_frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(report_frame.steps[0].status, "COMPLETED")
            self.assertIn("report_result", report_frame.outputs)

    def test_runner_summary_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            runner = MaintenanceCommandRunner(runtime_dir)
            manifest = load_manifest("manifests/maintenance_rebuild_artifact_index.manifest.json")
            frame = create_taskframe(manifest, inputs={})
            frame.steps[0].command = "[mt:summary -> maintenance_summary] rebuild=true"
            frame.steps[0].action = "summary"
            frame.steps[0].output_alias = "maintenance_summary"
            PersistenceManager(runtime_dir).save_snapshot(frame)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("maintenance_summary", frame.outputs)
            self.assertIn("cleanup_report_count", frame.outputs["maintenance_summary"])

    def test_runner_marks_step_failed_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            runner = MaintenanceCommandRunner(runtime_dir)
            manifest = load_manifest("manifests/maintenance_rebuild_artifact_index.manifest.json")
            frame = create_taskframe(manifest)
            frame.steps[0].command = "[mt:delete -> result]"
            frame.steps[0].action = "delete"
            frame.steps[0].output_alias = "result"
            PersistenceManager(runtime_dir).save_snapshot(frame)

            result = runner.run_step(frame, frame.steps[0])

            self.assertFalse(result.ok)
            self.assertEqual(frame.steps[0].status, "FAILED")
            self.assertIn("MAINTENANCE_COMMAND_FAILED", [event.event_type for event in frame.audit])

    def test_runner_records_audit_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._make_frame("manifests/smoke_gmail_check.manifest.json", runtime_dir)
            runner = MaintenanceCommandRunner(runtime_dir)
            manifest = load_manifest("manifests/maintenance_rebuild_artifact_index.manifest.json")
            frame = create_taskframe(manifest)
            PersistenceManager(runtime_dir).save_snapshot(frame)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            event_types = [event.event_type for event in frame.audit]
            self.assertIn("MAINTENANCE_COMMAND_STARTED", event_types)
            self.assertIn("MAINTENANCE_COMMAND_COMPLETED", event_types)


if __name__ == "__main__":
    unittest.main()
