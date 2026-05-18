"""Spec 110 — Order Management Report tests."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path


class TestOrderManagementReports(unittest.TestCase):
    def test_order_validate_scenarios_generate_evidence(self):
        from runtime.event_store import intake_and_run_event
        with tempfile.TemporaryDirectory() as tmp:
            event = {
                "event_id": "evt-report-validate-001",
                "source": "operator_scenario_pack",
                "event_type": "manual.order_validate_new",
                "payload": {"customer_id": "CUST-1001", "items": [{"sku": "SKU-DESK-01", "quantity": 1}]},
                "received_at": "2026-05-18T00:00:00Z",
            }
            result = intake_and_run_event(event, runtime_data_dir=tmp, manifest_dir="manifests", routes_path="config/event_routes.json")
            self.assertIsNotNone(result)
            self.assertIn("frame_id", result)

    def test_order_reserve_stock_scenarios_generate_frame(self):
        from runtime.event_store import intake_and_run_event
        with tempfile.TemporaryDirectory() as tmp:
            event = {
                "event_id": "evt-report-reserve-001",
                "source": "operator_scenario_pack",
                "event_type": "manual.order_reserve_stock",
                "payload": {"order_ref": "ORD-10050", "customer_id": "CUST-1001", "items": [{"sku": "SKU-DESK-01", "quantity": 1}]},
                "received_at": "2026-05-18T00:00:00Z",
            }
            result = intake_and_run_event(event, runtime_data_dir=tmp, manifest_dir="manifests", routes_path="config/event_routes.json")
            self.assertIsNotNone(result.get("frame_id"))


if __name__ == "__main__":
    unittest.main()
