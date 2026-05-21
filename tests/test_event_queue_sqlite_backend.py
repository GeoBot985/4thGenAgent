"""Spec 137 — Test: durable queue SQLite backend persistence."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    claim_next_event,
    enqueue_event,
    list_queue,
    mark_event_completed,
    mark_event_failed,
    mark_event_processing,
    queue_health,
)
from runtime.event_queue_contract import (
    STATUS_CLAIMED,
    STATUS_COMPLETED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_RETRYABLE,
    STATUS_PENDING,
    FAILURE_RUNTIME_EXCEPTION,
)


def _make_event(event_id: str = "evt-sq-001", source: str = "operator_ui", event_type: str = "test.check") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"order_id": "ORD-1"},
    }


class TestSQLiteDurableQueueStorage(unittest.TestCase):

    def _sqlite_env(self, tmp: str) -> tuple[Path, dict[str, str]]:
        rd = Path(tmp) / "runtime_data"
        rd.mkdir(parents=True, exist_ok=True)
        db_path = rd / "taskframe_runtime.db"
        env_overrides = {
            "TASKFRAME_PERSISTENCE_BACKEND": "sqlite",
            "TASKFRAME_SQLITE_DB_PATH": str(db_path),
        }
        return rd, env_overrides

    def _set_env(self, overrides: dict[str, str]) -> dict[str, str | None]:
        saved = {}
        for key, val in overrides.items():
            saved[key] = os.environ.get(key)
            os.environ[key] = val
        return saved

    def _restore_env(self, saved: dict[str, str | None]) -> None:
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_sqlite_backend_enqueue_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                result = enqueue_event(_make_event(), runtime_data_dir=rd)
                self.assertTrue(result["ok"])
                queue_id = result["queue_id"]

                from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend
                backend = SQLitePersistenceBackend(rd / "taskframe_runtime.db")
                record = backend.get_durable_queue_record(queue_id)
                self.assertIsNotNone(record)
                self.assertEqual(record["queue_id"], queue_id)
                self.assertEqual(record["status"], STATUS_PENDING)
            finally:
                self._restore_env(saved)

    def test_sqlite_backend_state_survives_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                result = enqueue_event(_make_event(), runtime_data_dir=rd)
                queue_id = result["queue_id"]
                claim_next_event("worker-1", rd)
                mark_event_processing(queue_id, rd)
                mark_event_completed(queue_id, "frame-xyz", rd)

                from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend
                backend = SQLitePersistenceBackend(rd / "taskframe_runtime.db")
                record = backend.get_durable_queue_record(queue_id)
                self.assertEqual(record["status"], STATUS_COMPLETED)
                self.assertEqual(record["linked_frame_id"], "frame-xyz")
            finally:
                self._restore_env(saved)

    def test_sqlite_list_durable_records_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                enqueue_event(_make_event("e1", "op", "t.a"), runtime_data_dir=rd)
                enqueue_event(_make_event("e2", "op", "t.b"), runtime_data_dir=rd)
                enqueue_event(_make_event("e3", "op", "t.c"), runtime_data_dir=rd)

                from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend
                backend = SQLitePersistenceBackend(rd / "taskframe_runtime.db")
                all_pending = backend.list_durable_queue_records(limit=10, status=STATUS_PENDING)
                self.assertEqual(len(all_pending), 3)
            finally:
                self._restore_env(saved)

    def test_sqlite_dedupe_blocks_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                event = _make_event()
                r1 = enqueue_event(event, runtime_data_dir=rd)
                r2 = enqueue_event(event, runtime_data_dir=rd)
                self.assertTrue(r1["ok"])
                self.assertFalse(r2["ok"])
                self.assertTrue(r2["duplicate"])
            finally:
                self._restore_env(saved)

    def test_sqlite_claim_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                result = enqueue_event(_make_event(), runtime_data_dir=rd)
                queue_id = result["queue_id"]
                claimed = claim_next_event("w1", rd)
                self.assertTrue(claimed["ok"])

                from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend
                backend = SQLitePersistenceBackend(rd / "taskframe_runtime.db")
                record = backend.get_durable_queue_record(queue_id)
                self.assertEqual(record["status"], STATUS_CLAIMED)
                self.assertEqual(record["claimed_by"], "w1")
            finally:
                self._restore_env(saved)

    def test_sqlite_queue_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                enqueue_event(_make_event("e1"), runtime_data_dir=rd)
                enqueue_event(_make_event("e2"), runtime_data_dir=rd)
                health = queue_health(rd)
                self.assertTrue(health["ok"])
                self.assertEqual(health["pending_count"], 2)
                self.assertEqual(health["backend"], "sqlite")
            finally:
                self._restore_env(saved)

    def test_sqlite_schema_version_is_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                enqueue_event(_make_event(), runtime_data_dir=rd)
                from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend, SCHEMA_VERSION
                backend = SQLitePersistenceBackend(rd / "taskframe_runtime.db")
                result = backend.verify_schema()
                self.assertEqual(result["schema_version"], SCHEMA_VERSION)
                self.assertNotIn("durable_event_queue", result.get("missing_tables", []))
            finally:
                self._restore_env(saved)

    def test_sqlite_mark_failed_dead_letter_at_max_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd, env = self._sqlite_env(tmp)
            saved = self._set_env(env)
            try:
                result = enqueue_event(_make_event(), runtime_data_dir=rd, max_attempts=1)
                queue_id = result["queue_id"]
                claim_next_event("w1", rd)
                mark_event_processing(queue_id, rd)
                failed = mark_event_failed(queue_id, {"message": "err", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
                self.assertEqual(failed["status"], STATUS_DEAD_LETTER)

                from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend
                backend = SQLitePersistenceBackend(rd / "taskframe_runtime.db")
                record = backend.get_durable_queue_record(queue_id)
                self.assertEqual(record["status"], STATUS_DEAD_LETTER)
            finally:
                self._restore_env(saved)
