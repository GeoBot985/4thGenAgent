"""Spec 109 — Operator UI event sources panel tests."""
from __future__ import annotations

import unittest


class TestOperatorDataEventSourcesPanel(unittest.TestCase):

    def test_build_event_sources_panel_is_callable(self):
        from src.operator_data import build_event_sources_panel
        self.assertTrue(callable(build_event_sources_panel))

    def test_build_event_sources_panel_returns_ok_structure(self):
        from src.operator_data import build_event_sources_panel

        panel = build_event_sources_panel()
        self.assertIn("ok", panel)
        self.assertIn("contracts", panel)
        self.assertIn("count", panel)
        self.assertIsInstance(panel["contracts"], list)

    def test_build_event_sources_panel_has_all_builtin_sources(self):
        from src.operator_data import build_event_sources_panel

        panel = build_event_sources_panel()
        source_types = {c.get("source_type") for c in panel.get("contracts", [])}
        for expected in ("operator_ui", "schedule", "customer_inbox", "gmail", "calendar", "sheet", "rpa", "system"):
            self.assertIn(expected, source_types, f"Missing source in panel: {expected}")

    def test_build_event_sources_panel_has_validation(self):
        from src.operator_data import build_event_sources_panel

        panel = build_event_sources_panel()
        self.assertIn("validation", panel)
        self.assertIsInstance(panel["validation"], dict)


class TestEventSourceRegistryInOperatorContext(unittest.TestCase):

    def test_list_event_source_contracts_returns_list(self):
        from runtime.event_source_registry import list_event_source_contracts

        contracts = list_event_source_contracts()
        self.assertIsInstance(contracts, list)
        self.assertGreater(len(contracts), 0)

    def test_get_event_source_contract_returns_contract(self):
        from runtime.event_source_registry import get_event_source_contract

        for source in ("operator_ui", "schedule", "gmail", "system"):
            c = get_event_source_contract(source)
            self.assertIsNotNone(c, f"Contract not found for: {source}")
            self.assertEqual(c.get("source_type"), source)

    def test_validate_all_contracts_passes(self):
        from runtime.event_source_registry import validate_all_event_source_contracts

        result = validate_all_event_source_contracts()
        self.assertTrue(result.get("ok"), f"Validation failed: {result}")


if __name__ == "__main__":
    unittest.main()
