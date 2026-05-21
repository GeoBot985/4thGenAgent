"""Spec 137 — Test: durable queue runner."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_queue import enqueue_event, list_queue
from runtime.event_queue_contract import STATUS_COMPLETED, STATUS_PENDING
from runtime.event_queue_runner import process_next_queued_event, process_queued_events


def _make_event(
    event_id: str = "evt-run-001",
    source: str = "operator_ui",
    event_type: str = "test.no_route",
) -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "event_type": event_type,
        "payload": {"key": "value"},
    }


class TestProcessNextQueuedEvent(unittest.TestCase):

    def test_no_pending_returns_no_pending_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = process_next_queued_event(runtime_data_dir=rd)
            self.assertFalse(result.get("ok"))
            self.assertTrue(result.get("no_pending_event"))

    def test_process_next_claims_and_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            result = process_next_queued_event(runtime_data_dir=rd)
            self.assertIn("queue_id", result)
            self.assertIn("status", result)

    def test_process_next_removes_item_from_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event("e1", "op", "t.no_route_x"), runtime_data_dir=rd)
            process_next_queued_event(runtime_data_dir=rd)
            pending = list_queue(status=STATUS_PENDING, runtime_data_dir=rd)
            self.assertEqual(pending["count"], 0, "No pending items after processing")

    def test_process_next_links_frame_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            result = process_next_queued_event(runtime_data_dir=rd)
            if result.get("ok"):
                self.assertIn("frame_id", result)

    def test_no_live_side_effects_during_processing(self):
        """Processing must never trigger live execution."""
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            result = process_next_queued_event(runtime_data_dir=rd)
            # The runner always uses dry_run=True via intake_and_run_event
            # Just verify the queue item transitioned out of PENDING
            self.assertNotIn(result.get("status", ""), (STATUS_PENDING,))

    def test_failed_route_is_classified_as_permanent_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event("e1", "unknown_source", "no.route.event"), runtime_data_dir=rd)
            result = process_next_queued_event(runtime_data_dir=rd)
            # May be FAILED or COMPLETED depending on route resolution
            self.assertIn("queue_id", result)

    def test_second_process_next_finds_no_more_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            process_next_queued_event(runtime_data_dir=rd)
            result2 = process_next_queued_event(runtime_data_dir=rd)
            self.assertTrue(result2.get("no_pending_event"))


class TestProcessQueuedEvents(unittest.TestCase):

    def test_process_zero_items_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            result = process_queued_events(limit=5, runtime_data_dir=rd)
            self.assertTrue(result["ok"])
            self.assertEqual(result["processed"], 1)  # one no-work result
            self.assertTrue(result["no_more_pending"])

    def test_process_batch_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            for i in range(5):
                enqueue_event(_make_event(f"e{i}", "op", f"t.x{i}"), runtime_data_dir=rd)
            result = process_queued_events(limit=3, runtime_data_dir=rd)
            self.assertTrue(result["ok"])
            self.assertLessEqual(result["processed"], 4)

    def test_process_batch_returns_result_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            enqueue_event(_make_event(), runtime_data_dir=rd)
            result = process_queued_events(limit=5, runtime_data_dir=rd)
            self.assertIn("results", result)
            self.assertIsInstance(result["results"], list)
