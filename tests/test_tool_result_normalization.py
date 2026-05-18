import sys
import types
import unittest
from dataclasses import dataclass

from runtime.models import Manifest, ManifestStep, ParsedCommand, StepRuntime, ToolResult
from runtime.taskframe import create_taskframe
from runtime.tool_registry import TOOL_REGISTRY
from runtime.tool_runner import ToolRunner, normalize_tool_result


@dataclass
class WorkspaceResultLike:
    ok: bool
    action: str
    output: str = ""
    error: str = ""
    payload: dict | None = None


class ToolResultNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.original_registry = {}
        self.module_name = "fake_tools_normalization"
        self.fake_module = types.ModuleType(self.module_name)

        def boom_tool():
            raise RuntimeError("boom")

        self.fake_module.boom_tool = boom_tool
        sys.modules[self.module_name] = self.fake_module

    def tearDown(self):
        for key, value in self.original_registry.items():
            if value is None:
                TOOL_REGISTRY.pop(key, None)
            else:
                TOOL_REGISTRY[key] = value
        sys.modules.pop(self.module_name, None)

    def _register_tool(self, key: str, spec: dict) -> None:
        if key not in self.original_registry:
            self.original_registry[key] = TOOL_REGISTRY.get(key)
        TOOL_REGISTRY[key] = spec

    def _make_frame(self, command: str, namespace: str, action: str, output_alias: str | None = None):
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
            manifest_id="normalization.test",
            name="Normalization Test",
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
        frame = create_taskframe(manifest)
        frame.state = "RUNNING"
        return frame

    def test_normalize_dict_result(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        result = normalize_tool_result({"value": 1}, "fake/read", spec, {}, dry_run=False)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"value": 1})
        self.assertEqual(result.metadata["tool"], "fake/read")
        self.assertEqual(result.metadata["function"], "boom_tool")
        self.assertTrue(result.metadata["live"])
        self.assertFalse(result.metadata["dry_run"])

    def test_normalize_list_result(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        result = normalize_tool_result([1, 2], "fake/read", spec, {}, dry_run=False)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, [1, 2])

    def test_normalize_string_result(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        result = normalize_tool_result("hello", "fake/read", spec, {}, dry_run=False)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, "hello")

    def test_normalize_bool_result(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        result = normalize_tool_result(True, "fake/read", spec, {}, dry_run=False)

        self.assertTrue(result.ok)
        self.assertTrue(result.data)

    def test_normalize_none_result(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }

        result = normalize_tool_result(None, "fake/read", spec, {}, dry_run=False)

        self.assertTrue(result.ok)
        self.assertIsNone(result.data)

    def test_normalize_toolresult_result(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }
        original = ToolResult(
            ok=True,
            type="fake_read_result",
            data={"x": 1},
            evidence={"tool": "fake/read", "mode": "live", "source": "builtin", "operation": "read", "input_refs": [], "output_ref": "fake_read_result"},
            error="",
            raw={"x": 1},
            metadata={"custom": "value"},
        )

        result = normalize_tool_result(original, "fake/read", spec, {}, dry_run=False)

        self.assertEqual(result.data, {"x": 1})
        self.assertIsInstance(result.evidence, dict)
        self.assertTrue(result.evidence)
        self.assertEqual(result.metadata["custom"], "value")
        self.assertEqual(result.metadata["tool"], "fake/read")
        self.assertTrue(result.metadata["live"])

    def test_normalize_workspace_result_like_object(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }
        original = WorkspaceResultLike(ok=True, action="fake_read", output="ok", payload={"json": [1]})

        result = normalize_tool_result(original, "fake/read", spec, {}, dry_run=False)

        self.assertTrue(result.ok)
        self.assertEqual(result.data["action"], "fake_read")
        self.assertEqual(result.data["output"], "ok")
        self.assertEqual(result.data["payload"], {"json": [1]})
        self.assertIsInstance(result.evidence, dict)
        self.assertTrue(result.evidence)
        self.assertIs(result.raw, original)

    def test_normalize_failed_workspace_result_like_object(self):
        spec = {
            "namespace": "fake",
            "action": "read",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_read_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }
        original = WorkspaceResultLike(ok=False, action="fake_read", output="", error="boom")

        result = normalize_tool_result(original, "fake/read", spec, {}, dry_run=False)

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "boom")
        self.assertEqual(result.data["action"], "fake_read")
        self.assertIsInstance(result.evidence, dict)
        self.assertTrue(result.evidence)

    def test_exception_result_path_returns_error_tool_result(self):
        spec = {
            "namespace": "fake",
            "action": "boom",
            "module": self.module_name,
            "function": "boom_tool",
            "side_effect": False,
            "requires_approval": False,
            "allow_live": True,
            "output_type": "fake_boom_result",
            "required_args": [],
            "optional_args": [],
            "arg_types": {},
        }
        self._register_tool("fake/boom", spec)
        frame = self._make_frame('[t:fake/boom -> out] ', "fake", "boom", "out")
        runner = ToolRunner(dry_run=False)

        result = runner.execute_live_tool(frame, frame.steps[0], "fake/boom", spec, {})

        self.assertFalse(result.ok)
        self.assertIn("boom", result.error)
        self.assertEqual(result.metadata["exception_type"], "ToolFunctionError")


if __name__ == "__main__":
    unittest.main()
