"""Spec 137 — Test: operator UI queue panel helper."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import (
    claim_next_event,
    enqueue_event,
    mark_event_completed,
    mark_event_failed,
    mark_event_processing,
)
from runtime.event_queue_contract import FAILURE_RUNTIME_EXCEPTION
from runtime.operator_queue_panel import build_queue_panel


def _make_event(event_id: str = "evt-op-001", source: str = "operator_ui", event_type: str = "test.panel") -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"x": 1},
    }


class TestBuildQueuePanel(unittest.TestCase):

    def test_empty_queue_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            panel = build_queue_panel(rd)
            self.assertTrue(panel["ok"])

    def test_empty_queue_has_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            panel = build_queue_panel(rd)
            required = ["ok", "summary", "pending", "processing", "failed_retryable", "dead_letter", "recent_completed"]
            for key in required:
                self.assertIn(key, panel, f"Missing key: {key}")

    def test_summary_has_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            panel = build_queue_panel(rd)
            summary = panel["summary"]
            for field in ("total", "pending", "processing", "failed_retryable", "dead_letter", "completed", "backend"):
                self.assertIn(field, summary, f"Missing summary field: {field}")

    def test_pending_shows_in_pending_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event("e1"), runtime_data_dir=rd)
            enqueue_event(_make_event("e2"), runtime_data_dir=rd)
            panel = build_queue_panel(rd)
            self.assertEqual(len(panel["pending"]), 2)
            self.assertEqual(panel["summary"]["pending"], 2)

    def test_processing_shows_in_processing_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            claim_next_event("w1", rd)
            mark_event_processing(r["queue_id"], rd)
            panel = build_queue_panel(rd)
            self.assertEqual(panel["summary"]["processing"], 1)
            self.assertEqual(len(panel["processing"]), 1)

    def test_completed_shows_in_recent_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)
            mark_event_processing(queue_id, rd)
            mark_event_completed(queue_id, "frame-123", rd)
            panel = build_queue_panel(rd)
            self.assertEqual(panel["summary"]["completed"], 1)
            self.assertEqual(len(panel["recent_completed"]), 1)

    def test_failed_retryable_shows_in_failed_retryable_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            r = enqueue_event(_make_event(), runtime_data_dir=rd)
            queue_id = r["queue_id"]
            claim_next_event("w1", rd)
            mark_event_processing(queue_id, rd)
            mark_event_failed(queue_id, {"message": "timeout", "category": FAILURE_RUNTIME_EXCEPTION}, rd)
            panel = build_queue_panel(rd)
            self.assertEqual(panel["summary"]["failed_retryable"], 1)
            self.assertEqual(len(panel["failed_retryable"]), 1)

    def test_panel_records_are_slimmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            panel = build_queue_panel(rd)
            if panel["pending"]:
                record = panel["pending"][0]
                self.assertIn("queue_id", record)
                self.assertIn("status", record)
                self.assertIn("source", record)
                self.assertIn("event_type", record)
                self.assertNotIn("payload_json", record)

    def test_panel_does_not_start_processing(self):
        """build_queue_panel is read-only and must not claim or process items."""
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            build_queue_panel(rd)
            build_queue_panel(rd)
            panel = build_queue_panel(rd)
            self.assertEqual(panel["summary"]["pending"], 1)
            self.assertEqual(len(panel["processing"]), 0)

    def test_summary_total_counts_all_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event("e1"), runtime_data_dir=rd)
            enqueue_event(_make_event("e2"), runtime_data_dir=rd)
            enqueue_event(_make_event("e3"), runtime_data_dir=rd)
            panel = build_queue_panel(rd)
            self.assertEqual(panel["summary"]["total"], 3)
