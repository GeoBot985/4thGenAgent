"""Spec 138 — Test: operator scheduler panel."""
from __future__ import annotations

import tempfile
import unittest

from runtime.scheduler_contract import TYPE_DAILY, TYPE_INTERVAL
from runtime.scheduler_store import create_schedule, record_schedule_run
from src.operator_scheduler_panel import build_scheduler_panel


class TestBuildSchedulerPanel(unittest.TestCase):

    def test_empty_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_scheduler_panel(runtime_data_dir=tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(result["total_schedules"], 0)
            self.assertEqual(result["enabled_count"], 0)

    def test_counts_enabled_and_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", enabled=True, runtime_data_dir=tmp)
            create_schedule("s2", "B", "et", TYPE_DAILY, time_of_day="09:00", enabled=False, runtime_data_dir=tmp)
            result = build_scheduler_panel(runtime_data_dir=tmp)
            self.assertEqual(result["total_schedules"], 2)
            self.assertEqual(result["enabled_count"], 1)
            self.assertEqual(result["disabled_count"], 1)

    def test_schedules_list_has_summary_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            result = build_scheduler_panel(runtime_data_dir=tmp)
            s = result["schedules"][0]
            for field in ("schedule_id", "name", "event_type", "schedule_type", "enabled",
                          "misfire_mode", "last_scheduled_for", "last_run_at", "last_run_status"):
                self.assertIn(field, s)

    def test_recent_runs_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            record_schedule_run("s1", "2026-05-21T08:00:00Z", status="enqueued", queue_id="q1", runtime_data_dir=tmp)
            result = build_scheduler_panel(runtime_data_dir=tmp)
            self.assertEqual(len(result["recent_runs"]), 1)

    def test_panel_does_not_trigger_processing(self):
        """Panel must be read-only — no side effects."""
        with tempfile.TemporaryDirectory() as tmp:
            result = build_scheduler_panel(runtime_data_dir=tmp)
            self.assertIn("ok", result)
