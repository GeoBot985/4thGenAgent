from __future__ import annotations

import unittest
from pathlib import Path

from src.operator_data import build_selected_detail


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "operator_ui.py"


def make_snapshot() -> dict:
    return {
        "active_event": {
            "event_id": "evt-ui-demo-1234",
            "source": "callcenter",
            "event_type": "customer_message",
            "received_at": "2026-05-01T10:00:00Z",
            "duplicate": False,
            "linked_frame_id": "frame_123",
            "payload": {"customer_id": "CUST-001", "message": "Where is my order ORD-10042?"},
        },
        "active_frame": {
            "frame_id": "frame_123",
            "state": "WAITING_FOR_EXECUTE",
            "manifest_id": "customer.message_status_check",
            "trigger": {"route_id": "callcenter.customer_message"},
            "inputs": {"customer_id": "CUST-001", "message": "Where is my order ORD-10042?"},
            "outputs": {
                "order_id": "ORD-10042",
                "order": {"status": "shipped"},
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
                    "step_id": "prepare_pending_send",
                }
            ],
            "evidence": [
                {
                    "kind": "business_lookup",
                    "step_id": "lookup_order",
                    "datasets": [{"dataset": "orders", "query": {"order_id": "ORD-10042"}, "found": True}],
                }
            ],
            "steps": [
                {"step_id": "validate_input", "kind": "validate_required_inputs"},
                {"step_id": "extract_order_id", "kind": "extract_order_id"},
                {
                    "step_id": "lookup_order",
                    "kind": "mock_order_lookup",
                    "command": "[t:order/read -> order] order_id=$order_id",
                    "namespace": "order",
                    "action": "read",
                    "output_alias": "order",
                },
            ],
        },
    }


