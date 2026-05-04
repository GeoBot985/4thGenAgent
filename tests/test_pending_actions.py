import unittest

from runtime.models import StepRuntime
from runtime.taskframe import create_taskframe
from runtime.tool_registry import get_tool_spec
from runtime.tool_runner import create_pending_action
from runtime.manifest_loader import load_manifest


class PendingActionTests(unittest.TestCase):
    def test_pending_action_shape(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        step = frame.steps[0]
        spec = get_tool_spec("wa", "send")

        action = create_pending_action(
            frame,
            step,
            spec,
            {"chat": "Cornelia", "message": "Running late"},
        )

        self.assertTrue(action["action_id"].startswith("pa_"))
        self.assertEqual(action["step_id"], "stage_message")
        self.assertEqual(action["tool"], "wa/send")
        self.assertEqual(action["namespace"], "wa")
        self.assertEqual(action["action"], "send")
        self.assertEqual(action["output_alias"], "sent_msg")
        self.assertEqual(action["args"], {"chat": "Cornelia", "message": "Running late"})
        self.assertEqual(action["status"], "PENDING_APPROVAL")
        self.assertIn("created_at", action)

    def test_multiple_pending_actions_get_unique_ids(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        step = frame.steps[0]
        spec = get_tool_spec("wa", "send")

        action1 = create_pending_action(frame, step, spec, {"chat": "Cornelia"})
        action2 = create_pending_action(frame, step, spec, {"chat": "Cornelia"})

        self.assertNotEqual(action1["action_id"], action2["action_id"])


if __name__ == "__main__":
    unittest.main()

