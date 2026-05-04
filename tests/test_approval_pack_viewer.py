from __future__ import annotations

import unittest

from src.operator_approval_pack import (
    build_approval_pack_view,
    build_human_execute_summary,
    build_pending_action_pack,
)


class ApprovalPackViewerTests(unittest.TestCase):
    def test_build_approval_pack_view_no_pending_actions(self):
        view = build_approval_pack_view({"frame_id": "frame_1", "pending_actions": []})
        self.assertTrue(view["ok"])
        self.assertEqual(view["pending_action_count"], 0)
        self.assertEqual(view["approval_packs"], [])

    def test_build_approval_pack_view_with_whatsapp_action(self):
        frame = {
            "frame_id": "frame_1",
            "manifest_id": "customer.message_status_check",
            "state": "WAITING_FOR_EXECUTE",
            "outputs": {"draft_reply": {"body": "Runtime smoke test"}},
            "pending_actions": [
                {
                    "action_id": "pa_1",
                    "status": "PENDING_APPROVAL",
                    "step_id": "stage_send_reply",
                    "tool": "wa/send",
                    "namespace": "wa",
                    "action": "send",
                    "output_alias": "sent_msg",
                    "side_effect": True,
                    "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
                }
            ],
        }
        view = build_approval_pack_view(frame)
        pack = view["approval_packs"][0]
        self.assertEqual(view["pending_action_count"], 1)
        self.assertEqual(pack["tool"], "wa/send")
        self.assertEqual(pack["risk_class"], "external_communication")
        self.assertIn("WhatsApp", pack["human_summary"])
        self.assertIn("Cornelia", pack["human_summary"])
        self.assertIn("Runtime smoke test", pack["human_summary"])

    def test_build_human_execute_summary_known_booking_tool(self):
        summary = build_human_execute_summary({"tool": "gb/book", "args": {"court": "Court 1", "date": "2026-05-01", "time_value": "10:00"}})
        self.assertIn("Court 1", summary)
        self.assertIn("2026-05-01", summary)
        self.assertIn("10:00", summary)

    def test_build_human_execute_summary_unknown_tool_fallback(self):
        summary = build_human_execute_summary({"tool": "x/custom", "args": {"foo": "bar"}})
        self.assertIn('tool "x/custom"', summary)
        self.assertIn("listed arguments", summary)

    def test_approval_pack_helpers_tolerate_partial_data(self):
        cases = [
            {},
            {"pending_actions": None},
            {"pending_actions": [{}]},
            {"pending_actions": [{"tool": "wa/send"}]},
        ]
        for frame in cases:
            view = build_approval_pack_view(frame)
            self.assertIsInstance(view, dict)
            self.assertIn("approval_packs", view)
            if frame.get("pending_actions") in (None, []):
                self.assertEqual(view["approval_packs"], [])


if __name__ == "__main__":
    unittest.main()
