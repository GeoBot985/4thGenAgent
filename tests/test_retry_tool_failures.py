import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.arg_resolver import ArgumentResolutionError
from runtime.events import create_event
from runtime.llm_adapter import BaseLLMAdapter
from runtime.manifest_loader import load_manifest
from runtime.memory_store import MemoryStore
from runtime.models import MemoryResult
from runtime.orchestrator import Orchestrator
from runtime.taskframe import create_taskframe, tool_result_ok
from runtime.tool_registry import TOOL_REGISTRY
from runtime.tool_runner import ToolRunner


def write_manifest(tmpdir: Path, data: dict, filename: str = "manifest.manifest.json") -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class FlakyLLMAdapter(BaseLLMAdapter):
    provider = "fake"
    model = "fake"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, system: str = "", metadata: dict | None = None) -> str:
        self.calls += 1
        if not self.responses:
            return "not json"
        if self.calls - 1 < len(self.responses):
            return self.responses[self.calls - 1]
        return self.responses[-1]


class RetryToolFailureTests(unittest.TestCase):
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

    def test_dry_run_tool_does_not_need_retry(self):
        manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[0].attempts, 1)
        self.assertIn(frame.state, {"COMPLETED", "COMPLETED_NO_DATA"})

    def test_forced_dry_run_failure_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_forced_dry_run_failure",
                    "name": "Smoke Test - Forced Dry Run Failure",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "check_mail",
                            "retry": {"max_attempts": 2, "retry_on": ["any"]},
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            with patch("runtime.tool_runner.dry_run_tool_result", side_effect=[RuntimeError("temporary dry run failure"), tool_result_ok("gmail_check_result", data={"dry_run": True, "tool": "g/check", "function": "gmail_check", "args": {"max_results": 5}})]):
                frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertIn("unread_mail", frame.outputs)

    def test_side_effect_staging_failure_can_retry_before_pending_action_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_name = "fake_retry_tools"

            def stage_tool(chat, message):  # pragma: no cover - patched by resolve_command_args
                return {"chat": chat, "message": message}

            self._install_fake_module(module_name, stage_tool=stage_tool)
            TOOL_REGISTRY["fake/stage"] = {
                "namespace": "fake",
                "action": "stage",
                "module": module_name,
                "function": "stage_tool",
                "side_effect": True,
                "requires_approval": True,
                "allow_live": False,
                "output_type": "fake_stage_result",
                "required_args": ["chat", "message"],
                "optional_args": [],
                "arg_types": {},
            }
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_stage_failure",
                    "name": "Smoke Test - Retry Stage Failure",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "stage_message",
                            "retry": {"max_attempts": 2, "retry_on": ["any"]},
                            "command": "[t:fake/stage -> sent_msg] chat=\"Cornelia\"; message=\"Hello\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_pending_actions": ["sent_msg"], "allow_pending_approval": True},
                },
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            with patch("runtime.tool_runner.resolve_command_args", side_effect=[ArgumentResolutionError("temporary"), {"chat": "Cornelia", "message": "Hello"}]):
                frame = orch.run_next_step(frame, manifest, dry_run=True)

            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertEqual(frame.steps[0].status, "STAGED")
            self.assertEqual(len(frame.pending_actions), 1)
            self.assertIn("STEP_RETRY_SCHEDULED", [event.event_type for event in frame.audit])

    def test_side_effect_staging_success_does_not_retry(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)

        frame = orch.run_next_step(frame, manifest, dry_run=True)

        self.assertEqual(frame.steps[0].attempts, 1)
        self.assertEqual(frame.steps[0].status, "STAGED")
        self.assertEqual(len(frame.pending_actions), 1)

    def test_pending_action_execution_dry_run_failure_does_not_retry(self):
        manifest = load_manifest("manifests/smoke_whatsapp_stage_send.manifest.json")
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        frame = orch.run_until_blocked(frame, manifest, dry_run=True)
        action_id = frame.pending_actions[0]["action_id"]
        orch.approve_pending_action(frame, action_id, approved_by="test")

        with patch("runtime.tool_runner.ToolRunner.execute_pending_action", side_effect=RuntimeError("temporary failure")) as execute_mock:
            with self.assertRaises(RuntimeError):
                orch.execute_approved_pending_actions(frame, manifest, dry_run=True)
            self.assertEqual(execute_mock.call_count, 1)

    def test_llm_bad_json_then_good_json_retries_and_succeeds(self):
        adapter = FlakyLLMAdapter([
            "not json",
            "{\"order_ref\":\"ORD-10042\",\"confidence\":\"high\"}",
        ])
        orch = Orchestrator(llm_adapter=adapter)
        manifest = load_manifest("manifests/smoke_retry_llm_success_after_failure.manifest.json")
        frame = orch.create_frame_from_manifest(manifest, inputs={"message": "Where is ORD-10042?"})
        frame = orch.prepare_frame(frame)

        frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "COMPLETED")
        self.assertEqual(frame.steps[0].attempts, 2)
        self.assertEqual(frame.outputs["extracted"]["order_ref"], "ORD-10042")

    def test_llm_bad_json_exhausted_fails(self):
        adapter = FlakyLLMAdapter(["not json", "still not json"])
        orch = Orchestrator(llm_adapter=adapter)
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_llm_exhausted",
                    "name": "Smoke Test - Retry LLM Exhausted",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["message"],
                    "steps": [
                        {
                            "id": "extract_order_ref",
                            "retry": {"max_attempts": 2, "retry_on": ["LLMOutputParseError", "any"]},
                            "command": "[q:extract -> extracted] schema=\"order_ref\"; fields=\"order_ref,confidence\"; text=$inputs.message",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["extracted"]},
                },
            )
            manifest = load_manifest(manifest_path)
            frame = orch.create_frame_from_manifest(manifest, inputs={"message": "Where is ORD-10042?"})
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertEqual(frame.steps[0].attempts, 2)

    def test_memory_command_failure_retries_only_if_policy_allows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_memory_set",
                    "name": "Smoke Test - Retry Memory Set",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["key", "value"],
                    "steps": [
                        {
                            "id": "set_memory",
                            "retry": {"max_attempts": 2, "retry_on": ["any"]},
                            "command": "[m:set -> saved_memory] key=$inputs.key; value=$inputs.value",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_memory"]},
                },
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator(memory_store=store)
            frame = orch.create_frame_from_manifest(
                manifest,
                inputs={"key": "supplier.ABC.preferred_channel", "value": "email"},
            )
            frame = orch.prepare_frame(frame)

            original_set = MemoryStore.set

            def flaky_set(self, key, value, metadata=None):
                if not hasattr(flaky_set, "calls"):
                    flaky_set.calls = 0  # type: ignore[attr-defined]
                flaky_set.calls += 1  # type: ignore[attr-defined]
                if flaky_set.calls == 1:  # type: ignore[attr-defined]
                    raise RuntimeError("temporary")
                return original_set(self, key, value, metadata=metadata)

            with patch.object(MemoryStore, "set", new=flaky_set):
                frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "COMPLETED")
            self.assertEqual(frame.steps[0].attempts, 2)
            self.assertEqual(store.get("supplier.ABC.preferred_channel").value, "email")

    def test_condition_evaluation_failure_does_not_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                Path(tmp),
                {
                    "manifest_id": "smoke.retry_condition_failure",
                    "name": "Smoke Test - Retry Condition Failure",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "bad_condition_step",
                            "retry": {"max_attempts": 2, "retry_on": ["any"]},
                            "when": {"all": [{"output": "missing_output", "field": "label", "equals": "refund"}]},
                            "command": "[m:set -> saved] key=\"a\"; value=\"b\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved"]},
                },
            )
            manifest = load_manifest(manifest_path)
            orch = Orchestrator()
            frame = orch.create_frame_from_manifest(manifest)
            frame = orch.prepare_frame(frame)

            frame = orch.run_until_blocked(frame, manifest, dry_run=True)

            self.assertEqual(frame.state, "FAILED_EXECUTION")
            self.assertEqual(frame.steps[0].attempts, 0)
            self.assertNotIn("STEP_RETRY_SCHEDULED", [event.event_type for event in frame.audit])


if __name__ == "__main__":
    unittest.main()
