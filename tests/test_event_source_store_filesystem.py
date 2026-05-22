"""Spec 139 — Test: event source filesystem backend persistence."""
from __future__ import annotations

import tempfile
import unittest

from runtime.event_sources.event_source_contract import build_fixture_source_config
from runtime.event_sources.event_source_state import (
    build_history_record,
    create_event_source,
    disable_event_source,
    enable_event_source,
    get_event_source,
    get_event_source_state,
    list_event_source_history,
    list_event_sources,
    save_event_source,
    save_event_source_state,
    append_event_source_history,
)


class TestEventSourceFilesystemStore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _make_config(self, source_id: str = "test_src_001") -> dict:
        return build_fixture_source_config(
            source_id=source_id,
            name="Test Fixture Source",
            event_source="fixture_inbox",
            event_type="message_received",
            fixture_path="tests/fixtures/event_sources/customer_messages.json",
            enabled=True,
        )

    # --- Source config CRUD ---

    def test_create_and_retrieve_source(self):
        config = self._make_config("fs_src_001")
        result = create_event_source(config, self.rdd)
        self.assertTrue(result["ok"])
        retrieved = get_event_source("fs_src_001", self.rdd)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["source_id"], "fs_src_001")

    def test_get_nonexistent_source_returns_none(self):
        retrieved = get_event_source("no_such_source", self.rdd)
        self.assertIsNone(retrieved)

    def test_duplicate_create_fails(self):
        config = self._make_config("fs_dup_001")
        create_event_source(config, self.rdd)
        result = create_event_source(config, self.rdd)
        self.assertFalse(result["ok"])
        self.assertIn("already exists", result["error"])

    def test_list_sources_returns_all(self):
        create_event_source(self._make_config("s1"), self.rdd)
        create_event_source(self._make_config("s2"), self.rdd)
        sources = list_event_sources(self.rdd)
        ids = [s["source_id"] for s in sources]
        self.assertIn("s1", ids)
        self.assertIn("s2", ids)

    def test_list_sources_enabled_only(self):
        cfg_enabled = self._make_config("enabled_src")
        cfg_enabled["enabled"] = True
        cfg_disabled = self._make_config("disabled_src")
        cfg_disabled["enabled"] = False
        create_event_source(cfg_enabled, self.rdd)
        create_event_source(cfg_disabled, self.rdd)
        enabled = list_event_sources(self.rdd, enabled_only=True)
        ids = [s["source_id"] for s in enabled]
        self.assertIn("enabled_src", ids)
        self.assertNotIn("disabled_src", ids)

    def test_enable_disable_source(self):
        create_event_source(self._make_config("toggle_src"), self.rdd)
        disable_event_source("toggle_src", self.rdd)
        cfg = get_event_source("toggle_src", self.rdd)
        self.assertFalse(cfg["enabled"])
        enable_event_source("toggle_src", self.rdd)
        cfg = get_event_source("toggle_src", self.rdd)
        self.assertTrue(cfg["enabled"])

    def test_enable_nonexistent_source_returns_error(self):
        result = enable_event_source("no_src", self.rdd)
        self.assertFalse(result["ok"])

    # --- State CRUD ---

    def test_default_state_returned_for_new_source(self):
        state = get_event_source_state("brand_new_src", self.rdd)
        self.assertEqual(state["source_id"], "brand_new_src")
        self.assertEqual(state["poll_count"], 0)
        self.assertIn("cursor", state)

    def test_save_and_retrieve_state(self):
        state = get_event_source_state("state_src", self.rdd)
        state["poll_count"] = 5
        state["event_count"] = 10
        save_event_source_state(state, self.rdd)
        loaded = get_event_source_state("state_src", self.rdd)
        self.assertEqual(loaded["poll_count"], 5)
        self.assertEqual(loaded["event_count"], 10)

    # --- History ---

    def test_append_and_list_history(self):
        hist = build_history_record("hist_src", ok=True, adapter="fixture_json", event_count=3, enqueued_count=3)
        append_event_source_history(hist, self.rdd)
        records = list_event_source_history(self.rdd, source_id="hist_src")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_id"], "hist_src")
        self.assertTrue(records[0]["ok"])

    def test_history_filter_by_source_id(self):
        hist_a = build_history_record("src_a", ok=True)
        hist_b = build_history_record("src_b", ok=False, error="test error")
        append_event_source_history(hist_a, self.rdd)
        append_event_source_history(hist_b, self.rdd)
        records_a = list_event_source_history(self.rdd, source_id="src_a")
        self.assertEqual(len(records_a), 1)
        self.assertEqual(records_a[0]["source_id"], "src_a")

    def test_history_empty_initially(self):
        records = list_event_source_history(self.rdd, source_id="fresh_src")
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
