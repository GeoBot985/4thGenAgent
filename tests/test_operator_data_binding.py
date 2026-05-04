from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

from src.operator_data import (
    build_operator_snapshot,
    load_event_ledger,
    load_taskframe,
    normalize_frame_for_ui,
    select_active_event,
)


class OperatorDataBindingTests(unittest.TestCase):
    def test_empty_runtime_snapshot_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = build_operator_snapshot(tmp)

            self.assertTrue(snapshot["ok"])
            self.assertEqual(snapshot["events"], [])
            self.assertIsNone(snapshot["active_event"])
            self.assertIsNone(snapshot["active_frame"])
            self.assertEqual(snapshot["outputs"], {})
            self.assertEqual(snapshot["pending_actions"], [])
            self.assertEqual(snapshot["errors"], [])
            self.assertIsInstance(snapshot["trace_lines"], list)

    def test_event_ledger_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            ledger = runtime_root / "events"
            ledger.mkdir(parents=True, exist_ok=True)
            (ledger / "events.jsonl").write_text(
                '{"event_id":"evt-001","source":"callcenter","event_type":"customer_message","status":"FRAME_CREATED","linked_frame_id":"frame-001","received_at":"2026-05-01T10:00:00Z"}\n',
                encoding="utf-8",
            )

            events = load_event_ledger(tmp)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_id"], "evt-001")
            self.assertEqual(events[0]["linked_frame_id"], "frame-001")

    def test_active_event_selected(self):
        events = [
            {"event_id": "evt-001", "source": "callcenter", "event_type": "customer_message", "status": "RECEIVED"},
            {
                "event_id": "evt-002",
                "source": "callcenter",
                "event_type": "customer_message",
                "status": "FRAME_CREATED",
                "linked_frame_id": "frame-002",
            },
        ]

        active = select_active_event(events)

        self.assertIsNotNone(active)
        self.assertEqual(active["event_id"], "evt-002")

    def test_linked_taskframe_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            frame_dir = runtime_root / "taskframes"
            frame_dir.mkdir(parents=True, exist_ok=True)
            frame_dir.joinpath("frame-001.json").write_text(
                """
{
  "frame_id": "frame-001",
  "state": "WAITING_FOR_EXECUTE",
  "manifest_id": "customer.message_status_check",
  "trigger": {
    "kind": "event",
    "event_id": "evt-001",
    "source": "callcenter",
    "event_type": "customer_message",
    "route_id": "callcenter.customer_message"
  },
  "inputs": {
    "customer_id": "CUST-001",
    "message": "Where is my order ORD-10042?"
  },
  "outputs": {
    "order_id": "ORD-10042",
    "order": {
      "status": "shipped"
    },
    "draft_reply": {
      "body": "Your order ORD-10042 has shipped."
    }
  },
  "validations": [
    {
      "step_id": "validate_customer_owns_order",
      "ok": true
    }
  ],
  "pending_actions": [
    {
      "action_type": "send_customer_message",
      "status": "PENDING_APPROVAL",
      "customer_id": "CUST-001",
      "channel": "callcenter",
      "body": "Your order ORD-10042 has shipped."
    }
  ],
  "errors": []
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frame = load_taskframe("frame-001", tmp)

            self.assertIsNotNone(frame)
            self.assertEqual(frame["frame_id"], "frame-001")
            self.assertEqual(frame["outputs"]["order_id"], "ORD-10042")
            self.assertEqual(len(frame["pending_actions"]), 1)
            self.assertEqual(frame["pending_actions"][0]["action_type"], "send_customer_message")

    def test_malformed_jsonl_line_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            ledger = runtime_root / "events"
            ledger.mkdir(parents=True, exist_ok=True)
            (ledger / "events.jsonl").write_text(
                "not-json\n"
                '{"event_id":"evt-002","source":"external","event_type":"mock_ping","status":"FRAME_CREATED"}\n',
                encoding="utf-8",
            )

            snapshot = build_operator_snapshot(tmp)

            self.assertTrue(snapshot["ok"])
            self.assertEqual(len(snapshot["events"]), 1)
            self.assertTrue(any("Malformed event ledger line" in error for error in snapshot["errors"]))

    def test_normalize_frame_for_ui_handles_missing_keys(self):
        normalized = normalize_frame_for_ui({"frame_id": "frame-1"})

        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["frame_id"], "frame-1")
        self.assertEqual(normalized["outputs"], {})
        self.assertEqual(normalized["pending_actions"], [])

    def test_ui_module_still_imports(self):
        self.assertIsNotNone(importlib.import_module("src.operator_ui"))
        self.assertIsNotNone(importlib.import_module("src.operator_data"))


if __name__ == "__main__":
    unittest.main()
