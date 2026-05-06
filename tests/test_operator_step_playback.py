from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from src.operator_data import build_footer_text, group_events_for_queue, load_manifest
from src.operator_playback import build_playback_timeline, build_playback_view


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = ROOT / "src" / "operator_ui.py"
PLAYBACK_SOURCE = ROOT / "src" / "operator_playback.py"


def make_snapshot() -> dict:
    return {
        "active_event": {
            "event_id": "evt-ui-demo-1234",
            "source": "callcenter",
            "event_type": "customer_message",
            "status": "FRAME_CREATED",
            "linked_frame_id": "frame_123",
        },
        "active_frame": {
            "frame_id": "frame_123",
            "state": "WAITING_FOR_EXECUTE",
            "manifest_id": "customer.message_status_check",
            "trigger": {"route_id": "callcenter.customer_message"},
            "outputs": {
                "order_id": "ORD-10042",
                "order": {"status": "shipped"},
                "customer": {"customer_id": "CUST-001"},
                "shipment": {"shipment_id": "SHP-1"},
                "payment": {"payment_id": "PAY-1"},
                "business_lookups": [{"dataset": "orders", "query": {"order_id": "ORD-10042"}, "found": True}],
                "draft_reply": {"body": "Your order ORD-10042 has shipped."},
            },
            "validations": [
                {"step_id": "validate_customer_owns_order", "ok": True},
                {"step_id": "validate_draft_reply", "ok": True},
            ],
            "pending_actions": [
                {
                    "action_type": "send_customer_message",
                    "status": "PENDING_APPROVAL",
                    "customer_id": "CUST-001",
                    "channel": "callcenter",
                    "body": "Your order ORD-10042 has shipped.",
                }
            ],
            "evidence": [
                {
                    "kind": "business_lookup",
                    "step_id": "lookup_order",
                    "datasets": [
                        {"dataset": "orders", "query": {"order_id": "ORD-10042"}, "found": True},
                        {"dataset": "customers", "query": {"customer_id": "CUST-001"}, "found": True},
                        {"dataset": "shipments", "query": {"order_id": "ORD-10042"}, "found": True},
                        {"dataset": "payments", "query": {"order_id": "ORD-10042"}, "found": True},
                    ],
                }
            ],
            "steps": [{"step_id": step_id} for step_id in (
                "validate_input",
                "extract_order_id",
                "lookup_order",
                "validate_customer_owns_order",
                "draft_status_reply",
                "validate_draft_reply",
                "prepare_pending_send",
            )],
        },
        "outputs": {},
        "validations": [],
        "pending_actions": [],
        "events": [],
        "frames_by_id": {},
    }


