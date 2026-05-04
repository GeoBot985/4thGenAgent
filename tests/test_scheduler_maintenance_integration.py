import tempfile
import unittest
from pathlib import Path

from runtime.errors import SchedulerError
from runtime.maintenance import run_maintenance_tick
from runtime.runtime_engine import RuntimeEngine
from runtime.scheduler import SchedulerStub


class SchedulerMaintenanceIntegrationTests(unittest.TestCase):
    def test_create_events_for_enabled_by_prefix_returns_maintenance_events(self):
        scheduler = SchedulerStub()
        events = scheduler.create_events_for_enabled_by_prefix("maintenance.")
        self.assertTrue(events)
        self.assertTrue(all(event.event_type.startswith("maintenance.") for event in events))

    def test_create_events_for_enabled_by_prefix_excludes_non_maintenance(self):
        scheduler = SchedulerStub()
        events = scheduler.create_events_for_enabled_by_prefix("maintenance.")
        event_types = {event.event_type for event in events}
        self.assertNotIn("schedule.gmail_check", event_types)
        self.assertNotIn("manual.gmail_check", event_types)

    def test_create_events_for_enabled_by_prefix_rejects_empty_prefix(self):
        scheduler = SchedulerStub()
        with self.assertRaises(SchedulerError):
            scheduler.create_events_for_enabled_by_prefix("")

    def test_run_maintenance_tick_runs_enabled_maintenance_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = SchedulerStub()
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)

            frames = run_maintenance_tick(engine, scheduler, dry_run=True)

            self.assertTrue(frames)
            self.assertTrue(all(frame.manifest_id.startswith("maintenance.") for frame in frames))
            self.assertTrue(all(frame.trigger["source"] == "scheduler" for frame in frames))

    def test_run_maintenance_tick_preserves_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = SchedulerStub()
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)

            frames = run_maintenance_tick(engine, scheduler, dry_run=True)

            self.assertTrue(frames)
            self.assertTrue(all(frame.state in {"COMPLETED", "COMPLETED_NO_DATA"} for frame in frames))

    def test_run_maintenance_tick_does_not_execute_destructive_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            report = runtime_dir / "runs" / "frame_1" / "reports" / "run_report.html"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("<html>report</html>", encoding="utf-8")

            scheduler = SchedulerStub()
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            run_maintenance_tick(engine, scheduler, dry_run=True)

            self.assertTrue(report.exists())

    def test_run_maintenance_tick_continues_after_one_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            scheduler = SchedulerStub()
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True)

            frames = run_maintenance_tick(engine, scheduler, dry_run=True)

            self.assertTrue(frames)
            self.assertTrue(all(frame.manifest_id.startswith("maintenance.") for frame in frames))


if __name__ == "__main__":
    unittest.main()
