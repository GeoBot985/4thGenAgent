import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.orchestrator import Orchestrator
from runtime.taskframe import create_taskframe
from runtime.tool_registry import TOOL_REGISTRY


class StepTimeoutPolicyTests(unittest.TestCase):
    def setUp(self):
        self._registry_backup = dict(TOOL_REGISTRY)
        self._modules_to_cleanup: list[str] = []

        module_name = "fake_timing_tools"
        module = types.ModuleType(module_name)

        def fake_fast():
            time.sleep(0.01)
            return {"ok": True}

        def fake_slow():
            time.sleep(0.05)
            return {"ok": True}

        module.fake_fast = fake_fast
        module.fake_slow = fake_slow
        sys.modules[module_name] = module
        self._modules_to_cleanup.append(module_name)

        TOOL_REGISTRY["fake/fast"] = {
            "namespace": "fake",
            "action": "fast",
            "module": module_name,
            "function": "fake_fast",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }
        TOOL_REGISTRY["fake/slow"] = {
            "namespace": "fake",
            "action": "slow",
            "module": module_name,
            "function": "fake_slow",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

    def tearDown(self):
        TOOL_REGISTRY.clear()
        TOOL_REGISTRY.update(self._registry_backup)
        for module_name in self._modules_to_cleanup:
            sys.modules.pop(module_name, None)

    def test_manifest_loader_stores_timeout_seconds(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        self.assertEqual(manifest.steps[0].timeout_seconds, 1.0)

    def test_create_taskframe_copies_timeout_seconds(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        frame = create_taskframe(manifest)

        self.assertEqual(frame.steps[0].timeout_seconds, 1.0)
        self.assertEqual(frame.steps[0].started_at, "")
        self.assertEqual(frame.steps[0].ended_at, "")
        self.assertEqual(frame.steps[0].duration_ms, 0.0)

    def test_fast_step_completes_within_timeout(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[0].status, "COMPLETED")
        self.assertIn("result", frame.outputs)
        self.assertFalse(frame.attempts[0]["timed_out"])
        self.assertIn("STEP_TIMING_RECORDED", [event.event_type for event in frame.audit])

    def test_slow_step_exceeding_timeout_fails(self):
        manifest = load_manifest("manifests/smoke_timeout_exceeded.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertNotIn("result", frame.outputs)
        self.assertTrue(frame.attempts[0]["timed_out"])
        self.assertEqual(frame.attempts[0]["error_type"], "StepTimeoutExceeded")
        self.assertEqual(frame.attempts[0]["error_tag"], "timeout")
        self.assertIn("STEP_TIMEOUT_EXCEEDED", [event.event_type for event in frame.audit])

    def test_timeout_success_records_timing_event(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        self.assertIn("STEP_TIMING_RECORDED", [event.event_type for event in frame.audit])
        self.assertGreaterEqual(frame.steps[0].duration_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
