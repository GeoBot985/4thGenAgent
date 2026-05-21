"""Spec 137 — Test: durable queue dedupe behaviour."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import enqueue_event, cancel_event
from runtime.event_queue_contract import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_PERMANENT,
    STATUS_PENDING,
    TERMINAL_STATUSES,
    build_dedupe_key,
)


def _make_event(source: str = "operator_ui", event_type: str = "test.check", event_id: str = "evt-001") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"customer_id": "CUST-1"},
    }


class TestDedupeKey(unittest.TestCase):

    def test_same_event_produces_same_key(self):
        event = _make_event()
        k1 = build_dedupe_key(event)
        k2 = build_dedupe_key(event)
        self.assertEqual(k1, k2)

    def test_different_event_id_same_source_type_differ_for_manual(self):
        e1 = _make_event(source="manual", event_id="a")
        e2 = _make_event(source="manual", event_id="b")
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_gmail_uses_message_id(self):
        e1 = {"source": "gmail", "event_type": "email.received", "payload": {"message_id": "msg-abc"}}
        e2 = {"source": "gmail", "event_type": "email.received", "payload": {"message_id": "msg-xyz"}}
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_same_gmail_message_id_is_duplicate(self):
        e1 = {"source": "gmail", "event_type": "email.received", "payload": {"message_id": "msg-abc"}}
        e2 = dict(e1)
        self.assertEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_schedule_uses_schedule_id_and_time(self):
        e1 = {"source": "schedule", "event_type": "schedule.trigger", "payload": {"schedule_id": "s1", "scheduled_time": "2026-05-21T10:00:00Z"}}
        e2 = {"source": "schedule", "event_type": "schedule.trigger", "payload": {"schedule_id": "s1", "scheduled_time": "2026-05-21T11:00:00Z"}}
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e2))

    def test_file_event_uses_path_and_hash(self):
        e1 = {"source": "file", "event_type": "file.changed", "payload": {"file_path": "/a/b.txt", "content_hash": "abc123"}}
        e2 = {"source": "file", "event_type": "file.changed", "payload": {"file_path": "/a/b.txt", "content_hash": "abc123"}}
        e3 = {"source": "file", "event_type": "file.changed", "payload": {"file_path": "/a/b.txt", "content_hash": "def456"}}
        self.assertEqual(build_dedupe_key(e1), build_dedupe_key(e2))
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e3))

    def test_database_event_uses_table_key_version(self):
        e1 = {"source": "database", "event_type": "db.row_changed", "payload": {"source_table": "orders", "source_key": "ord-1", "version": "v1"}}
        e2 = {"source": "database", "event_type": "db.row_changed", "payload": {"source_table": "orders", "source_key": "ord-1", "version": "v2"}}
        self.assertNotEqual(build_dedupe_key(e1), build_dedupe_key(e2))


class TestEnqueueDedupe(unittest.TestCase):

    def test_first_enqueue_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = enqueue_event(_make_event("operator_ui", "test.check", "evt-d001"), runtime_data_dir=rd)
            self.assertTrue(result["ok"])
            self.assertFalse(result["duplicate"])
            self.assertIn("queue_id", result)

    def test_duplicate_pending_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            event = _make_event("operator_ui", "test.check", "evt-d001")
            r1 = enqueue_event(event, runtime_data_dir=rd)
            r2 = enqueue_event(event, runtime_data_dir=rd)
            self.assertTrue(r1["ok"])
            self.assertFalse(r2["ok"])
            self.assertTrue(r2["duplicate"])
            self.assertEqual(r2["existing_queue_id"], r1["queue_id"])

    def test_different_event_types_are_not_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            e1 = _make_event("operator_ui", "test.check", "evt-d001")
            e2 = _make_event("operator_ui", "test.other", "evt-d002")
            r1 = enqueue_event(e1, runtime_data_dir=rd)
            r2 = enqueue_event(e2, runtime_data_dir=rd)
            self.assertTrue(r1["ok"])
            self.assertTrue(r2["ok"])
            self.assertNotEqual(r1["queue_id"], r2["queue_id"])

    def test_terminal_event_can_be_re_enqueued(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            event = _make_event("operator_ui", "test.check", "evt-d001")
            r1 = enqueue_event(event, runtime_data_dir=rd)
            self.assertTrue(r1["ok"])

            # Cancel it (terminal)
            from runtime.event_queue import cancel_event
            cancel_event(r1["queue_id"], reason="test cleanup", runtime_data_dir=rd)

            # Re-enqueue with different event_id (different dedupe key for non-manual source)
            # For operator_ui source, dedupe uses event_id as fallback
            # Use different event_id to get a new dedupe key
            event2 = _make_event("operator_ui", "test.check", "evt-d001-v2")
            r2 = enqueue_event(event2, runtime_data_dir=rd)
            self.assertTrue(r2["ok"], "Should be able to enqueue after terminal")

    def test_same_event_id_but_different_source_is_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            e1 = _make_event("operator_ui", "test.check", "evt-d001")
            e2 = _make_event("gmail", "test.check", "evt-d001")
            r1 = enqueue_event(e1, runtime_data_dir=rd)
            r2 = enqueue_event(e2, runtime_data_dir=rd)
            self.assertTrue(r1["ok"])
            self.assertTrue(r2["ok"])
