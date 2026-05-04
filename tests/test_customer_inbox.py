from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.customer_inbox import (
    get_customer_message,
    get_inbox_path,
    load_customer_messages,
    reset_customer_inbox,
    save_customer_messages,
    seed_customer_inbox,
    update_customer_message,
)


class CustomerInboxTests(unittest.TestCase):
    def test_seed_customer_inbox_creates_seed_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = seed_customer_inbox(tmp, overwrite=True)
            path = get_inbox_path(tmp)
            messages = load_customer_messages(tmp)
            self.assertTrue(path.is_file())
            self.assertGreaterEqual(len(messages), 4)
            self.assertTrue(any(m.get("message_id") == "msg_001" for m in messages))
            self.assertTrue(all(m.get("status") == "NEW" for m in messages))
            self.assertTrue(result["seeded"])

    def test_load_customer_messages_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_customer_messages(tmp), [])

    def test_update_customer_message_sets_status_and_frame_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed_customer_inbox(tmp, overwrite=True)
            updated = update_customer_message("msg_001", {"status": "PROCESSING", "linked_frame_id": "frame_123"}, tmp)
            self.assertEqual(updated["status"], "PROCESSING")
            self.assertEqual(updated["linked_frame_id"], "frame_123")
            self.assertEqual(updated["customer_id"], "CUST-1001")

    def test_save_customer_messages_rejects_duplicate_message_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_customer_messages([{"message_id": "a", "status": "NEW"}, {"message_id": "a", "status": "NEW"}], tmp)

    def test_save_customer_messages_rejects_unknown_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_customer_messages([{"message_id": "a", "status": "MYSTERY"}], tmp)


if __name__ == "__main__":
    unittest.main()
