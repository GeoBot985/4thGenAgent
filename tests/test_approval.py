import unittest

from runtime.approval import (
    approve_action,
    approve_all_pending_actions,
    reject_action,
    reject_all_pending_actions,
)
from runtime.errors import PendingActionError
from runtime.manifest_loader import load_manifest
from runtime.taskframe import create_taskframe


def make_frame_with_two_pending_actions():
    manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
    frame = create_taskframe(manifest)
    frame.pending_actions.append(make_single_pending_action("pa_1"))
    frame.pending_actions.append(
        {
            "action_id": "pa_extra",
            "step_id": "stage_message_2",
            "tool": "wa/send",
            "namespace": "wa",
            "action": "send",
            "output_alias": "sent_msg_2",
            "args": {"chat": "Cornelia", "message": "One"},
            "status": "PENDING_APPROVAL",
            "side_effect": True,
            "requires_approval": True,
            "created_at": "2026-05-01T00:00:00Z",
        }
    )
    return frame


def make_single_pending_action(action_id: str = "pa_1", status: str = "PENDING_APPROVAL") -> dict:
    return {
        "action_id": action_id,
        "step_id": "stage_message",
        "tool": "wa/send",
        "namespace": "wa",
        "action": "send",
        "output_alias": "sent_msg",
        "args": {"chat": "Cornelia", "message": "Runtime smoke test"},
        "status": status,
        "side_effect": True,
        "requires_approval": True,
        "created_at": "2026-05-01T00:00:00Z",
    }


class ApprovalTests(unittest.TestCase):
    def test_approve_action_marks_pending_action_approved(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        frame.pending_actions.append(make_single_pending_action())
        action_id = frame.pending_actions[0]["action_id"]

        approve_action(frame, action_id, approved_by="smoke", reason="Approved by smoke test")

        action = frame.pending_actions[0]
        self.assertEqual(action["status"], "APPROVED")
        self.assertEqual(action["approved_by"], "smoke")
        self.assertIn("approved_at", action)
        self.assertEqual(action["approval_reason"], "Approved by smoke test")
        self.assertEqual(frame.audit[-1].event_type, "PENDING_ACTION_APPROVED")

    def test_reject_action_marks_pending_action_rejected(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        frame.pending_actions.append(make_single_pending_action())
        action_id = frame.pending_actions[0]["action_id"]

        reject_action(frame, action_id, rejected_by="smoke", reason="Incorrect recipient")

        action = frame.pending_actions[0]
        self.assertEqual(action["status"], "REJECTED")
        self.assertEqual(action["rejected_by"], "smoke")
        self.assertIn("rejected_at", action)
        self.assertEqual(action["rejection_reason"], "Incorrect recipient")
        self.assertEqual(frame.audit[-1].event_type, "PENDING_ACTION_REJECTED")

    def test_approve_missing_action_fails(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        with self.assertRaises(PendingActionError):
            approve_action(frame, "missing")

    def test_reject_missing_action_fails(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        with self.assertRaises(PendingActionError):
            reject_action(frame, "missing")

    def test_approve_already_approved_action_fails(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        action = make_single_pending_action(status="APPROVED")
        frame.pending_actions.append(action)
        with self.assertRaises(PendingActionError):
            approve_action(frame, action["action_id"])

    def test_approve_rejected_action_fails(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        action = make_single_pending_action(status="REJECTED")
        frame.pending_actions.append(action)
        with self.assertRaises(PendingActionError):
            approve_action(frame, action["action_id"])

    def test_reject_approved_action_fails(self):
        frame = create_taskframe(load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json"))
        action = make_single_pending_action(status="APPROVED")
        frame.pending_actions.append(action)
        with self.assertRaises(PendingActionError):
            reject_action(frame, action["action_id"])

    def test_approve_all_pending_actions_approves_multiple_actions(self):
        frame = make_frame_with_two_pending_actions()

        approve_all_pending_actions(frame, approved_by="smoke", reason="Approved")

        self.assertEqual(frame.pending_actions[0]["status"], "APPROVED")
        self.assertEqual(frame.pending_actions[1]["status"], "APPROVED")

    def test_reject_all_pending_actions_rejects_multiple_actions(self):
        frame = make_frame_with_two_pending_actions()

        reject_all_pending_actions(frame, rejected_by="smoke", reason="Rejected")

        self.assertEqual(frame.pending_actions[0]["status"], "REJECTED")
        self.assertEqual(frame.pending_actions[1]["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
