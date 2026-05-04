from __future__ import annotations

import unittest

from runtime.business_store import get_customer, get_order, get_payment, get_shipment, search_inventory, search_orders


class BusinessDataStoreTests(unittest.TestCase):
    def test_search_orders_finds_seed_order(self):
        results = search_orders(order_id="ORD-10042")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["customer_id"], "CUST-1001")

    def test_get_order_returns_seed_order(self):
        order = get_order("ORD-10042")
        self.assertIsNotNone(order)
        self.assertEqual(order["status"], "shipped")

    def test_get_customer_returns_seed_customer(self):
        customer = get_customer("CUST-1001")
        self.assertIsNotNone(customer)
        self.assertEqual(customer["name"], "Alex")

    def test_get_shipment_returns_seed_shipment(self):
        shipment = get_shipment("ORD-10042")
        self.assertIsNotNone(shipment)
        self.assertEqual(shipment["tracking_ref"], "TRK-778899")

    def test_get_payment_returns_seed_payment(self):
        payment = get_payment("ORD-10042")
        self.assertIsNotNone(payment)
        self.assertEqual(payment["status"], "matched")

    def test_search_inventory_below_reorder(self):
        results = search_inventory(below_reorder=True)
        self.assertTrue(any(item["sku"] == "SKU-LAMP-01" for item in results))
        self.assertTrue(any(item["sku"] == "SKU-CHAIR-01" for item in results))


if __name__ == "__main__":
    unittest.main()
