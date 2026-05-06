from __future__ import annotations

import unittest

from src.operator_presenter import build_demo_view


def make_waiting_snapshot() -> dict:
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
            "validations": [{"step_id": "validate_customer_owns_order", "ok": True}],
            "evidence": [{"kind": "business_lookup", "datasets": [{"dataset": "orders", "query": {"order_id": "ORD-10042"}, "found": True}]}],
            "steps": [{"step_id": "validate_input"}, {"step_id": "extract_order_id"}, {"step_id": "lookup_order"}],
        },
    }


def make_completed_snapshot() -> dict:
    snapshot = make_waiting_snapshot()
    snapshot["active_frame"] = dict(snapshot["active_frame"], state="COMPLETED", pending_actions=[])
    return snapshot


class OperatorGuidedDemoFlowTests(unittest.TestCase):
    def test_guided_flow_before_run_points_to_run_demo(self):
        view = build_demo_view({}, None)

        self.assertEqual(view["next_action"]["primary_button"], "Run selected demo")
        self.assertTrue(view["current_run_summary"].startswith("Current run:"))
        self.assertEqual(view["guided_flow"][0]["status"], "ready")
        self.assertEqual(view["guided_flow"][1]["status"], "next")

    def test_guided_flow_waiting_for_execute_points_to_approval(self):
        view = build_demo_view(make_waiting_snapshot(), {"frame_id": "frame-100", "state": "WAITING_FOR_EXECUTE"})

        self.assertIn("Waiting for approval", view["approval"]["label"])
        self.assertEqual(view["next_action"]["primary_button"], "Approve & execute dry run")
        self.assertEqual(view["next_action"]["secondary_button"], "Reject")
        self.assertEqual(view["guided_flow"][3]["status"], "attention")
        self.assertIn("Current run:", view["current_run_summary"])

    def test_guided_flow_completed_points_to_evidence_generation(self):
        view = build_demo_view(make_completed_snapshot(), {"frame_id": "frame-100", "state": "COMPLETED"})

        self.assertEqual(view["next_action"]["primary_button"], "Generate evidence for this run")
        self.assertEqual(view["guided_flow"][4]["status"], "available")

    def test_guided_flow_with_generated_report_points_to_open_evidence(self):
        artifact_state = {
            "frame_id": "frame-100",
            "report_frame_id": "frame-100",
            "has_active_run": True,
            "report_generated": True,
            "evidence_generated": True,
            "paths": {
                "report_markdown": "/tmp/run_report.md",
                "report_html": "/tmp/run_report.html",
                "evidence_bundle": "/tmp/evidence_bundle.json",
                "taskframe_json": "/tmp/taskframe.json",
                "output_dir": "/tmp",
            },
            "messages": [],
            "report_result": {"frame_id": "frame-100"},
        }
        view = build_demo_view(make_completed_snapshot(), {"frame_id": "frame-100", "state": "COMPLETED", "report_result": {"frame_id": "frame-100"}}, artifact_state)

        self.assertEqual(view["next_action"]["primary_button"], "Open evidence for this run")
        self.assertEqual(view["guided_flow"][5]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
