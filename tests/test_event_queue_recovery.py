"""Spec 137 — Test: stale queue item recovery."""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    claim_next_event,
    enqueue_event,
    mark_event_processing,
    recover_stale_queue_items,
)
from runtime.event_queue_contract import (
    STATUS_CLAIMED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_RETRYABLE,
    STATUS_PENDING,
    STATUS_PROCESSING,
    update_durable_queue_record,
    build_durable_queue_record,
)
from runtime.persistence_backends.filesystem_backend import FilesystemPersistenceBackend


def _make_event(event_id: str = "evt-rec-001") -> dict:
    return {
        "event_id": event_id,
        "source": "operator_ui",
        "event_type": "test.stale",
        "payload": {"x": 1},
    }


def _back_date_record(backend: FilesystemPersistenceBackend, queue_id: str, minutes_ago: int) -> None:
    """Forcibly set updated_at to minutes_ago in the past for testing stale detection."""
    record = backend.get_durable_queue_record(queue_id)
    if record is None:
        return
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    past_str = past.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    record["updated_at"] = past_str
    backend.save_durable_queue_record(record)


class TestRecoverStaleQueueItems(unittest.TestCase):

    def test_no_stale_items_returns_zero_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            result = recover_stale_queue_items(rd, stale_timeout_minutes=15)
            self.assertTrue(result["ok"])
            self.assertEqual(result["recovered_count"], 0)

    def test_stale_claimed_item_is_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)

            backend = FilesystemPersistenceBackend(rd)
            _back_date_record(backend, queue_id, minutes_ago=20)

            result = recover_stale_queue_items(rd, stale_timeout_minutes=15)
            self.assertTrue(result["ok"])
            self.assertEqual(result["recovered_count"], 1)
            recovered = result["recovered"]
            self.assertEqual(recovered[0]["queue_id"], queue_id)
            self.assertEqual(recovered[0]["old_status"], STATUS_CLAIMED)

    def test_stale_processing_item_is_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)
            mark_event_processing(queue_id, rd)

            backend = FilesystemPersistenceBackend(rd)
            _back_date_record(backend, queue_id, minutes_ago=20)

            result = recover_stale_queue_items(rd, stale_timeout_minutes=15)
            self.assertEqual(result["recovered_count"], 1)
            self.assertEqual(result["recovered"][0]["old_status"], STATUS_PROCESSING)

    def test_stale_recovery_produces_failed_retryable_when_below_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd, max_attempts=3)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)

            backend = FilesystemPersistenceBackend(rd)
            _back_date_record(backend, queue_id, minutes_ago=30)

            recover_stale_queue_items(rd, stale_timeout_minutes=15)
            rec = backend.get_durable_queue_record(queue_id)
            self.assertEqual(rec["status"], STATUS_FAILED_RETRYABLE)

    def test_stale_recovery_produces_dead_letter_at_max_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd, max_attempts=1)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)

            backend = FilesystemPersistenceBackend(rd)
            record = backend.get_durable_queue_record(queue_id)
            record["attempt_count"] = 1
            backend.save_durable_queue_record(record)
            _back_date_record(backend, queue_id, minutes_ago=30)

            recover_stale_queue_items(rd, stale_timeout_minutes=15)
            rec = backend.get_durable_queue_record(queue_id)
            self.assertEqual(rec["status"], STATUS_DEAD_LETTER)

    def test_non_stale_items_are_not_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)

            result = recover_stale_queue_items(rd, stale_timeout_minutes=15)
            self.assertEqual(result["recovered_count"], 0)

            backend = FilesystemPersistenceBackend(rd)
            rec = backend.get_durable_queue_record(queue_id)
            self.assertEqual(rec["status"], STATUS_CLAIMED)

    def test_recovery_records_reason_in_last_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)

            backend = FilesystemPersistenceBackend(rd)
            _back_date_record(backend, queue_id, minutes_ago=20)

            recover_stale_queue_items(rd, stale_timeout_minutes=15)
            rec = backend.get_durable_queue_record(queue_id)
            self.assertIn("timeout", str(rec.get("last_error", "")).lower())

    def test_pending_items_are_not_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            result = recover_stale_queue_items(rd, stale_timeout_minutes=0)
            self.assertEqual(result["recovered_count"], 0)

    def test_duplicate_recovery_does_not_create_new_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)

            backend = FilesystemPersistenceBackend(rd)
            _back_date_record(backend, queue_id, minutes_ago=20)

            recover_stale_queue_items(rd, stale_timeout_minutes=15)
            recover_stale_queue_items(rd, stale_timeout_minutes=15)

            all_records = backend.list_durable_queue_records(limit=100)
            self.assertEqual(len(all_records), 1)
