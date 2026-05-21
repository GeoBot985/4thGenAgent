"""Spec 138 — Test: taskframe schedule CLI subcommands."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from src.taskframe_cli import main
from runtime.scheduler_store import create_schedule
from runtime.scheduler_contract import TYPE_DAILY, TYPE_INTERVAL
from pathlib import Path


def _run(*args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = main(list(args))
        except SystemExit as exc:
            rc = int(exc.code) if exc.code is not None else 0
    return rc, buf.getvalue()


class TestScheduleStatusCommand(unittest.TestCase):

    def test_status_no_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _run("schedule", "status", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertTrue(data["ok"])
            self.assertEqual(data["total_schedules"], 0)

    def test_status_with_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "Daily Test", "et", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            rc, out = _run("schedule", "status", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertEqual(data["total_schedules"], 1)


class TestScheduleListCommand(unittest.TestCase):

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _run("schedule", "list", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertEqual(data["count"], 0)

    def test_list_with_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et1", TYPE_DAILY, time_of_day="08:00", runtime_data_dir=tmp)
            create_schedule("s2", "B", "et2", TYPE_INTERVAL, interval_minutes=30, runtime_data_dir=tmp)
            rc, out = _run("schedule", "list", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertEqual(data["count"], 2)


class TestScheduleEnableDisable(unittest.TestCase):

    def test_enable_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", enabled=False, runtime_data_dir=tmp)
            rc, out = _run("schedule", "enable", "s1", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertTrue(data["ok"])

    def test_disable_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_schedule("s1", "A", "et", TYPE_DAILY, time_of_day="08:00", enabled=True, runtime_data_dir=tmp)
            rc, out = _run("schedule", "disable", "s1", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertTrue(data["ok"])

    def test_enable_missing_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _run("schedule", "enable", "ghost", "--runtime-data-dir", tmp, "--json")
            self.assertNotEqual(rc, 0)


class TestScheduleTickCommand(unittest.TestCase):

    def test_tick_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _run("schedule", "tick", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertTrue(data["ok"])
            self.assertTrue(data.get("dry_run"))


class TestScheduleLoadFixture(unittest.TestCase):

    def test_load_fixture(self):
        fixture = str(Path(__file__).parents[1] / "runtime_data" / "fixtures" / "schedules" / "daily_low_stock_check.json")
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _run("schedule", "load-fixture", fixture, "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertTrue(data["ok"])
            self.assertEqual(data["schedule_id"], "daily.low_stock_check")


class TestScheduleRunsCommand(unittest.TestCase):

    def test_runs_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _run("schedule", "runs", "--runtime-data-dir", tmp, "--json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertEqual(data["count"], 0)
