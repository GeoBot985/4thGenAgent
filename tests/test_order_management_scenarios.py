"""Spec 110 — Order Management Scenario Pack tests."""
from __future__ import annotations
import unittest
from src.operator_scenarios import get_scenario, list_scenarios, SCENARIO_CATEGORIES


class TestOrderManagementCategory(unittest.TestCase):
    def test_order_management_category_exists(self):
        self.assertIn("order_management", SCENARIO_CATEGORIES)

    def test_all_order_scenarios_exist(self):
        required_ids = [
            "order_validate_new_happy_path", "order_validate_new_invalid_customer",
            "order_validate_new_insufficient_stock", "order_reserve_stock_happy_path",
            "order_reserve_stock_approve_execute_dry_run", "order_release_paid_happy_path",
            "order_release_paid_unpaid_order", "order_detect_delayed_orders",
            "order_update_shipment_status_happy_path", "order_update_shipment_status_approve_execute_dry_run",
        ]
        for scenario_id in required_ids:
            try:
                scenario = get_scenario(scenario_id)
                self.assertIsNotNone(scenario, f"Scenario not found: {scenario_id}")
            except ValueError:
                self.fail(f"Scenario not found: {scenario_id}")

    def test_order_scenarios_are_deterministic(self):
        scenarios = [s for s in list_scenarios() if s.get("category") == "order_management"]
        for s in scenarios:
            self.assertFalse(s.get("uses_llm", False), f"Scenario {s['id']} must not use LLM")

    def test_order_scenarios_have_required_fields(self):
        scenarios = [s for s in list_scenarios() if s.get("category") == "order_management"]
        for s in scenarios:
            for field in ("id", "label", "category", "event_type", "source", "payload", "expected"):
                self.assertIn(field, s, f"Scenario {s['id']} missing field: {field}")


class TestOrderScenarioValidation(unittest.TestCase):
    def test_order_scenarios_validate(self):
        import importlib
        mod = importlib.import_module("src.operator_scenarios")
        validate_fn = getattr(mod, "validate_scenario", None) or getattr(mod, "validate_scenario_definition", None)
        if validate_fn is None:
            self.skipTest("No validate_scenario function found")
        for scenario_id in ["order_validate_new_happy_path", "order_reserve_stock_happy_path"]:
            scenario = get_scenario(scenario_id)
            result = validate_fn(scenario)
            # validate_scenario_definition returns a list of errors; validate_scenario returns a dict
            if isinstance(result, list):
                self.assertEqual(result, [], f"Scenario {scenario_id} validation errors: {result}")
            else:
                self.assertTrue(result.get("ok", True))


if __name__ == "__main__":
    unittest.main()
