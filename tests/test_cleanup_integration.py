import os
import tempfile
import time
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.inspection import RunInspector
from runtime.inspection_commands import InspectionCommandRunner
from runtime.manifest_loader import load_manifest
from runtime.persistence import get_taskframe_path
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe import create_taskframe


def _touch_old(path: Path, days: float) -> None:
    timestamp = time.time() - (days * 86400.0)
    os.utime(path, (timestamp, timestamp))


class CleanupIntegrationTests(unittest.TestCase):
    def _prepare_report_candidate(self, engine: RuntimeEngine) -> tuple[str, Path]:
        target = engine.handle_event(
            create_event(
                event_type="manual.gmail_check",
                source="manual",
                payload={},
            ),
            dry_run=True,
        )
        report_path = Path(engine.runtime_data_dir) / "runs" / target.frame_id / "reports" / "run_report.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("<html>report</html>", encoding="utf-8")
        _touch_old(report_path, 5)
        return target.frame_id, report_path

    def test_runtime_engine_handles_manual_cleanup_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)

            frame = engine.handle_event(
                create_event(
                    event_type="manual.cleanup_dry_run",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            self.assertEqual(frame.state, "COMPLETED")
            self.assertTrue(frame.outputs["cleanup_plan"]["dry_run"])
            self.assertTrue(Path(frame.outputs["cleanup_plan"]["report_path"]).is_file())
            self.assertGreaterEqual(frame.outputs["cleanup_plan"]["summary"]["candidate_count"], 1)

    def test_runtime_engine_handles_manual_cleanup_reports_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)

            frame = engine.handle_event(
                create_event(
                    event_type="manual.cleanup_reports_dry_run",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            self.assertEqual(frame.state, "COMPLETED")
            self.assertTrue(frame.outputs["report_cleanup_plan"]["dry_run"])
            self.assertTrue(Path(frame.outputs["report_cleanup_plan"]["report_path"]).is_file())

    def test_runtime_engine_handles_manual_cleanup_execute_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            _, report_path = self._prepare_report_candidate(engine)

            frame = engine.handle_event(
                create_event(
                    event_type="manual.cleanup_execute_confirmed",
                    source="manual",
                    payload={"confirm_cleanup": "true"},
                ),
                dry_run=True,
            )

            self.assertEqual(frame.state, "COMPLETED")
            self.assertTrue(frame.outputs["cleanup_result"]["dry_run"] is False)
            self.assertFalse(report_path.exists())
            self.assertTrue(Path(frame.outputs["cleanup_result"]["report_path"]).is_file())

    def test_runtime_engine_handles_manual_cleanup_blocked_without_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)

            frame = engine.handle_event(
                create_event(
                    event_type="manual.cleanup_blocked_without_confirmation",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertIn("cleanup_result", frame.outputs)

    def test_cleanup_command_frame_is_persisted_when_persist_runs_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)

            frame = engine.handle_event(
                create_event(
                    event_type="manual.cleanup_dry_run",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            self.assertTrue(get_taskframe_path(frame.frame_id, tmp).is_file())

    def test_cleanup_report_artifact_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)

            frame = engine.handle_event(
                create_event(
                    event_type="manual.cleanup_dry_run",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            cleanup_dir = Path(tmp) / "cleanup"
            self.assertTrue(cleanup_dir.is_dir())
            self.assertTrue(any(cleanup_dir.glob("cleanup_*.json")))
            self.assertTrue(Path(frame.outputs["cleanup_plan"]["report_path"]).is_file())

    def test_run_inspector_lists_cleanup_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)
            engine.handle_event(
                create_event(
                    event_type="manual.cleanup_dry_run",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            result = engine.inspector.get_cleanup_reports()

            self.assertTrue(result.ok)
            self.assertGreaterEqual(result.data["count"], 1)
            self.assertIn("cleanup_reports", result.data)
            self.assertIn("path", result.data["cleanup_reports"][0])

    def test_cleanup_reports_command_returns_cleanup_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            self._prepare_report_candidate(engine)
            engine.handle_event(
                create_event(
                    event_type="manual.cleanup_dry_run",
                    source="manual",
                    payload={},
                ),
                dry_run=True,
            )

            inspector = RunInspector(tmp)
            runner = InspectionCommandRunner(inspector=inspector)
            manifest = load_manifest("manifests/smoke_inspect_recent_runs.manifest.json")
            frame = create_taskframe(manifest)
            frame.steps[0].command = "[i:cleanup_reports -> cleanup_reports]"
            frame.steps[0].action = "cleanup_reports"
            frame.steps[0].output_alias = "cleanup_reports"

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertGreaterEqual(frame.outputs["cleanup_reports"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
