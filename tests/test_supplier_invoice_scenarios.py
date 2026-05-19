from __future__ import annotations

from src.operator_scenarios import get_scenario, list_scenarios


EXPECTED_IDS = {
    "supplier_invoice_match_happy_path",
    "supplier_invoice_match_price_exception",
    "supplier_invoice_match_quantity_exception",
    "supplier_invoice_match_missing_receipt",
    "supplier_invoice_match_missing_po",
    "supplier_invoice_match_duplicate_invoice",
    "supplier_invoice_match_approve_execute_dry_run",
    "supplier_invoice_match_report_generation",
}


def test_supplier_invoice_scenarios_validate():
    scenarios = list_scenarios(category="accounting", include_test_only=False)
    ids = {item["id"] for item in scenarios if str(item.get("id", "")).startswith("supplier_invoice_match_")}
    assert EXPECTED_IDS <= ids


def test_supplier_invoice_scenario_payloads_are_manual_invoice_match():
    scenario = get_scenario("supplier_invoice_match_happy_path")
    assert scenario["event_type"] == "manual.supplier_invoice_match"
    assert scenario["workflow_family"] == "supplier_invoice_matching"
    assert scenario["source"] == "operator_scenario_pack"


def test_supplier_invoice_scenario_approve_execute_dry_run_has_post_actions():
    scenario = get_scenario("supplier_invoice_match_approve_execute_dry_run")
    assert scenario["post_actions"]
    assert scenario["expected"]["final_state"] == "COMPLETED"
