"""Spec 110 — Order Management Tools tests."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from runtime.order_management_tools import (
    order_validate_new, order_prepare_stock_reservation, order_execute_stock_reservation,
    order_check_payment_status, order_prepare_release_paid_order, order_execute_release_paid_order,
    order_detect_delayed_orders, order_prepare_shipment_status_update, order_execute_shipment_status_update,
)

RUNTIME_ROOT = "runtime_data"  # uses the repo's seeded business data


class TestOrderValidateNew(unittest.TestCase):
    def test_happy_path(self):
        result = order_validate_new("CUST-1001", [{"sku": "SKU-DESK-01", "quantity": 1}], runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertTrue(result["valid"])

    def test_rejects_missing_customer(self):
        result = order_validate_new("CUST-9999", [{"sku": "SKU-DESK-01", "quantity": 1}], runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["valid"])

    def test_rejects_empty_items(self):
        result = order_validate_new("CUST-1001", [], runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["valid"])

    def test_rejects_unknown_sku(self):
        result = order_validate_new("CUST-1001", [{"sku": "SKU-UNKNOWN-999", "quantity": 1}], runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["valid"])

    def test_rejects_insufficient_stock(self):
        result = order_validate_new("CUST-1001", [{"sku": "SKU-CHAIR-01", "quantity": 2}], runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["valid"])


class TestPrepareStockReservation(unittest.TestCase):
    def test_returns_pending_action_shape(self):
        items = [{"sku": "SKU-DESK-01", "quantity": 1}]
        result = order_prepare_stock_reservation("ORD-10050", items, runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action_type"], "reserve_stock")
        self.assertEqual(result["tool"], "order/execute_stock_reservation")
        self.assertIn("reservation_lines", result)


class TestExecuteStockReservation(unittest.TestCase):
    def test_dry_run_does_not_mutate_inventory(self):
        lines = [{"sku": "SKU-DESK-01", "quantity": 1, "before_stock": 10, "after_stock": 9}]
        result = order_execute_stock_reservation("ORD-10050", reservation_lines=lines, dry_run=True, runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        # Verify actual inventory was not mutated
        from runtime.business_store import search_inventory
        inv = search_inventory(sku="SKU-DESK-01", runtime_root=RUNTIME_ROOT)
        self.assertEqual(inv[0]["available_stock"], 10)

    def test_live_mode_blocked(self):
        result = order_execute_stock_reservation("ORD-10050", dry_run=False, runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["ok"])


class TestCheckPaymentStatus(unittest.TestCase):
    def test_paid_order_can_release(self):
        result = order_check_payment_status("ORD-10052", runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertTrue(result["can_release"])

    def test_unpaid_order_cannot_release(self):
        result = order_check_payment_status("ORD-10053", runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertFalse(result["can_release"])


class TestPrepareReleasePaidOrder(unittest.TestCase):
    def test_requires_paid_order(self):
        result = order_prepare_release_paid_order("ORD-10052", runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool"], "order/execute_release_paid_order")

    def test_fails_unpaid_order(self):
        result = order_prepare_release_paid_order("ORD-10053", runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["ok"])


class TestExecuteReleasePaidOrder(unittest.TestCase):
    def test_dry_run_returns_before_after(self):
        result = order_execute_release_paid_order("ORD-10052", dry_run=True, runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertIn("before_status", result)
        self.assertIn("after_status", result)


class TestDetectDelayedOrders(unittest.TestCase):
    def test_returns_expected_delayed_order(self):
        result = order_detect_delayed_orders(days_overdue=2, runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        order_refs = [o.get("order_ref") for o in result.get("delayed_orders", [])]
        self.assertIn("ORD-10054", order_refs)

    def test_allows_empty_result(self):
        result = order_detect_delayed_orders(days_overdue=9999, runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertIsInstance(result["delayed_orders"], list)


class TestPrepareShipmentStatusUpdate(unittest.TestCase):
    def test_rejects_unknown_status(self):
        result = order_prepare_shipment_status_update("ORD-10055", "invalid_status", runtime_root=RUNTIME_ROOT)
        self.assertFalse(result["ok"])

    def test_accepts_valid_status(self):
        result = order_prepare_shipment_status_update("ORD-10055", "shipped", "TRK-999002", runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool"], "order/execute_shipment_status_update")


class TestExecuteShipmentStatusUpdate(unittest.TestCase):
    def test_dry_run_returns_before_after(self):
        result = order_execute_shipment_status_update("ORD-10055", "shipped", "TRK-999002", dry_run=True, runtime_root=RUNTIME_ROOT)
        self.assertTrue(result["ok"])
        self.assertIn("before_status", result)
        self.assertIn("after_status", result)


if __name__ == "__main__":
    unittest.main()
