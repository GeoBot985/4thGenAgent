import json
import tempfile
import unittest
from pathlib import Path

from runtime.errors import TaskFrameReloadError
from runtime.manifest_loader import load_manifest
from runtime.persistence import save_taskframe
from runtime.taskframe import create_taskframe, to_dict
from runtime.taskframe_reload import (
    audit_event_from_dict,
    load_manifest_for_frame,
    load_taskframe,
    step_runtime_from_dict,
    taskframe_from_dict,
)


class TaskFrameReloadTests(unittest.TestCase):
    def test_taskframe_from_dict_restores_all_fields_and_types(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        frame = create_taskframe(manifest)
        frame.outputs["reply"] = {"text": "hello"}
        frame.pending_actions.append({"action_id": "pa_1", "status": "PENDING_APPROVAL"})
        frame.executed_actions.append({"action_id": "ea_1", "status": "EXECUTED"})
        frame.validations.append({"validation_id": "v1", "ok": True})
        frame.errors.append({"type": "err", "message": "boom", "data": {}})
        frame.attempts.append({"step_id": "step_1", "attempt": 1, "status": "COMPLETED"})
        frame.audit.append(audit_event_from_dict({"timestamp": "2026-04-30T20:00:00Z", "event_type": "X", "message": "Y", "data": {}}))

        rehydrated = taskframe_from_dict(to_dict(frame))

        self.assertEqual(rehydrated.frame_id, frame.frame_id)
        self.assertEqual(rehydrated.manifest_id, frame.manifest_id)
        self.assertEqual(rehydrated.state, frame.state)
        self.assertEqual(rehydrated.trigger, frame.trigger)
        self.assertEqual(rehydrated.inputs, frame.inputs)
        self.assertEqual(rehydrated.outputs, frame.outputs)
        self.assertEqual(rehydrated.pending_actions, frame.pending_actions)
        self.assertEqual(rehydrated.executed_actions, frame.executed_actions)
        self.assertEqual(rehydrated.validations, frame.validations)
        self.assertEqual(rehydrated.errors, frame.errors)
        self.assertEqual(rehydrated.attempts, frame.attempts)
        self.assertIsNotNone(rehydrated.steps[0])
        self.assertEqual(rehydrated.audit[0].event_type, "TASKFRAME_CREATED")
        self.assertTrue(json.dumps(to_dict(rehydrated)))

    def test_taskframe_from_dict_missing_required_fields_fails(self):
        base = {
            "manifest_id": "smoke.gmail_check",
            "state": "CREATED",
            "steps": [],
            "created_at": "2026-04-30T20:00:00Z",
            "updated_at": "2026-04-30T20:00:00Z",
        }
        for key in ["frame_id", "manifest_id", "state"]:
            with self.subTest(key=key):
                data = dict(base)
                data.pop(key, None)
                with self.assertRaises(TaskFrameReloadError):
                    taskframe_from_dict(data)

    def test_taskframe_from_dict_allows_missing_optional_lists(self):
        data = {
            "frame_id": "tf_1",
            "manifest_id": "smoke.gmail_check",
            "state": "CREATED",
            "trigger": {},
            "raw_input": "",
            "inputs": {},
            "steps": [],
            "created_at": "2026-04-30T20:00:00Z",
            "updated_at": "2026-04-30T20:00:00Z",
        }
        frame = taskframe_from_dict(data)

        self.assertEqual(frame.outputs, {})
        self.assertEqual(frame.pending_actions, [])
        self.assertEqual(frame.executed_actions, [])
        self.assertEqual(frame.tool_calls, [])
        self.assertEqual(frame.llm_calls, [])
        self.assertEqual(frame.validations, [])
        self.assertEqual(frame.errors, [])
        self.assertEqual(frame.attempts, [])

    def test_load_taskframe_loads_persisted_frame_and_missing_frame_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
            frame = create_taskframe(manifest)
            save_taskframe(frame, tmp)

            loaded = load_taskframe(frame.frame_id, tmp)
            self.assertEqual(loaded.frame_id, frame.frame_id)

            with self.assertRaises(TaskFrameReloadError):
                load_taskframe("missing", tmp)

    def test_load_manifest_for_frame_loads_manifest_and_missing_manifest_fails(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        frame = create_taskframe(manifest)

        loaded = load_manifest_for_frame(frame)
        self.assertEqual(loaded.manifest_id, manifest.manifest_id)

        frame.manifest_id = "missing.manifest"  # type: ignore[misc]
        with self.assertRaises(Exception):
            load_manifest_for_frame(frame)

    def test_step_runtime_and_audit_event_rehydration_helpers(self):
        step = step_runtime_from_dict(
            {
                "step_id": "step_1",
                "command": "[t:g/check -> unread_mail] max_results=5",
                "status": "COMPLETED",
                "attempts": 2,
                "max_attempts": 3,
                "started_at": "2026-04-30T20:00:00Z",
                "ended_at": "2026-04-30T20:00:01Z",
                "duration_ms": 1000.0,
            }
        )
        audit = audit_event_from_dict({"timestamp": "2026-04-30T20:00:00Z", "event_type": "X", "message": "Y", "data": {}})

        self.assertEqual(step.step_id, "step_1")
        self.assertEqual(step.status, "COMPLETED")
        self.assertEqual(step.attempts, 2)
        self.assertEqual(audit.event_type, "X")


if __name__ == "__main__":
    unittest.main()
