from __future__ import annotations

import unittest

from src.operator_presenter import build_demo_view, humanize_state, humanize_step_id


def make_snapshot() -> dict:
    return {
        "active_event": {
            "event_id": "evt-100",
            "source": "callcenter",
            "event_type": "customer_message",
            "payload": {
                "customer_id": "CUST-001",
                "channel": "callcenter",
                "message": "Where is my order ORD-10042?",
            },
        },
        "active_frame": {
            "frame_id": "frame-100",
            "state": "WAITING_FOR_EXECUTE",
            "manifest_id": "customer.message_status_check",
            "inputs": {
                "customer_id": "CUST-001",
                "channel": "callcenter",
                "message": "Where is my order ORD-10042?",
            },
            "outputs": {
                "order_id": "ORD-10042",
                "order": {"status": "shipped"},
                "shipment": {"tracking_reference": "TRK-7788", "estimated_delivery_date": "2026-05-04"},
                "draft_reply": {"body": "Your order ORD-10042 has shipped."},
            },
            "pending_actions": [
                {
                    "action_type": "send_customer_message",
                    "status": "PENDING_APPROVAL",
                    "customer_id": "CUST-001",
                }
            ],
            "validations": [
                {"step_id": "validate_customer_owns_order", "ok": True},
            ],
            "evidence": [
                {
                    "kind": "business_lookup",
                    "datasets": [
                        {"dataset": "orders", "query": {"order_id": "ORD-10042"}, "found": True},
                        {"dataset": "customers", "query": {"customer_id": "CUST-001"}, "found": True},
                        {"dataset": "shipments", "query": {"order_id": "ORD-10042"}, "found": True},
                    ],
                }
            ],
            "steps": [
                {"step_id": "validate_input"},
                {"step_id": "extract_order_id"},
                {"step_id": "lookup_order"},
                {"step_id": "validate_customer_owns_order"},
                {"step_id": "draft_status_reply"},
                {"step_id": "validate_draft_reply"},
                {"step_id": "prepare_pending_send"},
            ],
        },
    }


class OperatorPresenterTests(unittest.TestCase):
    def test_humanize_state_waiting_for_execute(self):
        self.assertEqual(humanize_state("WAITING_FOR_EXECUTE"), "Waiting for approval")

    def test_humanize_known_customer_steps(self):
        self.assertEqual(humanize_step_id("validate_customer_owns_order"), "Confirmed the customer owns the order")

    def test_humanize_unknown_step_id_is_readable(self):
        self.assertEqual(humanize_step_id("custom_weird_step"), "Custom weird step")

    def test_build_demo_view_for_customer_status_snapshot(self):
        view = build_demo_view(make_snapshot(), {"label": "Customer Order Status"})

        self.assertTrue(view["scenario_title"])
        self.assertIn("Customer Order Status", view["scenario_title"])
        self.assertIn("ORD-10042", view["incoming_request"]["message"])
        self.assertEqual(view["incoming_request"]["order_id"], "ORD-10042")
        self.assertTrue(any(step["label"] == "Drafted the customer reply" for step in view["worker_steps"]))
        self.assertIn("ORD-10042", view["business_result"]["body"])
        self.assertIn("TRK-7788", view["business_result"]["body"])
        self.assertTrue(view["approval"]["required"])
        self.assertEqual(view["technical_refs"]["frame_id"], "frame-100")
        self.assertEqual(view["technical_refs"]["manifest_id"], "customer.message_status_check")
        self.assertEqual(view["technical_refs"]["state"], "WAITING_FOR_EXECUTE")


if __name__ == "__main__":
    unittest.main()
