"""Spec 139 — Test: fixture JSON event source adapter."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from runtime.event_sources.adapters.fixture_json import FixtureJsonAdapter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "event_sources"


def _make_config(fixture_path: str, source_id: str = "test_fixture_src", max_events: int = 10) -> dict:
    return {
        "source_id": source_id,
        "name": "Test Fixture Source",
        "adapter": "fixture_json",
        "mode": "fixture",
        "event_source": "fixture_customer_inbox",
        "event_type": "customer_message_received",
        "enabled": True,
        "poll": {"fixture_path": fixture_path, "max_events_per_poll": max_events},
        "dedupe": {"key_template": "fixture:{message_id}"},
    }


class TestFixtureJsonAdapterHealth(unittest.TestCase):

    def test_health_ok_when_fixture_exists(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages.json"))
        result = adapter.health(config)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")

    def test_health_fails_when_fixture_missing(self):
        adapter = FixtureJsonAdapter()
        config = _make_config("/nonexistent/path.json")
        result = adapter.health(config)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "fixture_missing")

    def test_health_fails_when_fixture_path_not_set(self):
        adapter = FixtureJsonAdapter()
        config = _make_config("")
        result = adapter.health(config)
        self.assertFalse(result["ok"])


class TestFixtureJsonAdapterPoll(unittest.TestCase):

    def _empty_state(self) -> dict:
        return {"source_id": "test_fixture_src", "cursor": {"watermark": "", "seen_ids": []}}

    def test_poll_reads_fixture_events(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages.json"))
        state = self._empty_state()
        result = adapter.poll(config, state)
        self.assertTrue(result["ok"])
        self.assertGreater(result["event_count"], 0)
        self.assertGreater(result["raw_count"], 0)
        self.assertEqual(len(result["events"]), result["event_count"])

    def test_poll_empty_fixture_returns_zero_events(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages_empty.json"))
        state = self._empty_state()
        result = adapter.poll(config, state)
        self.assertTrue(result["ok"])
        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["raw_count"], 0)

    def test_poll_malformed_fixture_returns_error(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages_malformed.json"))
        state = self._empty_state()
        result = adapter.poll(config, state)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "malformed_fixture")

    def test_poll_missing_fixture_returns_error(self):
        adapter = FixtureJsonAdapter()
        config = _make_config("/nonexistent/path.json")
        state = self._empty_state()
        result = adapter.poll(config, state)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "malformed_fixture")

    def test_poll_respects_max_events(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages.json"), max_events=1)
        state = self._empty_state()
        result = adapter.poll(config, state)
        self.assertTrue(result["ok"])
        self.assertLessEqual(result["event_count"], 1)

    def test_poll_provides_cursor_update_with_seen_ids(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages.json"))
        state = self._empty_state()
        result = adapter.poll(config, state)
        self.assertTrue(result["ok"])
        if result["event_count"] > 0:
            self.assertIn("seen_ids", result["cursor_update"])
            self.assertGreater(len(result["cursor_update"]["seen_ids"]), 0)

    def test_poll_skips_already_seen_ids(self):
        adapter = FixtureJsonAdapter()
        config = _make_config(str(FIXTURE_DIR / "customer_messages.json"))
        state = {"source_id": "test", "cursor": {"seen_ids": ["fixture:msg-fixture-001", "fixture:msg-fixture-002", "fixture:msg-fixture-003"]}}
        result = adapter.poll(config, state)
        self.assertTrue(result["ok"])
        self.assertEqual(result["event_count"], 0)


class TestFixtureJsonAdapterNormalize(unittest.TestCase):

    def _config(self) -> dict:
        return {
            "source_id": "test_src",
            "event_source": "fixture_customer_inbox",
            "event_type": "customer_message_received",
            "poll": {},
            "dedupe": {},
        }

    def test_normalize_produces_standard_event_shape(self):
        adapter = FixtureJsonAdapter()
        raw = {
            "message_id": "msg-001",
            "customer_id": "CUST-100",
            "from": "alex@example.com",
            "subject": "Help needed",
            "body": "Hello!",
            "received_at": "2026-05-21T08:00:00+00:00",
        }
        event = adapter.normalize(raw, self._config())
        self.assertIn("event_id", event)
        self.assertIn("source", event)
        self.assertIn("event_type", event)
        self.assertIn("received_at", event)
        self.assertIn("payload", event)
        self.assertTrue(event["event_id"].startswith("evt_fixture_"))
        self.assertEqual(event["source"], "fixture_customer_inbox")
        self.assertEqual(event["event_type"], "customer_message_received")
        self.assertEqual(event["payload"]["message_id"], "msg-001")
        self.assertEqual(event["payload"]["from"], "alex@example.com")
        self.assertEqual(event["payload"]["channel"], "email")

    def test_normalize_body_goes_to_message_field(self):
        adapter = FixtureJsonAdapter()
        raw = {"message_id": "msg-002", "body": "My body text"}
        event = adapter.normalize(raw, self._config())
        self.assertEqual(event["payload"]["message"], "My body text")


if __name__ == "__main__":
    unittest.main()
