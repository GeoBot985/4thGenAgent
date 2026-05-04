import json
import tempfile
import unittest
from pathlib import Path

from runtime.events import create_event
from runtime.runtime_engine import RuntimeEngine
from runtime.scheduler import SchedulerStub


class ScheduledMaintenanceTests(unittest.TestCase):
    def test_schedules_json_includes_maintenance_entries(self):
        schedules = json.loads(Path("manifests/schedules.json").read_text(encoding="utf-8"))
        schedule_ids = {item["schedule_id"] for item in schedules["schedules"]}
        self.assertIn("maintenance.artifact_index_rebuild", schedule_ids)
        self.assertIn("maintenance.cleanup_dry_run", schedule_ids)
        self.assertIn("maintenance.report_failed_runs", schedule_ids)
        self.assertIn("maintenance.report_pending_runs", schedule_ids)
        self.assertIn("maintenance.report_live_packs", schedule_ids)

    def test_event_routes_json_routes_maintenance_entries(self):
        routes = json.loads(Path("manifests/event_routes.json").read_text(encoding="utf-8"))
        event_types = {item["event_type"] for item in routes["routes"]}
        self.assertIn("maintenance.artifact_index_rebuild", event_types)
        self.assertIn("maintenance.cleanup_dry_run", event_types)
        self.assertIn("maintenance.report_failed_runs", event_types)
        self.assertIn("maintenance.report_pending_runs", event_types)
        self.assertIn("maintenance.report_live_packs", event_types)

    def test_runtime_engine_handles_maintenance_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            scheduler = SchedulerStub()
            for event_type in [
                "maintenance.artifact_index_rebuild",
                "maintenance.cleanup_dry_run",
                "maintenance.report_failed_runs",
                "maintenance.report_pending_runs",
                "maintenance.report_live_packs",
            ]:
                with self.subTest(event_type=event_type):
                    frame = engine.handle_event(scheduler.create_event_for_schedule(event_type), dry_run=True)
                    self.assertEqual(frame.trigger["source"], "scheduler")
                    self.assertTrue(frame.state in {"COMPLETED", "COMPLETED_NO_DATA"})
                    self.assertTrue(frame.manifest_id.startswith("maintenance."))

    def test_persisted_maintenance_frame_has_scheduler_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = RuntimeEngine(runtime_data_dir=tmp, persist_runs=True)
            scheduler = SchedulerStub()
            frame = engine.handle_event(scheduler.create_event_for_schedule("maintenance.artifact_index_rebuild"), dry_run=True)

            self.assertEqual(frame.trigger["source"], "scheduler")
            self.assertEqual(frame.trigger["event_type"], "maintenance.artifact_index_rebuild")


if __name__ == "__main__":
    unittest.main()
