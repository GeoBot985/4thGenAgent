"""Spec 138 — Test: scheduler contract constants, builders, validation."""
from __future__ import annotations

import unittest

from runtime.scheduler_contract import (
    DAYS_OF_WEEK,
    MISFIRE_ENQUEUE_ALL,
    MISFIRE_ENQUEUE_LATEST,
    MISFIRE_SKIP,
    RUN_STATUS_DUPLICATE,
    RUN_STATUS_ENQUEUED,
    RUN_STATUS_FAILED,
    RUN_STATUS_SKIPPED,
    TYPE_DAILY,
    TYPE_INTERVAL,
    TYPE_WEEKLY,
    VALID_MISFIRE_MODES,
    VALID_SCHEDULE_TYPES,
    build_schedule_record,
    build_schedule_run_record,
    build_scheduled_event,
    validate_schedule,
)


class TestConstants(unittest.TestCase):

    def test_schedule_types(self):
        self.assertIn(TYPE_DAILY, VALID_SCHEDULE_TYPES)
        self.assertIn(TYPE_INTERVAL, VALID_SCHEDULE_TYPES)
        self.assertIn(TYPE_WEEKLY, VALID_SCHEDULE_TYPES)

    def test_misfire_modes(self):
        self.assertIn(MISFIRE_SKIP, VALID_MISFIRE_MODES)
        self.assertIn(MISFIRE_ENQUEUE_LATEST, VALID_MISFIRE_MODES)
        self.assertIn(MISFIRE_ENQUEUE_ALL, VALID_MISFIRE_MODES)

    def test_run_statuses(self):
        for s in (RUN_STATUS_ENQUEUED, RUN_STATUS_SKIPPED, RUN_STATUS_FAILED, RUN_STATUS_DUPLICATE):
            self.assertIsInstance(s, str)
            self.assertTrue(s)

    def test_days_of_week(self):
        self.assertIn("monday", DAYS_OF_WEEK)
        self.assertIn("sunday", DAYS_OF_WEEK)
        self.assertEqual(len(DAYS_OF_WEEK), 7)


class TestBuildScheduleRecord(unittest.TestCase):

    def _daily(self, **kwargs):
        return build_schedule_record(
            "sched-001", "Test Schedule", "daily.check", TYPE_DAILY,
            time_of_day="08:00", **kwargs
        )

    def test_required_fields_present(self):
        record = self._daily()
        for field in ("schedule_id", "name", "event_type", "schedule_type", "enabled",
                      "misfire_mode", "timezone", "time_of_day", "interval_minutes",
                      "day_of_week", "payload_template", "max_catchup_windows", "priority",
                      "tags", "last_scheduled_for", "last_run_at", "last_run_status",
                      "created_at", "updated_at"):
            self.assertIn(field, record, f"Missing: {field}")

    def test_defaults(self):
        record = self._daily()
        self.assertTrue(record["enabled"])
        self.assertEqual(record["misfire_mode"], MISFIRE_SKIP)
        self.assertEqual(record["timezone"], "UTC")
        self.assertEqual(record["priority"], 100)
        self.assertEqual(record["max_catchup_windows"], 3)
        self.assertEqual(record["payload_template"], {})
        self.assertEqual(record["tags"], [])

    def test_custom_values(self):
        record = build_schedule_record(
            "s1", "name", "et", TYPE_INTERVAL,
            interval_minutes=30, priority=50, misfire_mode=MISFIRE_ENQUEUE_ALL,
            tags=["a", "b"],
        )
        self.assertEqual(record["interval_minutes"], 30)
        self.assertEqual(record["priority"], 50)
        self.assertEqual(record["misfire_mode"], MISFIRE_ENQUEUE_ALL)
        self.assertEqual(record["tags"], ["a", "b"])


class TestValidateSchedule(unittest.TestCase):

    def _make_daily(self, **overrides):
        base = build_schedule_record("s1", "Test", "et", TYPE_DAILY, time_of_day="09:00")
        base.update(overrides)
        return base

    def test_valid_daily(self):
        ok, errors = validate_schedule(self._make_daily())
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_missing_schedule_id(self):
        record = self._make_daily(schedule_id="")
        ok, errors = validate_schedule(record)
        self.assertFalse(ok)
        self.assertTrue(any("schedule_id" in e for e in errors))

    def test_invalid_schedule_type(self):
        record = self._make_daily(schedule_type="bogus")
        ok, errors = validate_schedule(record)
        self.assertFalse(ok)

    def test_invalid_misfire_mode(self):
        record = self._make_daily(misfire_mode="invalid")
        ok, errors = validate_schedule(record)
        self.assertFalse(ok)

    def test_daily_bad_time(self):
        record = self._make_daily(time_of_day="bad-time")
        ok, errors = validate_schedule(record)
        self.assertFalse(ok)

    def test_interval_zero_minutes(self):
        record = build_schedule_record("s1", "Test", "et", TYPE_INTERVAL, interval_minutes=0)
        ok, errors = validate_schedule(record)
        self.assertFalse(ok)

    def test_interval_positive_minutes_valid(self):
        record = build_schedule_record("s1", "Test", "et", TYPE_INTERVAL, interval_minutes=15)
        ok, errors = validate_schedule(record)
        self.assertTrue(ok)

    def test_weekly_requires_day_of_week(self):
        record = build_schedule_record("s1", "Test", "et", TYPE_WEEKLY, time_of_day="09:00", day_of_week="")
        ok, errors = validate_schedule(record)
        self.assertFalse(ok)

    def test_weekly_valid(self):
        record = build_schedule_record("s1", "Test", "et", TYPE_WEEKLY, time_of_day="09:00", day_of_week="monday")
        ok, errors = validate_schedule(record)
        self.assertTrue(ok)


class TestBuildScheduledEvent(unittest.TestCase):

    def test_event_has_required_fields(self):
        schedule = build_schedule_record("sched-1", "Test", "daily.check", TYPE_DAILY, time_of_day="08:00")
        event = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        self.assertEqual(event["source"], "schedule")
        self.assertEqual(event["event_type"], "daily.check")
        self.assertIn("event_id", event)
        self.assertIn("payload", event)

    def test_event_id_format(self):
        schedule = build_schedule_record("sched-1", "Test", "daily.check", TYPE_DAILY, time_of_day="08:00")
        event = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        self.assertTrue(event["event_id"].startswith("evt_sched_sched-1_"))

    def test_payload_contains_schedule_id_and_scheduled_for(self):
        schedule = build_schedule_record("s1", "Test", "et", TYPE_DAILY, time_of_day="08:00",
                                         payload_template={"foo": "bar"})
        event = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        self.assertEqual(event["payload"]["schedule_id"], "s1")
        self.assertEqual(event["payload"]["scheduled_for"], "2026-05-21T08:00:00Z")
        self.assertEqual(event["payload"]["foo"], "bar")


class TestBuildScheduleRunRecord(unittest.TestCase):

    def test_required_fields(self):
        run = build_schedule_run_record("s1", "2026-05-21T08:00:00Z", status=RUN_STATUS_ENQUEUED, queue_id="q1")
        for field in ("run_id", "schedule_id", "scheduled_for", "status", "queue_id", "failure_reason", "created_at"):
            self.assertIn(field, run)

    def test_values(self):
        run = build_schedule_run_record("s1", "2026-05-21T08:00:00Z", status=RUN_STATUS_FAILED, failure_reason="err")
        self.assertEqual(run["schedule_id"], "s1")
        self.assertEqual(run["status"], RUN_STATUS_FAILED)
        self.assertEqual(run["failure_reason"], "err")
