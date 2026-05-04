from __future__ import annotations

import tempfile
import unittest

from runtime.business_data import find_many, find_one, load_business_records, search_records, seed_business_dataset


class BusinessDataHelperTests(unittest.TestCase):
    def test_find_one_returns_matching_customer(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            customer = find_one("customers", "customer_id", "CUST-1001", tmp)
            self.assertIsNotNone(customer)
            self.assertEqual(customer["name"], "Alex")

    def test_find_one_returns_none_for_missing_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            self.assertIsNone(find_one("customers", "customer_id", "MISSING", tmp))

    def test_find_many_returns_order_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            items = find_many("order_items", "order_ref", "ORD-10042", tmp)
            self.assertGreaterEqual(len(items), 1)

    def test_search_records_filters_exact_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_business_dataset(tmp, overwrite=True)
            results = search_records("orders", {"customer_id": "CUST-1001", "status": "shipped"}, tmp)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["order_ref"], "ORD-10042")

    def test_load_missing_business_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_business_records("customers", tmp), [])


if __name__ == "__main__":
    unittest.main()