class OperatorUIDetailTests(unittest.TestCase):
    def test_playback_detail_includes_event(self):
        detail = build_selected_detail(make_snapshot(), {"step_id": "event_received"})
        self.assertIn("event_id", detail["event"])
        self.assertIn("source", detail["event"])
        self.assertIn("event_type", detail["event"])
        self.assertIn("payload", detail["event"])

    def test_playback_detail_includes_route(self):
        detail = build_selected_detail(make_snapshot(), {"step_id": "route_resolved"})
        self.assertIn("manifest_id", detail["route"])
        self.assertIn("event_type", detail["route"])
        self.assertIn("route_id", detail["route"])

    def test_playback_detail_includes_manifest(self):
        detail = build_selected_detail(make_snapshot(), {"step_id": "taskframe_created"})
        self.assertEqual(detail["manifest"]["manifest_id"], "customer.message_status_check")
        self.assertGreater(detail["manifest"]["step_count"], 0)
        self.assertIn("completion_requirements", detail["manifest"])

    def test_playback_detail_includes_manifest_step(self):
        detail = build_selected_detail(make_snapshot(), {"step_id": "lookup_order"})
        self.assertEqual(detail["manifest_step"]["step_id"], "lookup_order")
        self.assertIn("command", detail["manifest_step"])
        self.assertIn("kind", detail["manifest_step"])
        self.assertIn("action", detail["manifest_step"])

    def test_playback_detail_includes_runtime_result(self):
        detail = build_selected_detail(make_snapshot(), {"step_id": "lookup_order"})
        self.assertIn("status", detail["runtime_step_result"])
        self.assertIn("evidence", detail["runtime_step_result"])
        self.assertIn("outputs", detail["runtime_step_result"])

    def test_detail_helpers_tolerate_missing_data(self):
        for snapshot in ({}, {"active_event": None}, {"active_frame": None}, {"active_frame": {"frame_id": "x"}}):
            detail = build_selected_detail(snapshot, {"step_id": "lookup_order"})
            self.assertIsInstance(detail, dict)

    def test_ui_source_contains_selected_detail_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Autonomous Business Worker Demo", "Demo:", "Horizontal Demo Flow", "Current run:", "Incoming Request", "Automation Progress", "Business Result", "Approval / Evidence", "Run selected demo", "Browse demo catalog", "Start over", "Progress Animation", "Play", "Pause", "Step", "Selected Step Detail", "Event Detail", "Manifest Step", "Runtime Result", "Approval Pack", "Action Arguments", "Supporting Evidence", "Risk / Guardrails"):
            self.assertIn(text, source)

    def test_operator_ui_contains_approval_action_buttons(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Approve & execute dry run", "Reject", "View technical evidence", "Refresh current run"):
            self.assertIn(text, source)

    def test_operator_ui_contains_customer_inbox_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Customer Inbox", "Seed Inbox", "Reset Inbox", "Process Selected Message", "Selected Message"):
            self.assertIn(text, source)

    def test_operator_ui_contains_business_dataset_controls(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Advanced settings", "Scenario pack", "Reset dataset", "Use local Ollama", "Run selected scenario", "Run selected scenario and generate evidence", "Run full business workflow demo", "Browse demo catalog"):
            self.assertIn(text, source)

    def test_operator_ui_contains_failure_summary_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Failure Summary", "failed_step_id", "failure_message", "failed validations"):
            self.assertIn(text, source)

    def test_operator_ui_contains_negative_demo_labels(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Customer Order Status", "Run full business workflow demo", "Technical Inspector"):
            self.assertIn(text, source)

    def test_operator_ui_disables_approval_when_no_pending_action(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("update_approval_button_states", source)

    def test_operator_ui_contains_report_controls(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Reports", "Generate Report", "Open HTML", "Open Folder", "Report Status", "Generate evidence for this run", "Open evidence for this run", "No evidence pack has been generated for this run yet"):
            self.assertIn(text, source)

    def test_operator_ui_contains_tool_capability_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Tool Capability Registry", "Run Safe Health Checks", "Test Selected", "Retry", "Live Test", "Setup", "Details", "Tool Details"):
            self.assertIn(text, source)

    def test_operator_ui_report_generation_is_read_only(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Reports", "Generate Report", "Open HTML", "Open Folder"):
            self.assertIn(text, source)
        self.assertNotIn("dry_run=False", source)

    def test_operator_ui_contains_customer_message_statuses(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("NEW", "PROCESSING", "STAGED_REPLY", "APPROVED", "EXECUTED_DRY_RUN", "REJECTED", "FAILED"):
            self.assertIn(text, source)

    def test_operator_ui_has_approval_operation_result_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Approval Operation Result", "target_frame_id", "command_frame_id"):
            self.assertIn(text, source)

    def test_operator_ui_contains_customer_status_llm_demo_label(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("Customer Order Status", source)

    def test_operator_ui_contains_demo_scenario_pack_panel(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("Scenario", "Run selected scenario", "Run selected scenario and generate evidence", "Scenario Result", "Verdict", "Current run:", "Selected demo"):
            self.assertIn(text, source)

    def test_operator_ui_contains_scenario_category_labels(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("View Mode", "Demo", "Operator", "Inspector"):
            self.assertIn(text, source)

    def test_operator_ui_scenario_pack_does_not_expose_live_execution(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("dry_run=False", "execute_live_approved", "confirm_live", "Live Execute"):
            self.assertNotIn(text, source)

    def test_ui_does_not_expose_live_mode(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("dry_run=False", "execute_live_approved", "confirm_live", "Live Mode", "approve_and_execute"):
            self.assertNotIn(text, source)

    def test_operator_ui_approval_controls_do_not_expose_live_execution(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("dry_run=False", "execute_live_approved", "confirm_live", "approve_and_execute", "approve_all", "reject_all", "Live Execute", "Live Mode"):
            self.assertNotIn(text, source)

    def test_operator_ui_customer_inbox_does_not_execute_live_side_effects(self):
        source = SOURCE.read_text(encoding="utf-8")
        for text in ("dry_run=False", "execute_live_approved", "confirm_live"):
            self.assertNotIn(text, source)

    def test_ui_sources_avoid_blocking_sleep(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("time.sleep", source)
        self.assertNotIn("sleep(", source)
        self.assertIn(".after(", source)


if __name__ == "__main__":
    unittest.main()