class OperatorStepPlaybackTests(unittest.TestCase):
    def test_playback_module_imports(self):
        module = importlib.import_module("src.operator_playback")
        self.assertTrue(hasattr(module, "build_playback_timeline"))
        self.assertTrue(hasattr(module, "build_playback_view"))

    def test_timeline_builds_in_expected_order(self):
        timeline = build_playback_timeline(make_snapshot())
        self.assertEqual(
            [item["title"] for item in timeline],
            [
                "event_received",
                "route_resolved",
                "taskframe_created",
                "validate_input",
                "extract_order_id",
                "lookup_order",
                "validate_customer_owns_order",
                "draft_status_reply",
                "validate_draft_reply",
                "prepare_pending_send",
                "complete",
            ],
        )
        self.assertEqual(timeline[4]["label"], "Extracted the order number")
        self.assertEqual(timeline[9]["label"], "Prepared the message for approval")

    def test_playback_view_reveals_progressively(self):
        snapshot = make_snapshot()
        timeline = build_playback_timeline(snapshot)

        extract_index = next(i for i, item in enumerate(timeline) if item["title"] == "extract_order_id")
        draft_index = next(i for i, item in enumerate(timeline) if item["title"] == "draft_status_reply")
        pending_index = next(i for i, item in enumerate(timeline) if item["title"] == "prepare_pending_send")

        extract_view = build_playback_view(snapshot, timeline, extract_index)
        self.assertIn("order_id", extract_view["outputs"])
        self.assertNotIn("draft_reply", extract_view["outputs"])
        self.assertEqual(extract_view["pending_actions"], [])
        self.assertEqual(extract_view["current_label"], "Extracted the order number")

        draft_view = build_playback_view(snapshot, timeline, draft_index)
        self.assertIn("order_id", draft_view["outputs"])
        self.assertIn("draft_reply", draft_view["outputs"])
        self.assertEqual(draft_view["pending_actions"], [])
        self.assertEqual(draft_view["visible_step_labels"][-1], "Drafted the customer reply")

        pending_view = build_playback_view(snapshot, timeline, pending_index)
        self.assertGreaterEqual(len(pending_view["pending_actions"]), 1)
        self.assertEqual(pending_view["pending_actions"][0]["action_type"], "send_customer_message")
        self.assertEqual(pending_view["pending_actions"][0]["status"], "PENDING_APPROVAL")
        self.assertEqual(pending_view["current_label"], "Prepared the message for approval")

    def test_skip_to_end_view_shows_full_snapshot(self):
        snapshot = make_snapshot()
        timeline = build_playback_timeline(snapshot)
        view = build_playback_view(snapshot, timeline, len(timeline) - 1)

        self.assertIn("draft_reply", view["outputs"])
        self.assertGreaterEqual(len(view["pending_actions"]), 1)
        self.assertTrue(view["validations"])
        self.assertEqual(view["frame"]["state"], "WAITING_FOR_EXECUTE")

    def test_footer_binding_helper(self):
        footer = build_footer_text({"active_frame": {"frame_id": "frame-123", "pending_actions": [1]}}, "running")
        self.assertIn("Active Frame: frame-123", footer)
        self.assertIn("Pending Actions: 1", footer)
        self.assertIn("Playback: running", footer)

    def test_manifest_loads_by_id(self):
        manifest = load_manifest("customer.message_status_check")
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["id"], "customer.message_status_check")

    def test_queue_grouping_uses_frame_state(self):
        events = [
            {"event_id": "evt-1", "source": "callcenter", "event_type": "customer_message", "status": "FRAME_CREATED", "linked_frame_id": "frame-1"},
        ]
        frames = {"frame-1": {"state": "WAITING_FOR_EXECUTE"}}

        grouped = group_events_for_queue(events, frames)

        self.assertEqual(len(grouped["Waiting for Execute"]), 1)
        self.assertEqual(len(grouped["Incoming Events"]), 0)

    def test_playback_detail_includes_manifest_step(self):
        snapshot = make_snapshot()
        timeline = build_playback_timeline(snapshot)
        lookup_index = next(i for i, item in enumerate(timeline) if item["title"] == "lookup_order")
        view = build_playback_view(snapshot, timeline, lookup_index)

        detail = view["selected_detail"]
        self.assertEqual(detail["manifest_step"]["step_id"], "lookup_order")
        self.assertEqual(detail["manifest_step"]["kind"], "mock_order_lookup")
        runtime_result = detail["runtime_step_result"]
        self.assertTrue(runtime_result["evidence"])
        self.assertTrue(any(item.get("dataset") == "orders" for item in runtime_result["evidence"]))

    def test_playback_detail_includes_event(self):
        snapshot = make_snapshot()
        timeline = build_playback_timeline(snapshot)
        view = build_playback_view(snapshot, timeline, 0)

        detail = view["selected_detail"]
        self.assertEqual(detail["event"]["event_id"], "evt-ui-demo-1234")
        self.assertEqual(detail["event"]["source"], "callcenter")
        self.assertEqual(detail["event"]["event_type"], "customer_message")
        self.assertIn("payload", detail["event"])

    def test_ui_sources_avoid_blocking_sleep(self):
        for path in (UI_SOURCE, PLAYBACK_SOURCE):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("time.sleep", source)
            self.assertNotIn("sleep(", source)
        self.assertIn(".after(", UI_SOURCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
