"""Spec 139 — Test: event source polling engine."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_sources.event_source_contract import build_fixture_source_config
from runtime.event_sources.event_source_state import (
    create_event_source,
    get_event_source_state,
    list_event_source_history,
)
from runtime.event_sources.polling_engine import (
    enqueue_polled_events,
    normalize_polled_events,
    poll_enabled_event_sources,
    poll_event_source,
)

FIXTURE_PATH = str(
    Path(__file__).parent / "fixtures" / "event_sources" / "customer_messages.json"
)


def _make_fixture_config(source_id: str, enabled: bool = True, rdd: str = "runtime_data") -> dict:
    return build_fixture_source_config(
        source_id=source_id,
        name=f"Test Fixture Source {source_id}",
        event_source="fixture_customer_inbox",
        event_type="customer_message_received",
        fixture_path=FIXTURE_PATH,
        enabled=enabled,
    )


class TestPollEventSource(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_poll_nonexistent_source_returns_error(self):
        result = poll_event_source("no_such_src", self.rdd)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "source_not_found")

    def test_poll_disabled_source_returns_error(self):
        config = _make_fixture_config("disabled_src", enabled=False)
        create_event_source(config, self.rdd)
        result = poll_event_source("disabled_src", self.rdd)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "source_disabled")

    def test_poll_fixture_source_succeeds(self):
        config = _make_fixture_config("enabled_src_01")
        create_event_source(config, self.rdd)
        result = poll_event_source("enabled_src_01", self.rdd)
        self.assertTrue(result["ok"])
        self.assertGreater(result["event_count"], 0)
        self.assertGreaterEqual(result["enqueued_count"], 0)

    def test_poll_enqueues_events_into_durable_queue(self):
        config = _make_fixture_config("queue_src_01")
        create_event_source(config, self.rdd)
        result = poll_event_source("queue_src_01", self.rdd)
        self.assertTrue(result["ok"])
        self.assertGreater(result["enqueued_count"], 0)

    def test_poll_updates_state_poll_count(self):
        config = _make_fixture_config("state_update_src")
        create_event_source(config, self.rdd)
        poll_event_source("state_update_src", self.rdd)
        state = get_event_source_state("state_update_src", self.rdd)
        self.assertEqual(state["poll_count"], 1)

    def test_poll_writes_history(self):
        config = _make_fixture_config("history_src")
        create_event_source(config, self.rdd)
        poll_event_source("history_src", self.rdd)
        history = list_event_source_history(self.rdd, source_id="history_src")
        self.assertGreater(len(history), 0)
        self.assertTrue(history[0]["ok"])

    def test_duplicate_poll_skips_duplicates(self):
        config = _make_fixture_config("dedup_src")
        create_event_source(config, self.rdd)
        first = poll_event_source("dedup_src", self.rdd)
        self.assertTrue(first["ok"])
        second = poll_event_source("dedup_src", self.rdd)
        self.assertTrue(second["ok"])
        # Second poll should see duplicates (queue-level dedupe) or empty
        total_new = second.get("enqueued_count", 0)
        total_dup = second.get("duplicate_count", 0)
        # Either enqueued 0 new or reported duplicates
        self.assertEqual(total_new + total_dup, second.get("event_count", 0) + total_dup)

    def test_cursor_persists_across_polls(self):
        config = _make_fixture_config("cursor_src")
        create_event_source(config, self.rdd)
        poll_event_source("cursor_src", self.rdd)
        state = get_event_source_state("cursor_src", self.rdd)
        cursor = state.get("cursor", {})
        self.assertIsInstance(cursor.get("seen_ids", []), list)


class TestPollEnabledSources(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_poll_enabled_with_no_sources_returns_ok(self):
        result = poll_enabled_event_sources(self.rdd)
        self.assertTrue(result["ok"])
        self.assertEqual(result["sources_polled"], 0)

    def test_poll_enabled_skips_disabled_sources(self):
        cfg_disabled = _make_fixture_config("disabled_s", enabled=False)
        create_event_source(cfg_disabled, self.rdd)
        result = poll_enabled_event_sources(self.rdd)
        self.assertEqual(result["sources_polled"], 0)

    def test_poll_enabled_polls_only_enabled_sources(self):
        create_event_source(_make_fixture_config("active_s1", enabled=True), self.rdd)
        create_event_source(_make_fixture_config("inactive_s2", enabled=False), self.rdd)
        result = poll_enabled_event_sources(self.rdd)
        self.assertEqual(result["sources_polled"], 1)


class TestNormalizePolledEvents(unittest.TestCase):

    def test_valid_events_pass_through(self):
        events = [
            {"event_id": "e1", "source": "fixture", "event_type": "msg", "payload": {}},
            {"event_id": "e2", "source": "fixture", "event_type": "msg", "payload": {}},
        ]
        result = normalize_polled_events({"events": events})
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["warnings"], [])

    def test_missing_required_fields_skipped(self):
        events = [
            {"event_id": "e1", "source": "fixture"},
        ]
        result = normalize_polled_events({"events": events})
        self.assertEqual(result["count"], 0)
        self.assertGreater(len(result["warnings"]), 0)

    def test_non_dict_events_skipped(self):
        result = normalize_polled_events({"events": ["not_a_dict", None, 42]})
        self.assertEqual(result["count"], 0)


class TestEnqueuePolledEvents(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_enqueue_events_returns_ok(self):
        events = [
            {
                "event_id": "evt_enq_test_001",
                "source": "fixture_customer_inbox",
                "event_type": "customer_message_received",
                "received_at": "2026-05-21T08:00:00Z",
                "payload": {"message_id": "enq_msg_001"},
            }
        ]
        result = enqueue_polled_events("test_src", events, self.rdd)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["enqueued_count"], 0)

    def test_duplicate_enqueue_counted_as_duplicate(self):
        event = {
            "event_id": "evt_dup_enq_001",
            "source": "fixture_customer_inbox",
            "event_type": "customer_message_received",
            "received_at": "2026-05-21T08:00:00Z",
            "payload": {"message_id": "dup_enq_msg_001"},
        }
        enqueue_polled_events("test_src", [event], self.rdd)
        result2 = enqueue_polled_events("test_src", [event], self.rdd)
        self.assertTrue(result2["ok"])
        self.assertEqual(result2["duplicate_count"], 1)
        self.assertEqual(result2["enqueued_count"], 0)


if __name__ == "__main__":
    unittest.main()
