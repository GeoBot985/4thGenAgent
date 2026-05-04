import tempfile
import unittest
from pathlib import Path

from runtime.event_store import intake_and_run_event, intake_event
from runtime.taskframe_reload import load_taskframe


class MockCustomerMessageWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_customer_message_routes_to_manifest(self) -> None:
        event = {
            "event_id": "evt-cust-001",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-1001",
                "channel": "callcenter",
                "message": "Where is my order ORD-10042?",
            },
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "FRAME_CREATED")
        self.assertEqual(result["route_id"], "callcenter.customer_message")
        self.assertEqual(result["manifest_id"], "customer.message_status_check")
        self.assertIsNotNone(result["frame_id"])

    def test_workflow_creates_draft_and_pending_action(self) -> None:
        event = {
            "event_id": "evt-cust-001",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-1001",
                "channel": "callcenter",
                "message": "Where is my order ORD-10042?",
            },
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_and_run_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")
        self.assertEqual(result["outputs"]["order_id"], "ORD-10042")
        self.assertEqual(result["outputs"]["order"]["order_ref"], "ORD-10042")
        self.assertIn("draft_reply", result["outputs"])
        self.assertEqual(len(load_taskframe(result["frame_id"], self.runtime_dir).pending_actions), 1)
        frame = load_taskframe(result["frame_id"], self.runtime_dir)
        self.assertEqual(frame.pending_actions[0]["action_type"], "send_customer_message")
        self.assertEqual(frame.pending_actions[0]["status"], "PENDING_APPROVAL")
        body = result["outputs"]["draft_reply"]["body"]
        self.assertIn("ORD-10042", body)
        self.assertIn("shipped", body)
        for forbidden in ["refund", "compensation", "voucher", "credit", "free"]:
            self.assertNotIn(forbidden, body.lower())

    def test_missing_order_id_fails_validation(self) -> None:
        event = {
            "event_id": "evt-cust-no-order",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-1001",
                "channel": "callcenter",
                "message": "Where is my order?",
            },
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_and_run_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertTrue(any("ORDER_ID_NOT_FOUND" in error for error in result["errors"]))

    def test_unknown_order_fails_validation(self) -> None:
        event = {
            "event_id": "evt-cust-no-order-2",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-1001",
                "channel": "callcenter",
                "message": "Where is my order ORD-99999?",
            },
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_and_run_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertTrue(any("ORDER_NOT_FOUND" in error for error in result["errors"]))

    def test_wrong_customer_fails_validation(self) -> None:
        event = {
            "event_id": "evt-cust-wrong-owner",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-999",
                "channel": "callcenter",
                "message": "Where is my order ORD-10042?",
            },
            "received_at": "2026-05-01T10:00:00Z",
        }
        result = intake_and_run_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertTrue(any("CUSTOMER_ORDER_MISMATCH" in error for error in result["errors"]))

    def test_duplicate_customer_event_does_not_create_second_frame(self) -> None:
        event = {
            "event_id": "evt-cust-dup-001",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-1001",
                "channel": "callcenter",
                "message": "Where is my order ORD-10042?",
            },
            "received_at": "2026-05-01T10:00:00Z",
        }
        first = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        second = intake_event(event, runtime_data_dir=self.runtime_dir, manifest_dir="manifests")
        self.assertTrue(first["ok"])
        self.assertEqual(first["status"], "FRAME_CREATED")
        self.assertTrue(second["ok"])
        self.assertEqual(second["status"], "DUPLICATE_EVENT")
        self.assertEqual(second["frame_id"], first["frame_id"])


if __name__ == "__main__":
    unittest.main()
