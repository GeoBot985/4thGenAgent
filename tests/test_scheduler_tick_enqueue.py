"""Spec 138 — Test: scheduler tick enqueue behaviour."""
from __future__ import annotations

import datetime
import tempfile
import unittest

from runtime.scheduler_contract import TYPE_INTERVAL, build_schedule_record
from runtime.scheduler_engine import run_scheduler_tick
from runtime.scheduler_store import create_schedule


_UTC = datetime.timezone.utc


class TestSchedulerTick(unittest.TestCase):

    def test_tick_dry_run_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "Test", "maintenance.scheduled", TYPE_INTERVAL,
                            interval_minutes=60, enabled=True, runtime_data_dir=tmp)
            now = datetime.datetime(2026, 5, 21, 12, 0, 0, tzinfo=_UTC)
            result = run_scheduler_tick(runtime_data_dir=tmp, now=now, dry_run=True)
            self.assertTrue(result["ok"])

    def test_tick_no_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scheduler_tick(runtime_data_dir=tmp, dry_run=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["schedules_checked"], 0)
            self.assertEqual(result["enqueued"], 0)

    def test_tick_disabled_schedule_not_fired(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "Test", "maintenance.scheduled", TYPE_INTERVAL,
                            interval_minutes=60, enabled=False, runtime_data_dir=tmp)
            now = datetime.datetime(2026, 5, 21, 12, 0, 0, tzinfo=_UTC)
            result = run_scheduler_tick(runtime_data_dir=tmp, now=now, dry_run=True)
            self.assertEqual(result["enqueued"], 0)

    def test_tick_dry_run_flag_in_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scheduler_tick(runtime_data_dir=tmp, dry_run=True)
            self.assertTrue(result.get("dry_run"))

    def test_tick_result_has_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_scheduler_tick(runtime_data_dir=tmp, dry_run=True)
            for key in ("ok", "dry_run", "schedules_checked", "windows_found", "enqueued", "skipped", "duplicates", "failed", "results"):
                self.assertIn(key, result, f"Missing key: {key}")
