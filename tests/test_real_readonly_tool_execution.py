import sys
import types
import unittest
from unittest.mock import patch

from runtime.approval import approve_action
from runtime.errors import ToolExecutionBlocked
from runtime.models import Manifest, ManifestStep, ParsedCommand
from runtime.taskframe import create_taskframe
from runtime.tool_registry import TOOL_REGISTRY
from runtime.tool_runner import ToolRunner


class RealReadonlyToolExecutionTests(unittest.TestCase):
    def setUp(self):
        self.saved_registry: dict[str, dict | None] = {}
        self.fake_module_name = "fake_tools_live_exec"
        self.fake_module = types.ModuleType(self.fake_module_name)

        def fake_read_tool(limit=5):
            return [{"id": "1", "value": "ok", "limit": limit}]

        async def fake_async_read_tool(name: str):
            return {"name": name, "ok": True}

        def boom_tool():
            raise RuntimeError("boom")

        self.fake_module.fake_read_tool = fake_read_tool
        self.fake_module.fake_async_read_tool = fake_async_read_tool
        self.fake_module.boom_tool = boom_tool
        sys.modules[self.fake_module_name] = self.fake_module

    def tearDown(self):
        for key, value in self.saved_registry.items():
            if value is None:
                TOOL_REGISTRY.pop(key, None)
            else:
                TOOL_REGISTRY[key] = value
        sys.modules.pop(self.fake_module_name, None)

    def _register_tool(self, key: str, spec: dict) -> None:
        if key not in self.saved_registry:
            self.saved_registry[key] = TOOL_REGISTRY.get(key)
        TOOL_REGISTRY[key] = spec

    def _make_frame(self, command: str, namespace: str, action: str, output_alias: str, inputs: dict | None = None):
        parsed = ParsedCommand(
            raw=command,
            kind="tool",
            namespace=namespace,
            action=action,
            output_alias=output_alias,
            payload="",
            args={},
        )
        manifest = Manifest(
            manifest_id="live.test",
            name="Live Test",
            version=1,
            trigger={"type": "manual"},
            inputs=[],
            steps=[
                ManifestStep(
                    id="step_1",
                    command=command,
                    parsed_command=parsed,
                )
            ],
            validations=[],
            completion={},
            raw={},
        )
        frame = create_taskframe(manifest, inputs=inputs or {})
        frame.state = "RUNNING"
        return frame

    def test_dry_run_true_never_imports_or_calls_real_tool_functions(self):
        manifest = self._make_frame('[t:g/check -> unread_mail] max_results=5', "g", "check", "unread_mail")
        runner = ToolRunner(dry_run=True)
        step = manifest.steps[0]

        with patch("runtime.tool_runner.import_tool_function", side_effect=AssertionError("should not import")):
            result = runner.run_step(manifest, step)

        self.assertTrue(result.ok)
        self.assertEqual(step.status, "COMPLETED")
        self.assertIn("unread_mail", manifest.outputs)

    def test_live_read_only_tool_imports_function(self):
        self._register_tool(
            "fake/read",
            {
                "namespace": "fake",
                "action": "read",
                "module": self.fake_module_name,
                "function": "fake_read_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_read_result",
                "required_args": [],
                "optional_args": ["limit"],
                "arg_types": {"limit": "int"},
            },
        )
        frame = self._make_frame('[t:fake/read -> fake_rows] limit=3', "fake", "read", "fake_rows")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertIn("fake_rows", frame.outputs)
        self.assertEqual(frame.outputs["fake_rows"], [{"id": "1", "value": "ok", "limit": 3}])
        self.assertEqual(frame.steps[0].status, "COMPLETED")
        self.assertEqual(frame.tool_calls[0]["tool"], "fake/read")
        self.assertTrue(frame.tool_calls[0]["live"])
        self.assertFalse(frame.tool_calls[0]["dry_run"])
        self.assertTrue(any(event.event_type == "TOOL_LIVE_EXECUTION_STARTED" for event in frame.audit))
        self.assertTrue(any(event.event_type == "TOOL_LIVE_EXECUTION_COMPLETED" for event in frame.audit))

    def test_live_read_only_tool_calls_sync_function(self):
        self._register_tool(
            "fake/read",
            {
                "namespace": "fake",
                "action": "read",
                "module": self.fake_module_name,
                "function": "fake_read_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_read_result",
                "required_args": [],
                "optional_args": ["limit"],
                "arg_types": {"limit": "int"},
            },
        )
        frame = self._make_frame('[t:fake/read -> fake_rows] limit=3', "fake", "read", "fake_rows")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["fake_rows"], [{"id": "1", "value": "ok", "limit": 3}])

    def test_live_read_only_tool_calls_async_function(self):
        self._register_tool(
            "fake/async_read",
            {
                "namespace": "fake",
                "action": "async_read",
                "module": self.fake_module_name,
                "function": "fake_async_read_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_async_read_result",
                "required_args": ["name"],
                "optional_args": [],
                "arg_types": {},
            },
        )
        frame = self._make_frame('[t:fake/async_read -> result] name="Geo"', "fake", "async_read", "result")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.outputs["result"], {"name": "Geo", "ok": True})
        self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_live_read_only_tool_failure_marks_step_failed(self):
        self._register_tool(
            "fake/boom",
            {
                "namespace": "fake",
                "action": "boom",
                "module": self.fake_module_name,
                "function": "boom_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_boom_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        frame = self._make_frame('[t:fake/boom -> out] ', "fake", "boom", "out")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertTrue(frame.errors)
        self.assertTrue(any(event.event_type == "TOOL_LIVE_EXECUTION_FAILED" for event in frame.audit))

    def test_live_read_only_tool_failure_records_error(self):
        self._register_tool(
            "fake/boom",
            {
                "namespace": "fake",
                "action": "boom",
                "module": self.fake_module_name,
                "function": "boom_tool",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_boom_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        frame = self._make_frame('[t:fake/boom -> out] ', "fake", "boom", "out")
        runner = ToolRunner(dry_run=False)

        runner.run_step(frame, frame.steps[0])

        self.assertTrue(frame.errors)
        self.assertIn("boom", frame.errors[0]["message"])

    def test_dry_run_false_blocks_side_effect_direct_execution(self):
        frame = self._make_frame('[t:wa/send -> sent_msg] chat="Cornelia"; message="Hello"', "wa", "send", "sent_msg")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertTrue(result.ok)
        self.assertEqual(frame.steps[0].status, "STAGED")
        self.assertEqual(frame.pending_actions[0]["tool"], "wa/send")
        self.assertNotIn("sent_msg", frame.outputs)
        self.assertFalse(frame.tool_calls[0]["live"])

    def test_approved_pending_action_with_dry_run_false_is_blocked(self):
        frame = self._make_frame('[t:wa/send -> sent_msg] chat="Cornelia"; message="Hello"', "wa", "send", "sent_msg")
        runner = ToolRunner(dry_run=True)
        runner.run_step(frame, frame.steps[0])
        action_id = frame.pending_actions[0]["action_id"]
        approve_action(frame, action_id, approved_by="test", reason="approved")

        with self.assertRaises(ToolExecutionBlocked):
            ToolRunner(dry_run=False).execute_pending_action(frame, frame.pending_actions[0])

    def test_unknown_function_fails_clearly(self):
        self._register_tool(
            "fake/missing_func",
            {
                "namespace": "fake",
                "action": "missing_func",
                "module": self.fake_module_name,
                "function": "does_not_exist",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_missing_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        frame = self._make_frame('[t:fake/missing_func -> out] ', "fake", "missing_func", "out")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertIn("Tool function not found", result.error)

    def test_unknown_module_fails_clearly(self):
        self._register_tool(
            "fake/missing_module",
            {
                "namespace": "fake",
                "action": "missing_module",
                "module": "module_that_does_not_exist_12345",
                "function": "whatever",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": True,
                "output_type": "fake_missing_result",
                "required_args": [],
                "optional_args": [],
                "arg_types": {},
            },
        )
        frame = self._make_frame('[t:fake/missing_module -> out] ', "fake", "missing_module", "out")
        runner = ToolRunner(dry_run=False)

        result = runner.run_step(frame, frame.steps[0])

        self.assertFalse(result.ok)
        self.assertEqual(frame.steps[0].status, "FAILED")
        self.assertEqual(frame.state, "FAILED_EXECUTION")
        self.assertIn("could not be imported", result.error)


if __name__ == "__main__":
    unittest.main()
