from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.business_data import load_business_records, seed_business_dataset, validate_business_dataset


class BusinessDatasetValidationTests(unittest.TestCase):
    def test_validate_business_dataset_seed_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            result = validate_business_dataset(tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])

    def test_validate_business_dataset_detects_order_customer_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            path = Path(tmp) / "business" / "orders.json"
            orders = json.loads(path.read_text(encoding="utf-8"))
            orders[0]["customer_id"] = "CUST-9999"
            path.write_text(json.dumps(orders, indent=2), encoding="utf-8")
            result = validate_business_dataset(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Order customer missing" in item for item in result["errors"]))

    def test_validate_business_dataset_detects_bad_order_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            path = Path(tmp) / "business" / "orders.json"
            orders = json.loads(path.read_text(encoding="utf-8"))
            orders[0]["total_amount"] = 1.0
            path.write_text(json.dumps(orders, indent=2), encoding="utf-8")
            result = validate_business_dataset(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Order total mismatch" in item for item in result["errors"]))

    def test_validate_business_dataset_allows_explicit_unmatched_payment_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            path = Path(tmp) / "business" / "payments.json"
            payments = json.loads(path.read_text(encoding="utf-8"))
            payments.append(
                {
                    "payment_id": "PAY-X",
                    "order_ref": "ORD-MISSING",
                    "customer_id": "CUST-1001",
                    "amount": 1.0,
                    "currency": "ZAR",
                    "status": "unmatched_order",
                    "paid_at": "2026-05-01T10:00:00Z",
                    "provider_ref": "BANK-X",
                }
            )
            path.write_text(json.dumps(payments, indent=2), encoding="utf-8")
            result = validate_business_dataset(tmp)
            self.assertTrue(result["ok"])

    def test_validate_business_dataset_detects_inventory_available_stock_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            path = Path(tmp) / "business" / "inventory.json"
            inventory = json.loads(path.read_text(encoding="utf-8"))
            inventory[0]["available_stock"] = 999
            path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
            result = validate_business_dataset(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Inventory available stock mismatch" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
