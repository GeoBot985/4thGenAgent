"""Spec 138 — Test: scheduler store with filesystem backend."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.scheduler_contract import TYPE_DAILY, TYPE_INTERVAL, MISFIRE_SKIP, build_schedule_record
from runtime.scheduler_store import (
    create_schedule,
    delete_schedule,
    disable_schedule,
    enable_schedule,
    get_schedule,
    list_schedules,
    load_schedule_fixture,
    record_schedule_run,
    list_schedule_runs,
    update_schedule,
)


def _tmp():
    return tempfile.mkdtemp()


class TestCreateAndGet(unittest.TestCase):

    def test_create_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = create_schedule("s1", "Test", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(result["schedule_id"], "s1")

    def test_get_returns_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "Test", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            record = get_schedule("s1", runtime_data_dir=tmp)
            self.assertIsNotNone(record)
            self.assertEqual(record["schedule_id"], "s1")

    def test_duplicate_create_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "Test", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            result = create_schedule("s1", "Test2", "et2", TYPE_DAILY, time_of_day="09:00", runtime_data_dir=tmp)
            self.assertFalse(result["ok"])
            self.assertIn("already exists", result.get("error", ""))

    def test_get_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(get_schedule("nonexistent", runtime_data_dir=tmp))


class TestListSchedules(unittest.TestCase):

    def test_list_returns_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et1", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            create_schedule("s2", "B", "et2", TYPE_INTERVAL, interval_minutes=30, runtime_data_dir=tmp)
            records = list_schedules(runtime_data_dir=tmp)
            self.assertEqual(len(records), 2)

    def test_enabled_only_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et1", TYPE_DAILY, time_of_day="08:00", enabled=True, runtime_data_dir=tmp)
            create_schedule("s2", "B", "et2", TYPE_DAILY, time_of_day="09:00", enabled=False, runtime_data_dir=tmp)
            enabled = list_schedules(enabled_only=True, runtime_data_dir=tmp)
            self.assertEqual(len(enabled), 1)
            self.assertEqual(enabled[0]["schedule_id"], "s1")


class TestEnableDisable(unittest.TestCase):

    def test_enable_sets_enabled_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", enabled=False, runtime_data_dir=tmp)
            result = enable_schedule("s1", runtime_data_dir=tmp)
            self.assertTrue(result["ok"])
            self.assertTrue(get_schedule("s1", runtime_data_dir=tmp)["enabled"])

    def test_disable_sets_enabled_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", enabled=True, runtime_data_dir=tmp)
            disable_schedule("s1", runtime_data_dir=tmp)
            self.assertFalse(get_schedule("s1", runtime_data_dir=tmp)["enabled"])

    def test_enable_missing_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = enable_schedule("ghost", runtime_data_dir=tmp)
            self.assertFalse(result["ok"])


class TestUpdateSchedule(unittest.TestCase):

    def test_update_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "OldName", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            update_schedule("s1", name="NewName", runtime_data_dir=tmp)
            self.assertEqual(get_schedule("s1", runtime_data_dir=tmp)["name"], "NewName")

    def test_update_bumps_updated_at(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            orig = get_schedule("s1", runtime_data_dir=tmp)["updated_at"]
            time.sleep(0.01)
            update_schedule("s1", priority=50, runtime_data_dir=tmp)
            self.assertGreaterEqual(get_schedule("s1", runtime_data_dir=tmp)["updated_at"], orig)


class TestDeleteSchedule(unittest.TestCase):

    def test_delete_disables_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", enabled=True, runtime_data_dir=tmp)
            delete_schedule("s1", runtime_data_dir=tmp)
            record = get_schedule("s1", runtime_data_dir=tmp)
            self.assertFalse(record["enabled"])
            self.assertIn("deleted_at", record)

    def test_deleted_schedule_not_in_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            delete_schedule("s1", runtime_data_dir=tmp)
            records = list_schedules(runtime_data_dir=tmp)
            self.assertEqual(len(records), 0)


class TestScheduleRuns(unittest.TestCase):

    def test_record_and_list_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            record_schedule_run("s1", "2026-05-21T08:00:00Z", status="enqueued", queue_id="q1", runtime_data_dir=tmp)
            runs = list_schedule_runs("s1", runtime_data_dir=tmp)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["schedule_id"], "s1")

    def test_run_updates_last_scheduled_for(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            record_schedule_run("s1", "2026-05-21T08:00:00Z", status="enqueued", runtime_data_dir=tmp)
            self.assertEqual(get_schedule("s1", runtime_data_dir=tmp)["last_scheduled_for"], "2026-05-21T08:00:00Z")


class TestLoadFixture(unittest.TestCase):

    def test_load_valid_fixture(self):
        fixture = Path(__file__).parents[1] / "runtime_data" / "fixtures" / "schedules" / "daily_low_stock_check.json"
        with tempfile.TemporaryDirectory() as tmp:
            result = load_schedule_fixture(fixture, runtime_data_dir=tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(result["schedule_id"], "daily.low_stock_check")

    def test_load_missing_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_schedule_fixture("/nonexistent/path.json", runtime_data_dir=tmp)
            self.assertFalse(result["ok"])
