"""Spec 139 — Test: operator event sources panel helper."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.event_sources.event_source_contract import build_fixture_source_config
from runtime.event_sources.event_source_state import create_event_source
from runtime.event_sources.polling_engine import poll_event_source
from src.operator_event_sources_panel import build_event_sources_panel

FIXTURE_PATH = str(
    Path(__file__).parent / "fixtures" / "event_sources" / "customer_messages.json"
)


class TestBuildEventSourcesPanel(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rdd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_panel_ok_with_empty_store(self):
        panel = build_event_sources_panel(runtime_data_dir=self.rdd)
        self.assertTrue(panel["ok"])
        self.assertIn("summary", panel)
        self.assertIn("sources", panel)
        self.assertIn("recent_history", panel)
        self.assertIn("recent_enqueued_events", panel)
        self.assertIn("warnings", panel)

    def test_panel_summary_has_required_keys(self):
        panel = build_event_sources_panel(runtime_data_dir=self.rdd)
        summary = panel["summary"]
        self.assertIn("source_count", summary)
        self.assertIn("enabled_count", summary)
        self.assertIn("needs_auth_count", summary)
        self.assertIn("last_poll_at", summary)

    def test_panel_source_count_increases_with_sources(self):
        panel_before = build_event_sources_panel(runtime_data_dir=self.rdd)
        self.assertEqual(panel_before["summary"]["source_count"], 0)

        config = build_fixture_source_config(
            source_id="panel_test_src_01",
            name="Panel Test Source",
            event_source="fixture_inbox",
            event_type="msg",
            fixture_path=FIXTURE_PATH,
        )
        create_event_source(config, self.rdd)

        panel_after = build_event_sources_panel(runtime_data_dir=self.rdd)
        self.assertEqual(panel_after["summary"]["source_count"], 1)

    def test_panel_enabled_count_accurate(self):
        cfg_on = build_fixture_source_config(
            source_id="panel_on", name="On", event_source="x", event_type="x",
            fixture_path=FIXTURE_PATH, enabled=True,
        )
        cfg_off = build_fixture_source_config(
            source_id="panel_off", name="Off", event_source="x", event_type="x",
            fixture_path=FIXTURE_PATH, enabled=False,
        )
        create_event_source(cfg_on, self.rdd)
        create_event_source(cfg_off, self.rdd)

        panel = build_event_sources_panel(runtime_data_dir=self.rdd)
        self.assertEqual(panel["summary"]["source_count"], 2)
        self.assertEqual(panel["summary"]["enabled_count"], 1)

    def test_panel_shows_history_after_poll(self):
        config = build_fixture_source_config(
            source_id="panel_poll_src",
            name="Panel Poll Source",
            event_source="fixture_inbox",
            event_type="msg",
            fixture_path=FIXTURE_PATH,
            enabled=True,
        )
        create_event_source(config, self.rdd)
        poll_event_source("panel_poll_src", self.rdd)

        panel = build_event_sources_panel(runtime_data_dir=self.rdd)
        self.assertTrue(panel["ok"])
        self.assertGreater(len(panel["recent_history"]), 0)

    def test_panel_source_summaries_have_required_fields(self):
        config = build_fixture_source_config(
            source_id="panel_fields_src",
            name="Panel Fields Source",
            event_source="fixture_inbox",
            event_type="msg",
            fixture_path=FIXTURE_PATH,
        )
        create_event_source(config, self.rdd)
        panel = build_event_sources_panel(runtime_data_dir=self.rdd)
        src = panel["sources"][0]
        for field in ("source_id", "name", "adapter", "mode", "enabled", "health_status"):
            self.assertIn(field, src, f"Missing field: {field}")

    def test_panel_never_triggers_processing(self):
        config = build_fixture_source_config(
            source_id="panel_no_side_effects",
            name="Panel No Side Effects",
            event_source="fixture_inbox",
            event_type="msg",
            fixture_path=FIXTURE_PATH,
            enabled=True,
        )
        create_event_source(config, self.rdd)
        panel1 = build_event_sources_panel(runtime_data_dir=self.rdd)
        panel2 = build_event_sources_panel(runtime_data_dir=self.rdd)
        src1 = next((s for s in panel1["sources"] if s["source_id"] == "panel_no_side_effects"), {})
        src2 = next((s for s in panel2["sources"] if s["source_id"] == "panel_no_side_effects"), {})
        self.assertEqual(src1.get("poll_count", 0), 0)
        self.assertEqual(src2.get("poll_count", 0), 0)

    def test_panel_returns_error_shape_on_catastrophic_failure(self):
        with unittest.mock.patch(
            "runtime.event_sources.event_source_state.list_event_sources",
            side_effect=RuntimeError("boom"),
        ):
            panel = build_event_sources_panel(runtime_data_dir=self.rdd)
        self.assertFalse(panel["ok"])
        self.assertIn("error", panel)


import unittest.mock


if __name__ == "__main__":
    unittest.main()
