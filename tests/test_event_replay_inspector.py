"""Spec 108 — Event Replay Inspector tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    STATUS_REPLAY_FAILED,
    STATUS_REPLAYED_DRY_RUN,
    build_queue_record,
    load_queue_record,
    replay_event_dry_run,
    write_queue_record,
)
from runtime.event_store import intake_event


def _make_event(event_id: str = "evt-r-001", source: str = "external", event_type: str = "stub") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"message": "replay-test"},
        "received_at": "2026-05-17T00:00:00Z",
    }


class TestReplayEventDryRun(unittest.TestCase):

    def test_replay_event_dry_run_creates_new_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            # First, ingest the event to create a queue record
            intake_event(_make_event("evt-r-create"), runtime_data_dir=rd)
            result = replay_event_dry_run("evt-r-create", runtime_data_dir=rd)
            # Replay should create a new frame
            self.assertIn("replay_frame_id", result)
            if result.get("ok"):
                self.assertIsNotNone(result.get("replay_frame_id"))

    def test_replay_event_dry_run_does_not_mutate_original_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            original_ev = _make_event("evt-r-nomut")
            intake_event(original_ev, runtime_data_dir=rd)
            original_record = load_queue_record("evt-r-nomut", rd)
            original_payload = dict(original_record.get("payload") or {})

            replay_event_dry_run("evt-r-nomut", runtime_data_dir=rd)

            # Original queue record should not have mutated payload
            after_record = load_queue_record("evt-r-nomut", rd)
            self.assertEqual(after_record.get("payload"), original_payload)

    def test_replay_event_records_replay_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-r-hist"), runtime_data_dir=rd)
            replay_event_dry_run("evt-r-hist", runtime_data_dir=rd, replayed_by="tester", reason="test replay")

            updated = load_queue_record("evt-r-hist", rd)
            self.assertIsNotNone(updated)
            history = updated.get("metadata", {}).get("replay_history") or []
            self.assertGreater(len(history), 0)
            last = history[-1]
            self.assertEqual(last.get("replayed_by"), "tester")
            self.assertEqual(last.get("reason"), "test replay")
            self.assertIn(last.get("status"), {STATUS_REPLAYED_DRY_RUN, STATUS_REPLAY_FAILED})

    def test_replay_unknown_event_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = replay_event_dry_run("evt-does-not-exist-xyz", runtime_data_dir=rd)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], STATUS_REPLAY_FAILED)
            self.assertIsNone(result.get("replay_frame_id"))
            self.assertTrue(len(result.get("errors", [])) > 0)

    def test_replay_increments_attempt_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-r-count"), runtime_data_dir=rd)
            before = load_queue_record("evt-r-count", rd)
            before_count = int(before.get("attempt_count", 0) or 0)
            replay_event_dry_run("evt-r-count", runtime_data_dir=rd)
            after = load_queue_record("evt-r-count", rd)
            after_count = int(after.get("attempt_count", 0) or 0)
            self.assertGreater(after_count, before_count)

    def test_replay_always_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            # Replay result must always be dry-run — never live
            intake_event(_make_event("evt-r-dryrun"), runtime_data_dir=rd)
            result = replay_event_dry_run("evt-r-dryrun", runtime_data_dir=rd)
            # The function signature only supports dry_run; verify no live frame state
            self.assertIn(result.get("status"), {STATUS_REPLAYED_DRY_RUN, STATUS_REPLAY_FAILED})
            # replay_frame_id should not be the same as original_frame_id (new frame)
            if result.get("ok") and result.get("replay_frame_id") and result.get("original_frame_id"):
                self.assertNotEqual(result["replay_frame_id"], result["original_frame_id"])


class TestEventQueueRecordShape(unittest.TestCase):

    def test_queue_record_has_all_canonical_fields(self):
        ev = _make_event("evt-r-shape")
        record = build_queue_record(ev)
        required = {
            "event_id", "source", "event_type", "payload", "received_at",
            "status", "duplicate", "duplicate_of_event_id",
            "route_id", "manifest_id", "linked_frame_id",
            "attempt_count", "last_attempted_at", "last_replay_frame_id",
            "failure_reason", "failure_code", "errors",
            "dry_run", "created_at", "updated_at", "metadata",
        }
        for key in required:
            self.assertIn(key, record, f"Queue record missing field: {key}")

    def test_queue_record_fingerprint_in_metadata(self):
        ev = _make_event("evt-r-fp")
        record = build_queue_record(ev)
        self.assertIn("fingerprint", record.get("metadata", {}))


if __name__ == "__main__":
    unittest.main()
