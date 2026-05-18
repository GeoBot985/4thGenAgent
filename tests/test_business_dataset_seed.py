from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.business_data import reset_business_dataset, seed_business_dataset


REQUIRED_FILES = [
    "customers.json",
    "customer_messages.json",
    "orders.json",
    "order_items.json",
    "shipments.json",
    "payments.json",
    "inventory.json",
    "suppliers.json",
    "purchase_orders.json",
    "supplier_invoices.json",
    "dataset_manifest.json",
]


class BusinessDatasetSeedTests(unittest.TestCase):
    def test_seed_business_dataset_writes_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = seed_business_dataset(tmp, overwrite=True)
            business_dir = Path(tmp) / "business"
            self.assertTrue(result["ok"])
            for name in REQUIRED_FILES:
                self.assertTrue((business_dir / name).is_file(), name)

    def test_seed_business_dataset_returns_record_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = seed_business_dataset(tmp, overwrite=True)
            self.assertEqual(result["dataset_version"], 2)
            self.assertEqual(result["record_counts"]["customers"], 5)
            self.assertEqual(result["record_counts"]["customer_messages"], 8)
            self.assertEqual(result["record_counts"]["orders"], 14)
            self.assertEqual(result["record_counts"]["order_items"], 18)
            self.assertEqual(result["record_counts"]["shipments"], 7)
            self.assertEqual(result["record_counts"]["payments"], 9)
            self.assertEqual(result["record_counts"]["inventory"], 8)
            self.assertEqual(result["record_counts"]["suppliers"], 4)
            self.assertEqual(result["record_counts"]["purchase_orders"], 4)
            self.assertEqual(result["record_counts"]["supplier_invoices"], 4)

    def test_seed_business_dataset_does_not_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            business_dir = Path(tmp) / "business"
            business_dir.mkdir(parents=True, exist_ok=True)
            sentinel = business_dir / "customers.json"
            sentinel.write_text(json.dumps([{"customer_id": "SENTINEL"}]), encoding="utf-8")
            seed_business_dataset(tmp, overwrite=False)
            self.assertIn("SENTINEL", sentinel.read_text(encoding="utf-8"))

    def test_reset_business_dataset_overwrites_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            business_dir = Path(tmp) / "business"
            customers = business_dir / "customers.json"
            customers.write_text(json.dumps([{"customer_id": "BROKEN"}]), encoding="utf-8")
            reset_business_dataset(tmp)
            data = json.loads(customers.read_text(encoding="utf-8"))
            self.assertTrue(any(item.get("customer_id") == "CUST-1001" for item in data))


if __name__ == "__main__":
    unittest.main()
