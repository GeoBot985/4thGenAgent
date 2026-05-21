"""Spec 138 — Test: scheduler misfire policy behaviour."""
from __future__ import annotations

import datetime
import unittest

from runtime.scheduler_contract import (
    MISFIRE_ENQUEUE_ALL,
    MISFIRE_ENQUEUE_LATEST,
    MISFIRE_SKIP,
    TYPE_INTERVAL,
    build_schedule_record,
)
from runtime.scheduler_engine import find_due_schedules, get_missed_windows


_UTC = datetime.timezone.utc


def _dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


class TestMisfireSkip(unittest.TestCase):

    def test_skip_only_fires_latest(self):
        """MISFIRE_SKIP: find_due_schedules returns all missed windows; engine fires only latest."""
        schedule = build_schedule_record(
            "s1", "T", "et", TYPE_INTERVAL, interval_minutes=30,
            misfire_mode=MISFIRE_SKIP, enabled=True,
        )
        since = _dt("2026-05-21T08:00:00Z")
        until = _dt("2026-05-21T10:00:00Z")
        windows = get_missed_windows(schedule, since, until)
        self.assertGreater(len(windows), 1)

    def test_enqueue_all_fires_all_within_max_catchup(self):
        schedule = build_schedule_record(
            "s1", "T", "et", TYPE_INTERVAL, interval_minutes=30,
            misfire_mode=MISFIRE_ENQUEUE_ALL, max_catchup_windows=3, enabled=True,
        )
        since = _dt("2026-05-21T08:00:00Z")
        until = _dt("2026-05-21T10:00:00Z")
        windows = get_missed_windows(schedule, since, until)
        self.assertGreater(len(windows), 0)

    def test_enqueue_latest_has_windows(self):
        schedule = build_schedule_record(
            "s1", "T", "et", TYPE_INTERVAL, interval_minutes=30,
            misfire_mode=MISFIRE_ENQUEUE_LATEST, enabled=True,
        )
        since = _dt("2026-05-21T08:00:00Z")
        until = _dt("2026-05-21T10:00:00Z")
        windows = get_missed_windows(schedule, since, until)
        self.assertEqual(len(windows), 4)


class TestFindDueSchedules(unittest.TestCase):

    def test_disabled_schedule_not_in_due_list(self):
        schedule = build_schedule_record(
            "s1", "T", "et", TYPE_INTERVAL, interval_minutes=5, enabled=False
        )
        now = _dt("2026-05-21T10:00:00Z")
        due = find_due_schedules([schedule], now=now)
        self.assertEqual(due, [])

    def test_enabled_overdue_schedule_in_due_list(self):
        schedule = build_schedule_record(
            "s1", "T", "et", TYPE_INTERVAL, interval_minutes=5, enabled=True
        )
        schedule["last_scheduled_for"] = "2026-05-21T09:00:00Z"
        now = _dt("2026-05-21T10:00:00Z")
        due = find_due_schedules([schedule], now=now)
        self.assertEqual(len(due), 1)
        _, windows = due[0]
        self.assertGreater(len(windows), 0)

    def test_up_to_date_schedule_not_due(self):
        schedule = build_schedule_record(
            "s1", "T", "et", TYPE_INTERVAL, interval_minutes=60, enabled=True
        )
        now = _dt("2026-05-21T10:00:00Z")
        schedule["last_scheduled_for"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        due = find_due_schedules([schedule], now=now)
        self.assertEqual(due, [])
