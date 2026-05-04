import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.errors import MemoryKeyError, MemoryStoreError
from runtime.memory_store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_store_creates_file_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_store.json"
            store = MemoryStore(path)

            data = store.load()

            self.assertTrue(path.exists())
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["items"], {})

    def test_set_stores_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")

            result = store.set("supplier.ABC.preferred_channel", "email")

            self.assertTrue(result.ok)
            self.assertTrue(store.exists("supplier.ABC.preferred_channel"))

    def test_set_updates_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            with patch("runtime.memory_store.utc_now", side_effect=["2026-04-30T20:00:00Z", "2026-04-30T21:00:00Z"]):
                first = store.set("supplier.ABC.preferred_channel", "email")
                second = store.set("supplier.ABC.preferred_channel", "whatsapp")

            data = store.load()
            item = data["items"]["supplier.ABC.preferred_channel"]
            self.assertEqual(item["value"], "whatsapp")
            self.assertEqual(item["created_at"], first.metadata.get("created_at", item["created_at"]))
            self.assertEqual(second.value, "whatsapp")

    def test_get_returns_found_true_for_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email")

            result = store.get("supplier.ABC.preferred_channel")

            self.assertTrue(result.found)
            self.assertEqual(result.value, "email")

    def test_get_returns_found_false_for_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")

            result = store.get("supplier.ABC.preferred_channel")

            self.assertFalse(result.found)
            self.assertIsNone(result.value)

    def test_list_returns_all_keys_with_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email")
            store.set("supplier.ABC.lead_time_days", 5)
            store.set("family.calendar.default", "Family")

            result = store.list("supplier.ABC.")

            self.assertEqual(result.metadata["count"], 2)
            self.assertEqual([item["key"] for item in result.items], ["supplier.ABC.lead_time_days", "supplier.ABC.preferred_channel"])

    def test_list_returns_empty_list_when_no_prefix_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email")

            result = store.list("family.")

            self.assertEqual(result.items, [])
            self.assertEqual(result.metadata["count"], 0)

    def test_exists_returns_true_for_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email")

            self.assertTrue(store.exists("supplier.ABC.preferred_channel"))

    def test_exists_returns_false_for_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")

            self.assertFalse(store.exists("supplier.ABC.preferred_channel"))

    def test_invalid_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")

            with self.assertRaises(MemoryKeyError):
                store.set("supplier ABC", "email")

    def test_empty_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")

            with self.assertRaises(MemoryKeyError):
                store.get("")

    def test_non_json_serializable_value_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")

            with self.assertRaises(MemoryStoreError):
                store.set("supplier.ABC.preferred_channel", object())

    def test_metadata_is_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email", metadata={"source": "manifest", "frame_id": "tf_123"})

            data = store.load()
            self.assertEqual(data["items"]["supplier.ABC.preferred_channel"]["metadata"]["frame_id"], "tf_123")

    def test_created_at_remains_stable_on_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            with patch("runtime.memory_store.utc_now", side_effect=["2026-04-30T20:00:00Z", "2026-04-30T21:00:00Z"]):
                store.set("supplier.ABC.preferred_channel", "email")
                store.set("supplier.ABC.preferred_channel", "whatsapp")

            data = store.load()
            item = data["items"]["supplier.ABC.preferred_channel"]
            self.assertEqual(item["created_at"], "2026-04-30T20:00:00Z")
            self.assertEqual(item["updated_at"], "2026-04-30T21:00:00Z")

    def test_updated_at_changes_on_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            with patch("runtime.memory_store.utc_now", side_effect=["2026-04-30T20:00:00Z", "2026-04-30T21:00:00Z"]):
                store.set("supplier.ABC.preferred_channel", "email")
                store.set("supplier.ABC.preferred_channel", "whatsapp")

            data = store.load()
            item = data["items"]["supplier.ABC.preferred_channel"]
            self.assertNotEqual(item["created_at"], item["updated_at"])


if __name__ == "__main__":
    unittest.main()
