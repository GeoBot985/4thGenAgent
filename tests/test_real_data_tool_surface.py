from __future__ import annotations

import unittest

from runtime.company_store import read_json_table
from runtime.file_tools import file_exists, file_read_json, file_write_json
from runtime.tool_registry import get_tool_spec


class RealDataToolSurfaceTests(unittest.TestCase):
    def test_company_store_rejects_path_traversal(self):
        from runtime.company_store import business_path

        with self.assertRaises(ValueError):
            business_path("../inventory")

    def test_company_store_reads_inventory_from_runtime_data_business(self):
        rows = read_json_table("inventory")
        self.assertTrue(any(row.get("sku") == "SKU-1001" for row in rows))

    def test_file_tools_reject_absolute_path(self):
        with self.assertRaises(ValueError):
            file_read_json("C:/windows/system.ini")

    def test_file_tools_reject_parent_traversal(self):
        with self.assertRaises(ValueError):
            file_exists("../secrets.txt")

    def test_file_read_json_locks_to_runtime_data(self):
        with self.assertRaises(ValueError):
            file_read_json("../runtime_data/business/inventory.json")

    def test_file_write_json_is_registered_as_side_effect_requires_approval(self):
        spec = get_tool_spec("file", "write_json")
        self.assertTrue(spec["side_effect"])
        self.assertTrue(spec["requires_approval"])


if __name__ == "__main__":
    unittest.main()
