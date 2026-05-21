"""Spec 138 — Test: scheduler store with SQLite backend."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.scheduler_contract import TYPE_DAILY, TYPE_INTERVAL
from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend
from runtime.scheduler_contract import build_schedule_record, build_schedule_run_record, RUN_STATUS_ENQUEUED


class TestSQLiteScheduleStore(unittest.TestCase):

    def _backend(self, tmp: str) -> SQLitePersistenceBackend:
        db_path = Path(tmp) / "test.db"
        backend = SQLitePersistenceBackend(db_path)
        backend.init_schema()
        return backend

    def test_save_and_get_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            record = build_schedule_record("s1", "Test", "et", TYPE_DAILY, time_of_day="08:00")
            backend.save_schedule_record(record)
            loaded = backend.get_schedule_record("s1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["schedule_id"], "s1")
            self.assertEqual(loaded["name"], "Test")

    def test_get_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            self.assertIsNone(backend.get_schedule_record("nonexistent"))

    def test_list_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            backend.save_schedule_record(build_schedule_record("s1", "A", "et1", TYPE_DAILY, time_of_day="08:00", enabled=True))
            backend.save_schedule_record(build_schedule_record("s2", "B", "et2", TYPE_INTERVAL, interval_minutes=30, enabled=False))
            all_records = backend.list_schedule_records()
            self.assertEqual(len(all_records), 2)

    def test_list_schedules_enabled_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            backend.save_schedule_record(build_schedule_record("s1", "A", "et1", TYPE_DAILY, time_of_day="08:00", enabled=True))
            backend.save_schedule_record(build_schedule_record("s2", "B", "et2", TYPE_DAILY, time_of_day="09:00", enabled=False))
            enabled = backend.list_schedule_records(enabled=True)
            self.assertEqual(len(enabled), 1)
            self.assertEqual(enabled[0]["schedule_id"], "s1")

    def test_update_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            record = build_schedule_record("s1", "OldName", "et", TYPE_DAILY, time_of_day="08:00")
            backend.save_schedule_record(record)
            updated = dict(record)
            updated["name"] = "NewName"
            backend.save_schedule_record(updated)
            loaded = backend.get_schedule_record("s1")
            self.assertEqual(loaded["name"], "NewName")

    def test_save_and_list_schedule_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            run = build_schedule_run_record("s1", "2026-05-21T08:00:00Z", status=RUN_STATUS_ENQUEUED, queue_id="q1")
            backend.save_schedule_run_record(run)
            runs = backend.list_schedule_run_records(schedule_id="s1")
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["schedule_id"], "s1")
            self.assertEqual(runs[0]["status"], RUN_STATUS_ENQUEUED)

    def test_schema_version_is_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            result = backend.verify_schema()
            self.assertEqual(result.get("schema_version"), 3)

    def test_verify_schema_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = self._backend(tmp)
            result = backend.verify_schema()
            self.assertTrue(result["ok"], f"Missing tables/indexes: {result}")
