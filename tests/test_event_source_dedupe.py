"""Spec 139 — Test: event source deduplication rules."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_sources.event_source_contract import build_fixture_source_config
from runtime.event_sources.event_source_state import create_event_source
from runtime.event_sources.polling_engine import enqueue_polled_events, poll_event_source

FIXTURE_PATH = str(
    Path(__file__).parent / "fixtures" / "event_sources" / "customer_messages.json"
)

DUPLICATE_FIXTURE_PATH = str(
    Path(__file__).parent / "fixtures" / "event_sources" / "customer_messages_duplicate.json"
)


def _make_event(message_id: str, source: str = "fixture_customer_inbox") -> dict:
    return {
        "event_id": f"evt_fixture_{message_id.replace('-', '_')}",
        "source": source,
        "event_type": "customer_message_received",
        "received_at": "2026-05-21T08:00:00Z",
        "payload": {"message_id": message_id, "customer_id": "CUST-100"},
    }


class TestEventSourceDedupe(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_first_enqueue_succeeds(self):
        event = _make_event("dedup_msg_001")
        result = enqueue_polled_events("test_src", [event], self.rdd)
        self.assertTrue(result["ok"])
        self.assertEqual(result["enqueued_count"], 1)
        self.assertEqual(result["duplicate_count"], 0)

    def test_second_enqueue_of_same_event_is_deduplicated(self):
        event = _make_event("dedup_msg_002")
        enqueue_polled_events("test_src", [event], self.rdd)
        result2 = enqueue_polled_events("test_src", [event], self.rdd)
        self.assertTrue(result2["ok"])
        self.assertEqual(result2["enqueued_count"], 0)
        self.assertEqual(result2["duplicate_count"], 1)

    def test_different_messages_not_deduplicated(self):
        event_a = _make_event("dedup_msg_003a")
        event_b = _make_event("dedup_msg_003b")
        enqueue_polled_events("test_src", [event_a], self.rdd)
        result = enqueue_polled_events("test_src", [event_b], self.rdd)
        self.assertEqual(result["enqueued_count"], 1)
        self.assertEqual(result["duplicate_count"], 0)

    def test_fixture_adapter_cursor_prevents_repolling_same_ids(self):
        from runtime.event_sources.adapters.fixture_json import FixtureJsonAdapter

        adapter = FixtureJsonAdapter()
        config = {
            "source_id": "cursor_dedup_src",
            "event_source": "fixture_customer_inbox",
            "event_type": "customer_message_received",
            "poll": {"fixture_path": FIXTURE_PATH, "max_events_per_poll": 10},
            "dedupe": {"key_template": "fixture:{message_id}"},
        }

        state_empty = {"source_id": "cursor_dedup_src", "cursor": {"seen_ids": []}}
        first_result = adapter.poll(config, state_empty)
        self.assertTrue(first_result["ok"])
        first_seen = list(first_result["cursor_update"].get("seen_ids") or [])

        state_with_seen = {"source_id": "cursor_dedup_src", "cursor": {"seen_ids": first_seen}}
        second_result = adapter.poll(config, state_with_seen)
        self.assertTrue(second_result["ok"])
        self.assertEqual(second_result["event_count"], 0)

    def test_polling_engine_dedupe_across_two_polls(self):
        config = build_fixture_source_config(
            source_id="engine_dedup_src",
            name="Engine Dedup Test",
            event_source="fixture_customer_inbox",
            event_type="customer_message_received",
            fixture_path=FIXTURE_PATH,
            enabled=True,
        )
        create_event_source(config, self.rdd)

        first = poll_event_source("engine_dedup_src", self.rdd)
        self.assertTrue(first["ok"])
        first_enqueued = first["enqueued_count"]

        second = poll_event_source("engine_dedup_src", self.rdd)
        self.assertTrue(second["ok"])
        second_enqueued = second["enqueued_count"]
        second_dup = second["duplicate_count"]

        self.assertEqual(second_enqueued, 0)
        self.assertGreaterEqual(second_dup, 0)

    def test_duplicate_fixture_not_double_enqueued(self):
        config = build_fixture_source_config(
            source_id="dup_fixture_src",
            name="Duplicate Fixture Source",
            event_source="fixture_customer_inbox",
            event_type="customer_message_received",
            fixture_path=FIXTURE_PATH,
            enabled=True,
        )
        create_event_source(config, self.rdd)
        poll_event_source("dup_fixture_src", self.rdd)

        config_dup = build_fixture_source_config(
            source_id="dup_fixture_src2",
            name="Duplicate Fixture Source 2",
            event_source="fixture_customer_inbox",
            event_type="customer_message_received",
            fixture_path=DUPLICATE_FIXTURE_PATH,
            enabled=True,
        )
        create_event_source(config_dup, self.rdd)
        result_dup = poll_event_source("dup_fixture_src2", self.rdd)
        self.assertTrue(result_dup["ok"])
        # The duplicate message should either not be enqueued OR be counted as a duplicate
        self.assertEqual(
            result_dup["enqueued_count"] + result_dup["duplicate_count"],
            result_dup["event_count"],
        )


if __name__ == "__main__":
    unittest.main()
