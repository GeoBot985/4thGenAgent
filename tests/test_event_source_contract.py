"""Spec 139 — Test: event source config contract shape and validation."""
from __future__ import annotations

import unittest

from runtime.event_sources.event_source_contract import (
    ADAPTER_FIXTURE_JSON,
    ADAPTER_GMAIL_READONLY,
    FAILURE_CREDENTIALS_MISSING,
    FAILURE_SOURCE_DISABLED,
    FAILURE_SOURCE_NOT_FOUND,
    MODE_FIXTURE,
    MODE_LIVE_READ,
    build_event_source_config,
    build_fixture_source_config,
    validate_event_source_config,
)


class TestBuildEventSourceConfig(unittest.TestCase):

    def test_basic_fields_present(self):
        cfg = build_event_source_config(
            source_id="test_src_001",
            name="Test Source",
            adapter=ADAPTER_FIXTURE_JSON,
            mode=MODE_FIXTURE,
            event_source="test_inbox",
            event_type="message_received",
        )
        self.assertEqual(cfg["source_id"], "test_src_001")
        self.assertEqual(cfg["name"], "Test Source")
        self.assertEqual(cfg["adapter"], ADAPTER_FIXTURE_JSON)
        self.assertEqual(cfg["mode"], MODE_FIXTURE)
        self.assertEqual(cfg["event_source"], "test_inbox")
        self.assertEqual(cfg["event_type"], "message_received")
        self.assertFalse(cfg["enabled"])
        self.assertIn("created_at", cfg)
        self.assertIn("updated_at", cfg)

    def test_enabled_default_is_false(self):
        cfg = build_event_source_config(
            source_id="x", name="x", adapter="fixture_json",
            mode="fixture", event_source="x", event_type="x",
        )
        self.assertFalse(cfg["enabled"])

    def test_enabled_can_be_set_true(self):
        cfg = build_event_source_config(
            source_id="x", name="x", adapter="fixture_json",
            mode="fixture", event_source="x", event_type="x",
            enabled=True,
        )
        self.assertTrue(cfg["enabled"])

    def test_poll_and_dedupe_default_to_empty_dicts(self):
        cfg = build_event_source_config(
            source_id="x", name="x", adapter="fixture_json",
            mode="fixture", event_source="x", event_type="x",
        )
        self.assertEqual(cfg["poll"], {})
        self.assertEqual(cfg["dedupe"], {})


class TestBuildFixtureSourceConfig(unittest.TestCase):

    def test_fixture_config_has_adapter_fixture_json(self):
        cfg = build_fixture_source_config(
            source_id="fixture_001",
            name="Fixture Test",
            event_source="fixture_inbox",
            event_type="message_received",
            fixture_path="tests/fixtures/event_sources/customer_messages.json",
        )
        self.assertEqual(cfg["adapter"], ADAPTER_FIXTURE_JSON)
        self.assertEqual(cfg["mode"], MODE_FIXTURE)
        self.assertTrue(cfg["enabled"])

    def test_fixture_config_has_fixture_path(self):
        cfg = build_fixture_source_config(
            source_id="fixture_002",
            name="Fixture Test",
            event_source="inbox",
            event_type="msg",
            fixture_path="some/path.json",
        )
        self.assertEqual(cfg["poll"]["fixture_path"], "some/path.json")
        self.assertEqual(cfg["poll"]["max_events_per_poll"], 10)


class TestValidateEventSourceConfig(unittest.TestCase):

    def _valid_config(self) -> dict:
        return {
            "source_id": "test_001",
            "name": "Test",
            "adapter": ADAPTER_FIXTURE_JSON,
            "mode": MODE_FIXTURE,
            "event_source": "inbox",
            "event_type": "message",
        }

    def test_valid_config_passes(self):
        ok, errors = validate_event_source_config(self._valid_config())
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_missing_source_id_fails(self):
        cfg = self._valid_config()
        del cfg["source_id"]
        ok, errors = validate_event_source_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any("source_id" in e for e in errors))

    def test_invalid_mode_fails(self):
        cfg = self._valid_config()
        cfg["mode"] = "invalid_mode"
        ok, errors = validate_event_source_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any("mode" in e for e in errors))

    def test_non_dict_fails(self):
        ok, errors = validate_event_source_config("not a dict")
        self.assertFalse(ok)

    def test_both_modes_are_valid(self):
        for mode in (MODE_FIXTURE, MODE_LIVE_READ):
            cfg = self._valid_config()
            cfg["mode"] = mode
            ok, errors = validate_event_source_config(cfg)
            self.assertTrue(ok, f"Mode {mode} should be valid but got errors: {errors}")

    def test_failure_category_constants_are_strings(self):
        for const in (FAILURE_SOURCE_NOT_FOUND, FAILURE_SOURCE_DISABLED, FAILURE_CREDENTIALS_MISSING):
            self.assertIsInstance(const, str)
            self.assertTrue(len(const) > 0)


if __name__ == "__main__":
    unittest.main()
