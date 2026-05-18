"""Spec 109 — Event Source Contracts tests."""
from __future__ import annotations

import unittest

from runtime.event_source_contracts import (
    DELIVERY_MODES,
    SIDE_EFFECT_LEVELS,
    SOURCE_TYPES,
    build_event_source_contract,
    validate_contract_shape,
)


class TestSourceTypeConstants(unittest.TestCase):

    def test_all_eight_source_types_defined(self):
        expected = {"operator_ui", "schedule", "customer_inbox", "gmail", "calendar", "sheet", "rpa", "system"}
        self.assertEqual(set(SOURCE_TYPES), expected)

    def test_delivery_modes_defined(self):
        for mode in ("push", "pull", "polling"):
            self.assertIn(mode, DELIVERY_MODES)

    def test_side_effect_levels_defined(self):
        for level in ("none", "low", "medium", "high"):
            self.assertIn(level, SIDE_EFFECT_LEVELS)


class TestBuildEventSourceContract(unittest.TestCase):

    def _make_contract(self, **overrides):
        defaults = dict(
            source_type="operator_ui",
            display_name="Operator UI",
            description="Test source.",
            delivery_mode="push",
            side_effect_level="none",
        )
        defaults.update(overrides)
        return build_event_source_contract(**defaults)

    def test_contract_has_all_canonical_fields(self):
        c = self._make_contract()
        for key in ("source_type", "display_name", "description", "delivery_mode", "side_effect_level",
                    "required_payload_fields", "optional_payload_fields", "allowed_event_types", "metadata"):
            self.assertIn(key, c, f"Missing key: {key}")

    def test_required_payload_fields_defaults_to_empty_list(self):
        c = self._make_contract()
        self.assertIsInstance(c["required_payload_fields"], list)

    def test_optional_payload_fields_defaults_to_empty_list(self):
        c = self._make_contract()
        self.assertIsInstance(c["optional_payload_fields"], list)

    def test_allowed_event_types_defaults_to_empty_list(self):
        c = self._make_contract()
        self.assertIsInstance(c["allowed_event_types"], list)

    def test_metadata_defaults_to_empty_dict(self):
        c = self._make_contract()
        self.assertIsInstance(c["metadata"], dict)

    def test_provided_values_are_stored(self):
        c = self._make_contract(
            required_payload_fields=["message_id"],
            optional_payload_fields=["channel"],
            allowed_event_types=["manual.*"],
        )
        self.assertIn("message_id", c["required_payload_fields"])
        self.assertIn("channel", c["optional_payload_fields"])
        self.assertIn("manual.*", c["allowed_event_types"])


class TestValidateContractShape(unittest.TestCase):

    def _valid_contract(self):
        return build_event_source_contract(
            source_type="test_source",
            display_name="Test",
            description="Test.",
            delivery_mode="push",
            side_effect_level="none",
        )

    def test_valid_contract_passes(self):
        ok, errors = validate_contract_shape(self._valid_contract())
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_missing_source_type_fails(self):
        c = self._valid_contract()
        c["source_type"] = ""
        ok, errors = validate_contract_shape(c)
        self.assertFalse(ok)
        self.assertTrue(any("source_type" in e for e in errors))

    def test_invalid_delivery_mode_fails(self):
        c = self._valid_contract()
        c["delivery_mode"] = "invalid_mode"
        ok, errors = validate_contract_shape(c)
        self.assertFalse(ok)

    def test_invalid_side_effect_level_fails(self):
        c = self._valid_contract()
        c["side_effect_level"] = "extreme"
        ok, errors = validate_contract_shape(c)
        self.assertFalse(ok)

    def test_non_list_required_payload_fields_fails(self):
        c = self._valid_contract()
        c["required_payload_fields"] = "not_a_list"
        ok, errors = validate_contract_shape(c)
        self.assertFalse(ok)

    def test_non_dict_input_fails(self):
        ok, errors = validate_contract_shape("not_a_dict")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
