"""Spec 139 — Test: event source SQLite backend persistence."""
from __future__ import annotations

import os
import tempfile
import unittest

from runtime.event_sources.event_source_contract import build_fixture_source_config
from runtime.event_sources.event_source_state import (
    build_history_record,
    create_event_source,
    get_event_source,
    get_event_source_state,
    list_event_source_history,
    list_event_sources,
    save_event_source_state,
    append_event_source_history,
)


class TestEventSourceSQLiteStore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name
        os.environ["TASKFRAME_PERSISTENCE_BACKEND"] = "sqlite"
        os.environ["TASKFRAME_SQLITE_DB_PATH"] = str(
            __import__("pathlib").Path(self.rdd) / "test_event_sources.db"
        )

    def tearDown(self):
        os.environ.pop("TASKFRAME_PERSISTENCE_BACKEND", None)
        os.environ.pop("TASKFRAME_SQLITE_DB_PATH", None)
        self._tmp.cleanup()

    def _make_config(self, source_id: str) -> dict:
        return build_fixture_source_config(
            source_id=source_id,
            name=f"SQLite Test Source {source_id}",
            event_source="fixture_inbox",
            event_type="message_received",
            fixture_path="tests/fixtures/event_sources/customer_messages.json",
            enabled=True,
        )

    def test_create_and_retrieve_source_sqlite(self):
        config = self._make_config("sqlite_src_001")
        result = create_event_source(config, self.rdd)
        self.assertTrue(result["ok"])
        retrieved = get_event_source("sqlite_src_001", self.rdd)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["source_id"], "sqlite_src_001")

    def test_list_sources_sqlite(self):
        create_event_source(self._make_config("sq_s1"), self.rdd)
        create_event_source(self._make_config("sq_s2"), self.rdd)
        sources = list_event_sources(self.rdd)
        ids = [s["source_id"] for s in sources]
        self.assertIn("sq_s1", ids)
        self.assertIn("sq_s2", ids)

    def test_list_sources_enabled_filter_sqlite(self):
        cfg_on = self._make_config("sq_on")
        cfg_on["enabled"] = True
        cfg_off = self._make_config("sq_off")
        cfg_off["enabled"] = False
        create_event_source(cfg_on, self.rdd)
        create_event_source(cfg_off, self.rdd)
        enabled = list_event_sources(self.rdd, enabled_only=True)
        ids = [s["source_id"] for s in enabled]
        self.assertIn("sq_on", ids)
        self.assertNotIn("sq_off", ids)

    def test_default_state_sqlite(self):
        state = get_event_source_state("brand_new_sqlite_src", self.rdd)
        self.assertEqual(state["source_id"], "brand_new_sqlite_src")
        self.assertEqual(state["poll_count"], 0)

    def test_save_and_load_state_sqlite(self):
        state = get_event_source_state("stateful_sqlite_src", self.rdd)
        state["poll_count"] = 7
        state["event_count"] = 14
        save_event_source_state(state, self.rdd)
        loaded = get_event_source_state("stateful_sqlite_src", self.rdd)
        self.assertEqual(loaded["poll_count"], 7)
        self.assertEqual(loaded["event_count"], 14)

    def test_append_and_list_history_sqlite(self):
        hist = build_history_record("sqlite_hist_src", ok=True, adapter="fixture_json", enqueued_count=5)
        append_event_source_history(hist, self.rdd)
        records = list_event_source_history(self.rdd, source_id="sqlite_hist_src")
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["ok"])

    def test_history_filter_by_source_id_sqlite(self):
        append_event_source_history(build_history_record("sq_hist_a", ok=True), self.rdd)
        append_event_source_history(build_history_record("sq_hist_b", ok=True), self.rdd)
        records = list_event_source_history(self.rdd, source_id="sq_hist_a")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_id"], "sq_hist_a")

    def test_get_nonexistent_source_returns_none_sqlite(self):
        retrieved = get_event_source("nonexistent_sq", self.rdd)
        self.assertIsNone(retrieved)


if __name__ == "__main__":
    unittest.main()
