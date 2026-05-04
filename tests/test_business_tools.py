from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import tools.workspace_tools as tools
from runtime.business_data import seed_business_dataset


class BusinessToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tempdir.name)
        self.runtime_root = Path(self.tempdir.name)
        seed_business_dataset("runtime_data", overwrite=True)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        self.tempdir.cleanup()

    def test_customer_read_tool_returns_customer(self):
        result = tools.customer_read("CUST-1001")
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["customer_id"], "CUST-1001")

    def test_order_read_tool_returns_order(self):
        result = tools.order_read("ORD-10042")
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["customer_id"], "CUST-1001")

    def test_order_read_tool_missing_order_fails(self):
        result = tools.order_read("ORD-MISSING")
        self.assertFalse(result.ok)
        self.assertIsNone(result.payload)

    def test_order_items_list_tool_returns_items(self):
        result = tools.order_items_list("ORD-10042")
        self.assertTrue(result.ok)
        self.assertGreaterEqual(len(result.payload), 1)

    def test_shipment_read_tool_returns_shipment(self):
        result = tools.shipment_read("ORD-10042")
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["shipment_id"], "SHIP-9001")

    def test_inventory_search_low_stock_returns_lamp_and_chair(self):
        result = tools.inventory_search_low_stock()
        self.assertTrue(result.ok)
        skus = {item["sku"] for item in result.payload}
        self.assertIn("SKU-LAMP-01", skus)
        self.assertIn("SKU-CHAIR-01", skus)

    def test_purchase_order_search_open_by_sku_detects_existing_open_po(self):
        result = tools.purchase_order_search_open_by_sku("SKU-LAMP-01")
        self.assertTrue(result.ok)
        self.assertTrue(any(item["po_id"] == "PO-5001" for item in result.payload))

    def test_supplier_search_active_excludes_inactive_supplier(self):
        result = tools.supplier_search_active()
        self.assertTrue(result.ok)
        supplier_ids = {item["supplier_id"] for item in result.payload}
        self.assertNotIn("SUP-004", supplier_ids)


if __name__ == "__main__":
    unittest.main()
