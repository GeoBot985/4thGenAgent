import tempfile
import unittest
from pathlib import Path

from runtime.artifact_cleanup import ArtifactCleaner
from runtime.cleanup_commands import CleanupCommandRunner
from runtime.command_parser import parse_command
from runtime.errors import CommandParseError
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe


class CleanupCommandTests(unittest.TestCase):
    def _make_runtime_dir_with_report(self) -> tuple[Path, str]:
        tmp = tempfile.TemporaryDirectory()
        runtime_dir = Path(tmp.name)
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)
        frame.state = "COMPLETED"
        frame.outputs["unread_mail"] = {"count": 1}
        from runtime.persistence import PersistenceManager

        PersistenceManager(runtime_dir).save_snapshot(frame)
        report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("<html>report</html>", encoding="utf-8")
        return runtime_dir, tmp.name

    def _make_frame(self, manifest_path: str, inputs: dict | None = None):
        manifest = load_manifest(manifest_path)
        frame = create_taskframe(manifest, inputs=inputs or {})
        return frame

    def test_parser_parses_cleanup_commands(self):
        cases = [
            ("[c:plan -> cleanup_plan] mode=\"derived_artifacts_only\"; max_report_age_days=30", "plan", "cleanup_plan"),
            ("[c:execute -> cleanup_result] mode=\"reports_only\"; dry_run=false; confirm_cleanup=true", "execute", "cleanup_result"),
            ("[c:reports_plan -> report_cleanup] max_report_age_days=0", "reports_plan", "report_cleanup"),
            ("[c:index_plan -> index_cleanup]", "index_plan", "index_cleanup"),
            ("[c:temp_plan -> temp_cleanup] max_temp_age_days=0", "temp_plan", "temp_cleanup"),
        ]
        for command, action, alias in cases:
            parsed = parse_command(command)
            self.assertEqual(parsed.kind, "cleanup")
            self.assertEqual(parsed.action, action)
            self.assertEqual(parsed.output_alias, alias)

    def test_parser_rejects_invalid_cleanup_commands(self):
        for command in [
            "[c]",
            "[c:plan]",
            "[c:plan ->]",
            "[c:/plan -> x]",
            "[c:delete_all -> x]",
            "[c:delete_runs -> x]",
            "[c:purge -> x]",
            "[c:wipe -> x]",
            "[c:force -> x]",
        ]:
            with self.subTest(command=command):
                with self.assertRaises(CommandParseError):
                    parse_command(command)

    def test_runner_plan_writes_output_and_forces_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html>report</html>", encoding="utf-8")

            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))
            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertIn("cleanup_plan", frame.outputs)
            self.assertTrue(frame.outputs["cleanup_plan"]["dry_run"])
            self.assertTrue(Path(frame.outputs["cleanup_plan"]["report_path"]).is_file())

    def test_runner_execute_requires_dry_run_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_execute_confirmed.manifest.json")
            frame = create_taskframe(manifest, inputs={"confirm_cleanup": "true"})
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html>report</html>", encoding="utf-8")

            frame.steps[0].command = "[c:execute -> cleanup_result] mode=\"reports_only\"; dry_run=true; confirm_cleanup=true; max_report_age_days=0"
            frame.steps[0].action = "execute"
            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))
            result = runner.run_step(frame, frame.steps[0])

            self.assertFalse(result.ok)
            self.assertEqual(frame.steps[0].status, "FAILED")

    def test_runner_execute_requires_confirm_cleanup_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_execute_confirmed.manifest.json")
            frame = create_taskframe(manifest, inputs={"confirm_cleanup": "false"})
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html>report</html>", encoding="utf-8")

            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))
            result = runner.run_step(frame, frame.steps[0])

            self.assertFalse(result.ok)
            self.assertEqual(frame.steps[0].status, "FAILED")

    def test_runner_reports_plan_sets_mode_reports_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))

            frame.steps[0].command = "[c:reports_plan -> report_cleanup_plan] max_report_age_days=0"
            frame.steps[0].action = "reports_plan"
            frame.steps[0].output_alias = "report_cleanup_plan"
            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["report_cleanup_plan"]["policy"]["mode"], "reports_only")

    def test_runner_index_plan_sets_mode_indexes_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))

            frame.steps[0].command = "[c:index_plan -> index_cleanup]"
            frame.steps[0].action = "index_plan"
            frame.steps[0].output_alias = "index_cleanup"
            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["index_cleanup"]["policy"]["mode"], "indexes_only")

    def test_runner_temp_plan_sets_mode_temp_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))

            frame.steps[0].command = "[c:temp_plan -> temp_cleanup] max_temp_age_days=0"
            frame.steps[0].action = "temp_plan"
            frame.steps[0].output_alias = "temp_cleanup"
            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["temp_cleanup"]["policy"]["mode"], "temp_only")

    def test_runner_marks_step_failed_on_policy_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))

            frame.steps[0].command = "[c:plan -> cleanup_plan] mode=\"all\""
            frame.steps[0].action = "plan"
            result = runner.run_step(frame, frame.steps[0])

            self.assertFalse(result.ok)
            self.assertEqual(frame.steps[0].status, "FAILED")
            self.assertIn("CLEANUP_COMMAND_FAILED", [event.event_type for event in frame.audit])

    def test_runner_records_audit_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html>report</html>", encoding="utf-8")

            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))
            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            event_types = [event.event_type for event in frame.audit]
            self.assertIn("CLEANUP_COMMAND_STARTED", event_types)
            self.assertIn("CLEANUP_COMMAND_COMPLETED", event_types)

    def test_runner_writes_cleanup_report_path_to_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest("manifests/smoke_cleanup_dry_run.manifest.json")
            frame = create_taskframe(manifest)
            from runtime.persistence import PersistenceManager

            PersistenceManager(runtime_dir).save_snapshot(frame)
            report_path = runtime_dir / "runs" / frame.frame_id / "reports" / "run_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("<html>report</html>", encoding="utf-8")

            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_dir))
            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertTrue(Path(frame.outputs["cleanup_plan"]["report_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
