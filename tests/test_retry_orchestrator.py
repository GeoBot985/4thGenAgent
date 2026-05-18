import json
import sys
import tempfile
import types
import unittest
import time
from pathlib import Path

from runtime.manifest_loader import load_manifest
from runtime.models import Manifest, ManifestStep
from runtime.orchestrator import Orchestrator
from runtime.taskframe import create_taskframe
from runtime.tool_registry import TOOL_REGISTRY


def write_manifest(tmpdir: Path, data: dict, filename: str = "manifest.manifest.json") -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class RetryOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self._registry_backup = dict(TOOL_REGISTRY)
        self._modules_to_cleanup: list[str] = []

    def tearDown(self):
        TOOL_REGISTRY.clear()
        TOOL_REGISTRY.update(self._registry_backup)
        for module_name in self._modules_to_cleanup:
            sys.modules.pop(module_name, None)

    def _install_fake_module(self, module_name: str, **attrs):
        module = types.ModuleType(module_name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[module_name] = module
        self._modules_to_cleanup.append(module_name)
        return module

    def _make_retry_manifest(self, tmpdir: Path, manifest_id: str, command: str, retry: dict, validations: list | None = None, completion: dict | None = None) -> Path:
        return write_manifest(
            tmpdir,
            {
                "manifest_id": manifest_id,
                "name": manifest_id,
                "version": 1,
                "trigger": {"type": "manual"},
                "inputs": [],
                "steps": [{"id": "run_step", "retry": retry, "command": command}],
                "validations": validations or [],
                "completion": completion or {"success_outputs": ["result"]},
            },
            filename=f"{manifest_id}.manifest.json",
        )

    def test_manifest_loader_stores_normalized_retry_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_loader",
                "[t:g/check -> unread_mail] max_results=5",
                {"max_attempts": 2},
                validations=[],
                completion={"success_outputs": ["unread_mail"]},
            )

            manifest = load_manifest(manifest_path)

            self.assertEqual(manifest.steps[0].retry["max_attempts"], 2)
            self.assertEqual(manifest.steps[0].retry["delay_seconds"], 0)
            self.assertEqual(manifest.steps[0].retry["retry_on"], ["any"])
            self.assertTrue(manifest.steps[0].retry["fail_on_exhausted"])

    def test_create_taskframe_copies_retry_policy_to_step_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_frame",
                "[t:g/check -> unread_mail] max_results=5",
                {"max_attempts": 3},
                validations=[],
                completion={"success_outputs": ["unread_mail"]},
            )

            manifest = load_manifest(manifest_path)
            frame = create_taskframe(manifest)

            self.assertEqual(frame.steps[0].retry["max_attempts"], 3)
            self.assertEqual(frame.steps[0].max_attempts, 3)
            self.assertEqual(frame.steps[0].attempts, 0)

    def test_run_next_step_increments_attempt_count(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[0].attempts, 1)
        self.assertEqual(frame.attempts[0]["attempt"], 1)

    def test_successful_step_records_one_attempt(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[0].attempts, 1)
        self.assertEqual(len(frame.attempts), 1)
        self.assertEqual(frame.attempts[0]["status"], "COMPLETED")

    def test_failed_then_successful_step_records_two_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            class FlakyTool:
                def __init__(self):
                    self.calls = 0

                def __call__(self):
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError("temporary failure")
                    return {"ok": True, "calls": self.calls}

            self._install_fake_module(module_name, flaky_tool=FlakyTool())
            TOOL_REGISTRY["fake/flaky"] = {
                "namespace": "fake",
                "action": "flaky",
                "module": module_name,
                "function": "flaky_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            }

            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_flaky",
                "[t:fake/flaky -> result]",
                {"max_attempts": 2, "retry_on": ["any"]},
                validations=[],
                completion={"success_outputs": ["result"]},
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=False)
            frame = orch.verify_frame(frame, manifest)

            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertEqual(len(frame.attempts), 2)
            self.assertEqual(frame.steps[0].status, "COMPLETED")
            self.assertEqual(frame.state, "COMPLETED")

    def test_retryable_failure_schedules_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            class FlakyTool:
                def __init__(self):
                    self.calls = 0

                def __call__(self):
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError("temporary failure")
                    return {"ok": True, "calls": self.calls}

            self._install_fake_module(module_name, flaky_tool=FlakyTool())
            TOOL_REGISTRY["fake/flaky"] = {
                "namespace": "fake",
                "action": "flaky",
                "module": module_name,
                "function": "flaky_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            }

            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_flaky_schedule",
                "[t:fake/flaky -> result]",
                {"max_attempts": 2, "retry_on": ["any"]},
                validations=[],
                completion={"success_outputs": ["result"]},
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=False)

            event_types = [event.event_type for event in frame.audit]
            self.assertIn("STEP_RETRY_SCHEDULED", event_types)
            self.assertIn("STEP_ATTEMPT_FAILED", event_types)

    def test_non_retryable_failure_does_not_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            def needs_arg(value):  # pragma: no cover - never called
                return {"value": value}

            self._install_fake_module(module_name, needs_arg=needs_arg)
            TOOL_REGISTRY["fake/needs_arg"] = {
                "namespace": "fake",
                "action": "needs_arg",
                "module": module_name,
                "function": "needs_arg",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": ["value"],
                "optional_args": [],
                "arg_types": {},
            }

            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_non_retryable",
                "[t:fake/needs_arg -> result]",
                {"max_attempts": 3, "retry_on": ["LLMOutputParseError"]},
                validations=[],
                completion={"success_outputs": ["result"]},
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=False)

            self.assertEqual(frame.steps[0].attempts, 1)
            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertNotIn("STEP_RETRY_SCHEDULED", [event.event_type for event in frame.audit])
            self.assertIn("STEP_RETRY_NOT_ALLOWED", [event.event_type for event in frame.audit])

    def test_retry_exhausted_marks_step_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            def always_fail():
                raise RuntimeError("permanent failure")

            self._install_fake_module(module_name, always_fail=always_fail)
            TOOL_REGISTRY["fake/always_fail"] = {
                "namespace": "fake",
                "action": "always_fail",
                "module": module_name,
                "function": "always_fail",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            }

            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_always_fail",
                "[t:fake/always_fail -> result]",
                {"max_attempts": 3, "retry_on": ["any"]},
                validations=[],
                completion={"success_outputs": ["result"]},
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=False)

            self.assertEqual(frame.steps[0].status, "FAILED")
            self.assertEqual(frame.steps[0].attempts, 3)
            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertIn("STEP_RETRY_EXHAUSTED", [event.event_type for event in frame.audit])

    def test_retry_success_leaves_frame_completed_after_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            class FlakyTool:
                def __init__(self):
                    self.calls = 0

                def __call__(self):
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError("temporary failure")
                    return {"ok": True, "calls": self.calls}

            self._install_fake_module(module_name, flaky_tool=FlakyTool())
            TOOL_REGISTRY["fake/flaky"] = {
                "namespace": "fake",
                "action": "flaky",
                "module": module_name,
                "function": "flaky_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            }

            manifest_path = self._make_retry_manifest(
                Path(tmp),
                "smoke.retry_completed",
                "[t:fake/flaky -> result]",
                {"max_attempts": 2, "retry_on": ["any"]},
                validations=[],
                completion={"success_outputs": ["result"]},
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)
            frame = orch.run_until_blocked(frame, manifest, dry_run=False)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertTrue(frame.completion_gate_result["ok"])

    def test_validation_step_does_not_retry(self):
        manifest = load_manifest("manifests/smoke_retry_no_retry_on_validation.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "FAILED_VALIDATION")
        self.assertEqual(frame.steps[0].attempts, 1)
        self.assertIn("STEP_ATTEMPT_FAILED", [event.event_type for event in frame.audit])
        self.assertNotIn("STEP_RETRY_SCHEDULED", [event.event_type for event in frame.audit])

    def test_frame_attempt_records_exist(self):
        manifest = load_manifest("manifests/smoke_retry_tool_exhausted.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            def always_fail():
                raise RuntimeError("permanent failure")

            self._install_fake_module(module_name, always_fail=always_fail)
            TOOL_REGISTRY["fake/always_fail"] = {
                "namespace": "fake",
                "action": "always_fail",
                "module": module_name,
                "function": "always_fail",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            }

            manifest = load_manifest("manifests/smoke_retry_tool_exhausted.manifest.json")
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)
            frame = orch.run_next_step(frame, manifest, dry_run=False)

        self.assertTrue(frame.attempts)
        self.assertEqual(frame.attempts[-1]["step_id"], "run_always_fail_tool")
        self.assertIn("error_type", frame.attempts[-1])

    def test_timeout_can_retry_when_retry_on_includes_timeout(self):
        module_name = "fake_retry_timeout_tools"

        class SlowThenFast:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    time.sleep(0.2)
                return {"ok": True, "calls": self.calls}

        self._install_fake_module(module_name, slow_then_fast=SlowThenFast())
        TOOL_REGISTRY["fake/slow_then_fast"] = {
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
        }

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_timeout",
                    "name": "smoke.retry_timeout",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_step",
                            "retry": {"max_attempts": 2, "retry_on": ["timeout"]},
                            "timeout_seconds": 0.01,
                            "command": "[t:fake/slow_then_fast -> result]",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["result"]},
                },
                filename="smoke.retry_timeout.manifest.json",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=False)

            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.outputs["result"]["calls"], 2)

    def test_timeout_can_retry_when_retry_on_includes_step_timeout_exceeded(self):
        module_name = "fake_retry_timeout_tools_type"

        class SlowThenFast:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    time.sleep(0.2)
                return {"ok": True, "calls": self.calls}

        self._install_fake_module(module_name, slow_then_fast=SlowThenFast())
        TOOL_REGISTRY["fake/slow_then_fast_type"] = {
            "namespace": "fake",
            "action": "slow_then_fast_type",
            "module": module_name,
            "function": "slow_then_fast",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_timeout_type",
                    "name": "smoke.retry_timeout_type",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_step",
                            "retry": {"max_attempts": 2, "retry_on": ["StepTimeoutExceeded"]},
                            "timeout_seconds": 0.01,
                            "command": "[t:fake/slow_then_fast_type -> result]",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["result"]},
                },
                filename="smoke.retry_timeout_type.manifest.json",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=False)

            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertEqual(frame.state, "COMPLETED")

    def test_timeout_does_not_retry_when_retry_on_excludes_timeout(self):
        module_name = "fake_retry_timeout_blocked"

        def always_slow():
            time.sleep(0.05)
            return {"ok": True}

        self._install_fake_module(module_name, always_slow=always_slow)
        TOOL_REGISTRY["fake/always_slow"] = {
            "namespace": "fake",
            "action": "always_slow",
            "module": module_name,
            "function": "always_slow",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_timeout_blocked",
                    "name": "smoke.retry_timeout_blocked",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_step",
                            "retry": {"max_attempts": 2, "retry_on": ["ToolFunctionError"]},
                            "timeout_seconds": 0.01,
                            "command": "[t:fake/always_slow -> result]",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["result"]},
                },
                filename="smoke.retry_timeout_blocked.manifest.json",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=False)

            self.assertEqual(frame.steps[0].attempts, 1)
            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertIn("STEP_RETRY_NOT_ALLOWED", [event.event_type for event in frame.audit])

    def test_timeout_retry_exhausted_marks_frame_failed(self):
        module_name = "fake_retry_timeout_exhausted"

        def always_slow():
            time.sleep(0.05)
            return {"ok": True}

        self._install_fake_module(module_name, always_slow=always_slow)
        TOOL_REGISTRY["fake/always_slow_exhausted"] = {
            "namespace": "fake",
            "action": "always_slow_exhausted",
            "module": module_name,
            "function": "always_slow",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_timeout_exhausted",
                    "name": "smoke.retry_timeout_exhausted",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_step",
                            "retry": {"max_attempts": 2, "retry_on": ["timeout"]},
                            "timeout_seconds": 0.01,
                            "command": "[t:fake/always_slow_exhausted -> result]",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["result"]},
                },
                filename="smoke.retry_timeout_exhausted.manifest.json",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_next_step(frame, manifest, dry_run=False)

            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertIn("STEP_RETRY_EXHAUSTED", [event.event_type for event in frame.audit])

    def test_timeout_retry_success_completes_frame(self):
        module_name = "fake_retry_timeout_success"

        class SlowThenFast:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    time.sleep(0.2)
                return {"ok": True, "calls": self.calls}

        self._install_fake_module(module_name, slow_then_fast=SlowThenFast())
        TOOL_REGISTRY["fake/slow_then_fast_success"] = {
            "namespace": "fake",
            "action": "slow_then_fast_success",
            "module": module_name,
            "function": "slow_then_fast",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_timeout_success",
                    "name": "smoke.retry_timeout_success",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_step",
                            "retry": {"max_attempts": 2, "retry_on": ["timeout"]},
                            "timeout_seconds": 0.01,
                            "command": "[t:fake/slow_then_fast_success -> result]",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["result"]},
                },
                filename="smoke.retry_timeout_success.manifest.json",
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=False)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].attempts, 2)


if __name__ == "__main__":
    unittest.main()
