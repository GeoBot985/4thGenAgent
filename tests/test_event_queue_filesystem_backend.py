"""Spec 137 — Test: durable queue filesystem backend persistence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    cancel_event,
    claim_next_event,
    enqueue_event,
    list_queue,
    mark_event_completed,
    mark_event_failed,
    mark_event_processing,
    queue_health,
    retry_event,
)
from runtime.event_queue_contract import (
    STATUS_CANCELLED,
    STATUS_CLAIMED,
    STATUS_COMPLETED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_PERMANENT,
    STATUS_FAILED_RETRYABLE,
    STATUS_PENDING,
    STATUS_PROCESSING,
    FAILURE_RUNTIME_EXCEPTION,
    FAILURE_ROUTE_NOT_FOUND,
)
from runtime.persistence_backends.filesystem_backend import FilesystemPersistenceBackend


def _make_event(event_id: str = "evt-fs-001", source: str = "operator_ui", event_type: str = "test.check") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"customer_id": "CUST-1"},
    }


class TestFilesystemDurableQueueStorage(unittest.TestCase):

    def test_filesystem_backend_is_used_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            backend = FilesystemPersistenceBackend(rd)
            self.assertEqual(backend.backend_name, "filesystem")

    def test_enqueue_creates_queue_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            self.assertTrue((rd / "queue").is_dir())

    def test_enqueue_creates_jsonl_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            self.assertTrue((rd / "queue" / "durable_queue.jsonl").is_file())

    def test_enqueue_creates_index_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            self.assertTrue((rd / "queue" / "durable_queue_index.json").is_file())

    def test_get_durable_queue_record_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            backend = FilesystemPersistenceBackend(rd)
            result = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = result["queue_id"]
            record = backend.get_durable_queue_record(queue_id)
            self.assertIsNotNone(record)
            self.assertEqual(record["queue_id"], queue_id)

    def test_list_durable_queue_records_returns_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            backend = FilesystemPersistenceBackend(rd)
            enqueue_event(_make_event("evt-a", "op", "t.a"), runtime_data_dir=rd)
            enqueue_event(_make_event("evt-b", "op", "t.b"), runtime_data_dir=rd)
            records = backend.list_durable_queue_records(limit=10)
            self.assertEqual(len(records), 2)

    def test_list_durable_queue_records_filter_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            backend = FilesystemPersistenceBackend(rd)
            enqueue_event(_make_event("evt-a", "op", "t.a"), runtime_data_dir=rd)
            enqueue_event(_make_event("evt-b", "op", "t.b"), runtime_data_dir=rd)
            pending = backend.list_durable_queue_records(limit=10, status=STATUS_PENDING)
            self.assertEqual(len(pending), 2)
            claimed = backend.list_durable_queue_records(limit=10, status=STATUS_CLAIMED)
            self.assertEqual(len(claimed), 0)

    def test_save_updates_existing_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            backend = FilesystemPersistenceBackend(rd)
            result = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = result["queue_id"]

            r = backend.get_durable_queue_record(queue_id)
            self.assertEqual(r["status"], STATUS_PENDING)

            claim_next_event("worker-1", rd)
            r2 = backend.get_durable_queue_record(queue_id)
            self.assertEqual(r2["status"], STATUS_CLAIMED)
            self.assertEqual(r2["claimed_by"], "worker-1")

    def test_queue_lifecycle_filesystem(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)

            enqueue_result = enqueue_event(_make_event(), runtime_data_dir=rd)
            self.assertTrue(enqueue_result["ok"])
            queue_id = enqueue_result["queue_id"]

            claimed = claim_next_event("w1", rd)
            self.assertTrue(claimed["ok"])
            self.assertEqual(claimed["status"], STATUS_CLAIMED)

            mark_event_processing(queue_id, rd)
            mark_event_completed(queue_id, "frame-abc", rd)

            backend = FilesystemPersistenceBackend(rd)
            final = backend.get_durable_queue_record(queue_id)
            self.assertEqual(final["status"], STATUS_COMPLETED)
            self.assertEqual(final["linked_frame_id"], "frame-abc")

    def test_queue_health_returns_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event("e1", "op", "t.x"), runtime_data_dir=rd)
            enqueue_event(_make_event("e2", "op", "t.y"), runtime_data_dir=rd)
            health = queue_health(rd)
            self.assertTrue(health["ok"])
            self.assertEqual(health["pending_count"], 2)
            self.assertEqual(health["backend"], "filesystem")

    def test_list_queue_function_returns_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event("e1", "op", "t.x"), runtime_data_dir=rd)
            result = list_queue(runtime_data_dir=rd)
            self.assertTrue(result["ok"])
            self.assertEqual(result["count"], 1)

    def test_cancel_sets_cancelled_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            cancel_result = cancel_event(r["queue_id"], reason="test", runtime_data_dir=rd)
            self.assertTrue(cancel_result["ok"])
            backend = FilesystemPersistenceBackend(rd)
            rec = backend.get_durable_queue_record(r["queue_id"])
            self.assertEqual(rec["status"], STATUS_CANCELLED)

    def test_retry_requires_failed_retryable_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            retry_result = retry_event(r["queue_id"], runtime_data_dir=rd)
            self.assertFalse(retry_result["ok"])

    def test_mark_failed_retryable_then_retry_resets_to_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)
            mark_event_processing(queue_id, rd)
            mark_event_failed(queue_id, {"message": "timeout", "category": FAILURE_RUNTIME_EXCEPTION}, rd)

            retry_result = retry_event(queue_id, rd)
            self.assertTrue(retry_result["ok"])
            backend = FilesystemPersistenceBackend(rd)
            rec = backend.get_durable_queue_record(queue_id)
            self.assertEqual(rec["status"], STATUS_PENDING)

    def test_max_attempts_moves_to_dead_letter(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd, max_attempts=1)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)
            mark_event_processing(queue_id, rd)
            failed = mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            self.assertEqual(failed["status"], STATUS_DEAD_LETTER)
