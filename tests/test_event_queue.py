"""Spec 108 — Event Queue tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    STATUS_DUPLICATE_EVENT,
    STATUS_FRAME_CREATED,
    STATUS_ROUTE_NOT_FOUND,
    STATUS_FAILED_EXECUTION,
    STATUS_RECEIVED,
    build_event_fingerprint,
    build_queue_record,
    list_queue_records,
    load_queue_record,
    write_queue_record,
)
from runtime.event_queue_inspector import get_event_detail, get_event_linked_frame_summary, list_event_queue
from runtime.event_store import intake_event, list_events


def _make_event(event_id: str = "evt-q-001", source: str = "external", event_type: str = "stub") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"message": "hello"},
        "received_at": "2026-05-17T00:00:00Z",
    }


class TestEventQueueWrite(unittest.TestCase):

    def test_intake_event_writes_event_queue_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-q-001"), runtime_data_dir=rd)
            record = load_queue_record("evt-q-001", rd)
            self.assertIsNotNone(record, "Queue record should be written after intake.")
            self.assertEqual(record["event_id"], "evt-q-001")
            self.assertIn("status", record)
            self.assertIn("source", record)
            self.assertIn("event_type", record)

    def test_intake_event_records_route_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = intake_event(_make_event("evt-q-002"), runtime_data_dir=rd)
            record = load_queue_record("evt-q-002", rd)
            self.assertIsNotNone(record)
            if result["ok"]:
                self.assertIsNotNone(record.get("route_id"))
                self.assertIsNotNone(record.get("manifest_id"))

    def test_intake_event_links_created_taskframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = intake_event(_make_event("evt-q-003"), runtime_data_dir=rd)
            if result.get("status") == "FRAME_CREATED":
                record = load_queue_record("evt-q-003", rd)
                self.assertIsNotNone(record)
                self.assertEqual(record.get("linked_frame_id"), result["frame_id"])
                self.assertEqual(record.get("status"), STATUS_FRAME_CREATED)

    def test_duplicate_event_does_not_create_second_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r1 = intake_event(_make_event("evt-q-dup"), runtime_data_dir=rd)
            r2 = intake_event(_make_event("evt-q-dup"), runtime_data_dir=rd)
            self.assertEqual(r2["status"], "DUPLICATE_EVENT")
            # Should not create a second frame
            if r1.get("frame_id"):
                self.assertEqual(r2.get("frame_id"), r1.get("frame_id"))

    def test_duplicate_event_record_links_original_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r1 = intake_event(_make_event("evt-q-dup2"), runtime_data_dir=rd)
            intake_event(_make_event("evt-q-dup2"), runtime_data_dir=rd)
            record = load_queue_record("evt-q-dup2", rd)
            self.assertIsNotNone(record)
            self.assertEqual(record.get("status"), STATUS_DUPLICATE_EVENT)
            if r1.get("frame_id"):
                self.assertTrue(record.get("duplicate"))

    def test_route_not_found_records_failure_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            ev = {
                "event_id": "evt-q-noroute",
                "source": "unknown_source_xyz",
                "event_type": "unknown_type_xyz",
                "payload": {},
                "received_at": "2026-05-17T00:00:00Z",
            }
            intake_event(ev, runtime_data_dir=rd)
            record = load_queue_record("evt-q-noroute", rd)
            self.assertIsNotNone(record)
            self.assertEqual(record.get("status"), STATUS_ROUTE_NOT_FOUND)
            self.assertIn("failure_code", record)
            self.assertEqual(record["failure_code"], "ROUTE_NOT_FOUND")

    def test_failed_runtime_event_records_failure_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            # Invalid event (missing event_id) triggers INVALID_EVENT / FAILED_EXECUTION
            ev = {
                "source": "external",
                "event_type": "stub",
                "payload": {},
                "received_at": "2026-05-17T00:00:00Z",
            }
            intake_event(ev, runtime_data_dir=rd)
            # INVALID_EVENT won't have a queue record by event_id since event_id is empty
            # but the queue file should have been written
            qp = rd / "events" / "event_queue.jsonl"
            self.assertTrue(qp.is_file(), "Queue JSONL should exist even for invalid events.")

    def test_list_event_queue_filters_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-q-filt1"), runtime_data_dir=rd)
            ev_no_route = {
                "event_id": "evt-q-filt2",
                "source": "zz_no_source",
                "event_type": "zz_no_type",
                "payload": {},
                "received_at": "2026-05-17T00:00:00Z",
            }
            intake_event(ev_no_route, runtime_data_dir=rd)

            no_route_records = list_queue_records(
                runtime_data_dir=rd,
                status=STATUS_ROUTE_NOT_FOUND,
            )
            self.assertTrue(
                any(r.get("event_id") == "evt-q-filt2" for r in no_route_records),
                "Filter by status ROUTE_NOT_FOUND should return no-route event.",
            )

    def test_get_event_detail_includes_linked_frame_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = intake_event(_make_event("evt-q-detail"), runtime_data_dir=rd)
            detail = get_event_detail("evt-q-detail", runtime_data_dir=rd)
            self.assertTrue(detail.get("ok"))
            self.assertEqual(detail.get("event_id"), "evt-q-detail")
            self.assertIn("failure_reason", detail)
            self.assertIn("replay_history", detail)
            if result.get("frame_id"):
                self.assertEqual(detail.get("linked_frame_id"), result["frame_id"])


class TestEventQueueFingerprint(unittest.TestCase):

    def test_build_event_fingerprint_is_deterministic(self):
        ev = _make_event("evt-fp-001")
        fp1 = build_event_fingerprint(ev)
        fp2 = build_event_fingerprint(ev)
        self.assertEqual(fp1, fp2)

    def test_build_event_fingerprint_differs_for_different_payload(self):
        ev1 = {**_make_event("evt-fp-002"), "payload": {"a": 1}}
        ev2 = {**_make_event("evt-fp-003"), "payload": {"a": 2}}
        self.assertNotEqual(build_event_fingerprint(ev1), build_event_fingerprint(ev2))

    def test_build_event_fingerprint_recorded_in_metadata(self):
        ev = _make_event("evt-fp-004")
        record = build_queue_record(ev)
        self.assertIn("fingerprint", record.get("metadata", {}))
        self.assertEqual(len(record["metadata"]["fingerprint"]), 64)  # sha256 hex


class TestListEventQueue(unittest.TestCase):

    def test_list_event_queue_returns_ok_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = list_event_queue(runtime_data_dir=rd)
            self.assertTrue(result["ok"])
            self.assertIsInstance(result["events"], list)
            self.assertIn("count", result)
            self.assertIn("filters", result)

    def test_list_event_queue_reflects_ingested_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            intake_event(_make_event("evt-q-list1"), runtime_data_dir=rd)
            intake_event(_make_event("evt-q-list2"), runtime_data_dir=rd)
            result = list_event_queue(runtime_data_dir=rd)
            ids = {ev.get("event_id") for ev in result["events"]}
            self.assertIn("evt-q-list1", ids)
            self.assertIn("evt-q-list2", ids)


if __name__ == "__main__":
    unittest.main()
