from __future__ import annotations

import unittest

from src.operator_scenarios import get_scenario, list_categories, list_scenarios, validate_scenario_definition


class DemoScenarioTests(unittest.TestCase):
    def test_list_scenarios_returns_required_scenarios(self):
        ids = {item["id"] for item in list_scenarios()}
        for required in (
            "customer_status_happy_path",
            "customer_status_approve_execute_dry_run",
            "customer_status_missing_customer",
            "customer_status_missing_order",
            "customer_status_wrong_customer_order",
            "customer_status_unsupported_intent",
            "customer_status_bad_llm_reply",
            "dataset_validation_seed_ok",
            "report_generation_happy_path",
        ):
            self.assertIn(required, ids)

    def test_get_scenario_returns_defensive_copy(self):
        scenario = get_scenario("customer_status_happy_path")
        scenario["label"] = "mutated"
        self.assertNotEqual(get_scenario("customer_status_happy_path")["label"], "mutated")

    def test_list_scenarios_filters_by_category(self):
        negative = list_scenarios("negative_path")
        self.assertTrue(all(item["category"] == "negative_path" for item in negative))

    def test_all_scenarios_have_required_fields(self):
        for scenario in list_scenarios():
            for key in ("id", "label", "category", "description", "expected"):
                self.assertIn(key, scenario)
            if scenario.get("scenario_type") != "dataset_validation":
                for key in ("event_type", "source", "payload"):
                    self.assertIn(key, scenario)

    def test_scenario_definitions_validate_cleanly(self):
        for scenario in list_scenarios():
            self.assertEqual(validate_scenario_definition(scenario), [])


if __name__ == "__main__":
    unittest.main()
