import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.models import ManifestStep
from runtime.orchestrator import Orchestrator
from runtime.taskframe import create_taskframe, to_dict
from runtime.tool_registry import TOOL_REGISTRY
from runtime.validation import run_validation


class ExecutionMetricsTests(unittest.TestCase):
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

        class SlowThenFast:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    time.sleep(0.05)
                return {"ok": True, "calls": self.calls}

        module.fake_fast = fake_fast
        module.fake_slow = fake_slow
        module.slow_then_fast = SlowThenFast()
        sys.modules[module_name] = module
        self._modules_to_cleanup.append(module_name)

        self._register_tool(
            "fake/fast",
            {
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
            },
        )
        self._register_tool(
            "fake/slow",
            {
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
            },
        )
        self._register_tool(
            "fake/slow_then_fast",
            {
                "namespace": "fake",
                "action": "slow_then_fast",
                "module": module_name,
                "function": "slow_then_fast",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )

    def tearDown(self):
        TOOL_REGISTRY.clear()
        TOOL_REGISTRY.update(self._registry_backup)
        for module_name in self._modules_to_cleanup:
            sys.modules.pop(module_name, None)

    def _register_tool(self, key: str, spec: dict) -> None:
        TOOL_REGISTRY[key] = spec

    def test_attempt_record_includes_timing_fields(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        attempt = frame.attempts[0]
        self.assertIn("started_at", attempt)
        self.assertIn("ended_at", attempt)
        self.assertIn("duration_ms", attempt)
        self.assertIn("timeout_seconds", attempt)
        self.assertIn("timed_out", attempt)

    def test_step_stores_last_attempt_metrics(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        step = frame.steps[0]
        self.assertTrue(step.started_at)
        self.assertTrue(step.ended_at)
        self.assertGreaterEqual(step.duration_ms, 0.0)

    def test_retry_after_timeout_creates_two_attempt_records(self):
        manifest = load_manifest("manifests/smoke_timeout_retry_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        self.assertEqual(len(frame.attempts), 2)
        self.assertTrue(frame.attempts[0]["timed_out"])
        self.assertFalse(frame.attempts[1]["timed_out"])
        self.assertEqual(frame.steps[0].attempts, 2)
        self.assertEqual(frame.state, "COMPLETED")

    def test_attempt_count_validations_pass(self):
        manifest = load_manifest("manifests/smoke_timeout_retry_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        result = run_validation(
            frame,
            {"id": "v1", "type": "attempt_count_equals", "step": "run_slow_then_fast_tool", "count": 2},
        )
        self.assertTrue(result.ok)

        result = run_validation(
            frame,
            {
                "id": "v2",
                "type": "attempt_count_less_than_or_equal",
                "step": "run_slow_then_fast_tool",
                "count": 3,
            },
        )
        self.assertTrue(result.ok)

    def test_step_duration_and_timeout_validations_pass(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        result = run_validation(
            frame,
            {"id": "v1", "type": "step_duration_under", "step": "run_fast_tool", "max_ms": 5000},
        )
        self.assertTrue(result.ok)

        result = run_validation(frame, {"id": "v2", "type": "step_timed_out", "step": "run_fast_tool"})
        self.assertFalse(result.ok)

        result = run_validation(frame, {"id": "v3", "type": "step_not_timed_out", "step": "run_fast_tool"})
        self.assertTrue(result.ok)

    def test_timed_out_validation_passes_for_slow_step(self):
        manifest = load_manifest("manifests/smoke_timeout_exceeded.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        result = run_validation(frame, {"id": "v1", "type": "step_timed_out", "step": "run_slow_tool"})
        self.assertTrue(result.ok)

    def test_to_dict_serializes_timing_fields(self):
        manifest = load_manifest("manifests/smoke_timeout_success.manifest.json")
        frame = create_taskframe(manifest)

        data = to_dict(frame)

        self.assertIn("started_at", data["steps"][0])
        self.assertIn("ended_at", data["steps"][0])
        self.assertIn("duration_ms", data["steps"][0])

    def test_timeout_retry_audits_include_attempts(self):
        manifest = load_manifest("manifests/smoke_timeout_retry_success.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=False)

        audit_types = [event.event_type for event in frame.audit]
        self.assertIn("STEP_ATTEMPT_STARTED", audit_types)
        self.assertIn("STEP_ATTEMPT_FAILED", audit_types)
        self.assertIn("STEP_RETRY_SCHEDULED", audit_types)
        self.assertIn("STEP_TIMING_RECORDED", audit_types)


if __name__ == "__main__":
    unittest.main()
