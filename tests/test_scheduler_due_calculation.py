"""Spec 138 — Test: scheduler due-time calculation."""
from __future__ import annotations

import datetime
import unittest

from runtime.scheduler_contract import TYPE_DAILY, TYPE_INTERVAL, TYPE_WEEKLY, build_schedule_record
from runtime.scheduler_engine import calculate_next_due, get_missed_windows


_UTC = datetime.timezone.utc


def _dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


class TestIntervalDue(unittest.TestCase):

    def _interval(self, minutes: int) -> dict:
        return build_schedule_record("s1", "T", "et", TYPE_INTERVAL, interval_minutes=minutes)

    def test_next_due_is_after_now(self):
        schedule = self._interval(30)
        after = _dt("2026-05-21T10:00:00Z")
        next_due = calculate_next_due(schedule, after)
        self.assertIsNotNone(next_due)
        self.assertEqual(next_due, _dt("2026-05-21T10:30:00Z"))

    def test_zero_interval_returns_none(self):
        schedule = self._interval(0)
        self.assertIsNone(calculate_next_due(schedule, _dt("2026-05-21T10:00:00Z")))

    def test_missed_windows_count(self):
        schedule = self._interval(60)
        since = _dt("2026-05-21T08:00:00Z")
        until = _dt("2026-05-21T12:00:00Z")
        windows = get_missed_windows(schedule, since, until)
        self.assertEqual(len(windows), 4)

    def test_missed_windows_order(self):
        schedule = self._interval(30)
        since = _dt("2026-05-21T08:00:00Z")
        until = _dt("2026-05-21T10:00:00Z")
        windows = get_missed_windows(schedule, since, until)
        for w in windows:
            self.assertGreater(w, since)
            self.assertLessEqual(w, until)


class TestDailyDue(unittest.TestCase):

    def _daily(self, time_of_day: str) -> dict:
        return build_schedule_record("s1", "T", "et", TYPE_DAILY, time_of_day=time_of_day)

    def test_next_due_same_day_if_time_not_reached(self):
        schedule = self._daily("14:00")
        after = _dt("2026-05-21T10:00:00Z")
        next_due = calculate_next_due(schedule, after)
        self.assertIsNotNone(next_due)
        self.assertEqual(next_due.hour, 14)
        self.assertEqual(next_due.date(), _dt("2026-05-21T00:00:00Z").date())

    def test_next_due_next_day_if_time_passed(self):
        schedule = self._daily("08:00")
        after = _dt("2026-05-21T10:00:00Z")
        next_due = calculate_next_due(schedule, after)
        self.assertIsNotNone(next_due)
        self.assertEqual(next_due.date().day, 22)

    def test_invalid_time_returns_none(self):
        schedule = self._daily("bad-time")
        self.assertIsNone(calculate_next_due(schedule, _dt("2026-05-21T10:00:00Z")))


class TestWeeklyDue(unittest.TestCase):

    def test_next_due_is_correct_weekday(self):
        schedule = build_schedule_record("s1", "T", "et", TYPE_WEEKLY, time_of_day="09:00", day_of_week="monday")
        after = _dt("2026-05-21T10:00:00Z")  # 2026-05-21 is a Thursday
        next_due = calculate_next_due(schedule, after)
        self.assertIsNotNone(next_due)
        self.assertEqual(next_due.weekday(), 0)  # Monday

    def test_invalid_day_returns_none(self):
        schedule = build_schedule_record("s1", "T", "et", TYPE_WEEKLY, time_of_day="09:00", day_of_week="badday")
        self.assertIsNone(calculate_next_due(schedule, _dt("2026-05-21T10:00:00Z")))


class TestGetMissedWindows(unittest.TestCase):

    def test_no_missed_when_since_equals_until(self):
        schedule = build_schedule_record("s1", "T", "et", TYPE_INTERVAL, interval_minutes=30)
        t = _dt("2026-05-21T10:00:00Z")
        windows = get_missed_windows(schedule, t, t)
        self.assertEqual(len(windows), 0)

    def test_returns_sorted_asc(self):
        schedule = build_schedule_record("s1", "T", "et", TYPE_INTERVAL, interval_minutes=10)
        since = _dt("2026-05-21T10:00:00Z")
        until = _dt("2026-05-21T10:40:00Z")
        windows = get_missed_windows(schedule, since, until)
        self.assertEqual(windows, sorted(windows))
