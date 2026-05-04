from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.customer_inbox import get_customer_message, reset_customer_inbox, update_customer_message
from runtime.taskframe_reload import load_taskframe
from src.operator_customer_inbox_runner import process_customer_message
from src.operator_demo_runner import run_demo_manifest


class CustomerInboxProcessingTests(unittest.TestCase):
    def test_process_customer_message_happy_path_stages_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            result = process_customer_message("msg_001", runtime_data_dir=tmp, use_local_llm=False)
            message = get_customer_message("msg_001", tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(message["status"], "STAGED_REPLY")
            self.assertTrue(str(message["linked_frame_id"]).startswith("frame_"))
            self.assertTrue(str(message["pending_action_id"]).startswith("pa_"))
            self.assertEqual(result["state"], "WAITING_FOR_EXECUTE")

    def test_process_customer_message_preserves_message_id_in_taskframe_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            result = process_customer_message("msg_001", runtime_data_dir=tmp, use_local_llm=False)
            frame = load_taskframe(result["target_frame_id"], tmp)
            self.assertEqual(frame.trigger.get("message_id"), "msg_001")
            self.assertEqual(frame.inputs.get("message"), "Where is my order ORD-10042?")
            self.assertEqual(frame.inputs.get("customer_id"), "CUST-1001")

    def test_process_customer_message_missing_order_marks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            result = process_customer_message("msg_004", runtime_data_dir=tmp, use_local_llm=False)
            message = get_customer_message("msg_004", tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(message["status"], "FAILED")
            self.assertNotEqual(message.get("failure_reason", ""), "")
            self.assertTrue(message.get("linked_frame_id"))

    def test_process_customer_message_blocks_staged_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            reset_customer_inbox(tmp)
            process_customer_message("msg_001", runtime_data_dir=tmp, use_local_llm=False)
            result = process_customer_message("msg_001", runtime_data_dir=tmp, use_local_llm=False)
            self.assertFalse(result["ok"])
            self.assertIn("status", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
