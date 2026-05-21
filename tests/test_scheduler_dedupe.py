"""Spec 138 — Test: scheduler event deduplication via event_queue dedupe key."""
from __future__ import annotations

import unittest

from runtime.event_queue_contract import build_dedupe_key
from runtime.scheduler_contract import build_scheduled_event, build_schedule_record, TYPE_DAILY


class TestSchedulerDedupeKey(unittest.TestCase):

    def _schedule(self, schedule_id="sched-1"):
        return build_schedule_record(schedule_id, "Test", "daily.check", TYPE_DAILY, time_of_day="08:00")

    def test_same_schedule_and_time_produces_same_key(self):
        schedule = self._schedule()
        e1 = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        e2 = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        self.assertEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_different_scheduled_for_produces_different_key(self):
        schedule = self._schedule()
        e1 = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        e2 = build_scheduled_event(schedule, "2026-05-22T08:00:00Z")
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_different_schedule_id_produces_different_key(self):
        s1 = self._schedule("sched-1")
        s2 = self._schedule("sched-2")
        e1 = build_scheduled_event(s1, "2026-05-21T08:00:00Z")
        e2 = build_scheduled_event(s2, "2026-05-21T08:00:00Z")
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_event_id_format_includes_schedule_id_and_time(self):
        schedule = self._schedule("my-sched")
        event = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        self.assertIn("my-sched", event["event_id"])
        self.assertIn("20260521", event["event_id"])

    def test_dedupe_key_uses_scheduled_for_not_scheduled_time(self):
        """Spec 138 events use scheduled_for; ensure the dedupe key picks it up."""
        schedule = self._schedule()
        event = build_scheduled_event(schedule, "2026-05-21T08:00:00Z")
        # payload should have scheduled_for, not scheduled_time
        self.assertIn("scheduled_for", event["payload"])
        self.assertNotIn("scheduled_time", event["payload"])
        # dedupe key should be non-empty and deterministic
        key = build_dedupe_key(event)
        self.assertTrue(key)
        self.assertEqual(key, build_dedupe_key(event))
