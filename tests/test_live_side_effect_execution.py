from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from copy import deepcopy
from pathlib import Path

from runtime.approval import approve_action
from runtime.events import create_event
from runtime.errors import LiveExecutionBlocked
from runtime.manifest_loader import load_manifest
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe import create_taskframe
from runtime.tool_registry import TOOL_REGISTRY
from runtime.tool_runner import ToolRunner


class LiveSideEffectExecutionTests(unittest.TestCase):
    def setUp(self):
        self._saved_registry: dict[str, dict | None] = {}
        self._modules_to_cleanup: list[str] = []

    def tearDown(self):
        for key, value in self._saved_registry.items():
            if value is None:
                TOOL_REGISTRY.pop(key, None)
            else:
                TOOL_REGISTRY[key] = value
        for module_name in self._modules_to_cleanup:
            sys.modules.pop(module_name, None)

    def _register_tool(self, key: str, spec: dict) -> None:
        if key not in self._saved_registry:
            self._saved_registry[key] = TOOL_REGISTRY.get(key)
        TOOL_REGISTRY[key] = spec

    def _install_module(self, module_name: str, **attrs) -> None:
        module = types.ModuleType(module_name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[module_name] = module
        self._modules_to_cleanup.append(module_name)

    def _staged_frame(
        self,
        runtime_dir: Path,
        event_type: str,
        payload: dict[str, object] | None = None,
        approve: bool = True,
    ):
        engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False)
        frame = engine.handle_event(create_event(event_type, "manual", payload=payload or {}), dry_run=True)
        self.assertEqual(frame.state, "WAITING_FOR_EXECUTE")
        manifest = load_manifest(
            {
                "manual.live_sheet_create_allowed": "manifests/smoke_live_sheet_create_allowed.manifest.json",
                "manual.live_sheet_write_allowed": "manifests/smoke_live_sheet_write_allowed.manifest.json",
                "manual.live_side_effect_blocked_by_manifest": "manifests/smoke_live_side_effect_blocked_by_manifest.manifest.json",
                "manual.live_side_effect_blocked_by_tool": "manifests/smoke_live_side_effect_blocked_by_tool.manifest.json",
            }[event_type]
        )
        if approve:
            action_id = frame.pending_actions[0]["action_id"]
            approve_action(frame, action_id, approved_by="tester", reason="approve")
        return frame, manifest

    def _approve_frame(self, frame):
        approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
        return frame.pending_actions[0]

    def _install_sheet_module(self, module_name: str = "fake_live_sheet_tools", write_result: dict | None = None):
        def sheet_create(title: str):
            return {
                "spreadsheetId": "fake_sheet_123",
                "title": title,
                "spreadsheetUrl": "https://example.test/fake_sheet_123",
            }

        def sheet_write(spreadsheet_id: str, range_name: str, values_json: str, mode: str = "append"):
            return write_result or {
                "spreadsheetId": spreadsheet_id,
                "rangeName": range_name,
                "mode": mode,
                "updatedRange": range_name,
                "updatedRows": 1,
                "updatedColumns": 2,
            }

        self._install_module(module_name, sheet_create=sheet_create, sheet_write=sheet_write)
        self._register_tool(
            "sheet/create",
            {
                "namespace": "sheet",
                "action": "create",
                "module": module_name,
                "function": "sheet_create",
                "side_effect": True,
                "requires_approval": True,
                "allow_live": False,
                "allow_live_side_effect": True,
                "live_guardrail": "sheet_create",
                "output_type": "sheet_create_result",
                "required_args": ["title"],
                "optional_args": [],
                "arg_types": {},
            },
        )
        self._register_tool(
            "sheet/write",
            {
                "namespace": "sheet",
                "action": "write",
                "module": module_name,
                "function": "sheet_write",
                "side_effect": True,
                "requires_approval": True,
                "allow_live": False,
                "allow_live_side_effect": True,
                "live_guardrail": "sheet_write",
                "output_type": "sheet_write_result",
                "required_args": ["spreadsheet_id", "range_name", "values_json"],
                "optional_args": ["mode"],
                "arg_types": {},
            },
        )

    def test_dry_run_approved_execution_still_works_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Dry run"})
            runner = ToolRunner(dry_run=True)

            result = runner.execute_pending_action(frame, frame.pending_actions[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.pending_actions[0]["status"], "EXECUTED")
            self.assertIn("created_sheet", frame.outputs)
            self.assertTrue(frame.outputs["created_sheet"]["dry_run"])

    def test_live_pending_action_requires_approved_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Live"}, approve=False)
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(frame.pending_actions[0]["status"], "FAILED")
            self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_live_pending_action_requires_live_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Live"})
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=False)

            self.assertFalse(result.ok)
            self.assertEqual(frame.pending_actions[0]["status"], "FAILED")

    def test_live_pending_action_requires_manifest_policy_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, _ = self._staged_frame(runtime_dir, "manual.live_side_effect_blocked_by_manifest", {"title": "Blocked"})
            manifest = load_manifest("manifests/smoke_live_side_effect_blocked_by_manifest.manifest.json")
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_live_pending_action_requires_tool_allow_live_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_side_effect_blocked_by_tool", {})
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(frame.pending_actions[0]["status"], "FAILED")

    def test_live_pending_action_runs_guardrail(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertTrue(result.ok)
            self.assertEqual(frame.executed_actions[0]["guardrail"], "sheet_create")
            self.assertTrue(frame.executed_actions[0]["live_side_effect"])

    def test_guardrail_failure_blocks_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "test-delete-unsafe"})
            called = {"count": 0}

            def sheet_create(title: str):
                called["count"] += 1
                return {"spreadsheetId": "x", "title": title}

            self._install_module("fake_live_sheet_tools_fail_guardrail", sheet_create=sheet_create)
            self._register_tool(
                "sheet/create",
                {
                    "namespace": "sheet",
                    "action": "create",
                    "module": "fake_live_sheet_tools_fail_guardrail",
                    "function": "sheet_create",
                    "side_effect": True,
                    "requires_approval": True,
                    "allow_live": False,
                    "allow_live_side_effect": True,
                    "live_guardrail": "sheet_create",
                    "output_type": "sheet_create_result",
                    "required_args": ["title"],
                    "optional_args": [],
                    "arg_types": {},
                },
            )
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(called["count"], 0)
            self.assertEqual(frame.pending_actions[0]["status"], "FAILED")

    def test_successful_fake_sheet_create_live_execution_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertTrue(result.ok)
            self.assertTrue(frame.outputs["created_sheet"]["live"])
            self.assertFalse(frame.outputs["created_sheet"]["dry_run"])
            self.assertEqual(frame.pending_actions[0]["status"], "EXECUTED")
            self.assertEqual(frame.executed_actions[0]["status"], "EXECUTED")

    def test_successful_fake_sheet_write_live_execution_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(
                runtime_dir,
                "manual.live_sheet_write_allowed",
                {
                    "spreadsheet_id": "sheet-123",
                    "range_name": "Sheet1!A1:B2",
                    "values_json": "[[\"a\", \"b\"]]",
                    "mode": "append",
                },
            )
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["write_result"]["result"]["updatedRange"], "Sheet1!A1:B2")
            self.assertTrue(frame.executed_actions[0]["live_side_effect"])
            self.assertEqual(frame.executed_actions[0]["guardrail"], "sheet_write")

    def test_failed_live_function_marks_pending_action_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})

            def sheet_create(title: str):
                raise RuntimeError("temporary failure")

            self._install_module("fake_live_sheet_tools_fail", sheet_create=sheet_create)
            self._register_tool(
                "sheet/create",
                {
                    "namespace": "sheet",
                    "action": "create",
                    "module": "fake_live_sheet_tools_fail",
                    "function": "sheet_create",
                    "side_effect": True,
                    "requires_approval": True,
                    "allow_live": False,
                    "allow_live_side_effect": True,
                    "live_guardrail": "sheet_create",
                    "output_type": "sheet_create_result",
                    "required_args": ["title"],
                    "optional_args": [],
                    "arg_types": {},
                },
            )
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(frame.pending_actions[0]["status"], "FAILED")
            self.assertEqual(frame.state, "FAILED_EXECUTION")

    def test_failed_live_function_records_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})

            def sheet_create(title: str):
                raise RuntimeError("temporary failure")

            self._install_module("fake_live_sheet_tools_fail_error", sheet_create=sheet_create)
            self._register_tool(
                "sheet/create",
                {
                    "namespace": "sheet",
                    "action": "create",
                    "module": "fake_live_sheet_tools_fail_error",
                    "function": "sheet_create",
                    "side_effect": True,
                    "requires_approval": True,
                    "allow_live": False,
                    "allow_live_side_effect": True,
                    "live_guardrail": "sheet_create",
                    "output_type": "sheet_create_result",
                    "required_args": ["title"],
                    "optional_args": [],
                    "arg_types": {},
                },
            )
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertTrue(frame.errors)
            self.assertIn("temporary failure", frame.errors[-1]["message"])

    def test_dry_run_live_mode_with_dry_run_true_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})
            self._install_sheet_module()
            runner = ToolRunner(dry_run=True)

            with self.assertRaises(LiveExecutionBlocked):
                runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

    def test_wa_send_live_execution_blocked_even_if_manifest_allowlist_includes_wa_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            frame, manifest = self._staged_frame(runtime_dir, "manual.live_side_effect_blocked_by_tool", {})
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(frame.pending_actions[0]["status"], "FAILED")

    def test_gb_book_live_execution_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest_path = runtime_dir / "gb_live_allowed.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_id": "smoke.gb_live_allowed",
                        "name": "Smoke Test - GB Live Allowed",
                        "version": 1,
                        "live_execution": {
                            "enabled": True,
                            "allowed_tools": ["gb/book"],
                            "requires_approval": True,
                        },
                        "trigger": {"type": "manual"},
                        "inputs": [],
                        "steps": [
                            {
                                "id": "stage_booking",
                                "command": "[t:gb/book -> booking] date=\"2026-05-01\"; time_value=\"18:00\"; court=\"Court 1\"; confirm=true; slowmo=0",
                            }
                        ],
                        "validations": [],
                        "completion": {"success_pending_actions": ["booking"], "allow_pending_approval": True},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=runtime_dir)
            # Avoid route lookup by creating frame directly from the manifest.
            manifest = load_manifest(manifest_path)
            frame = engine.orchestrator.create_frame_from_manifest(manifest)
            frame = engine.orchestrator.prepare_frame(frame)
            frame = engine.orchestrator.run_until_blocked(frame, manifest, dry_run=True)
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            self._install_sheet_module()
            runner = ToolRunner(dry_run=False)

            result = runner.execute_live_pending_action(frame, manifest, frame.pending_actions[0], runtime_live_mode=True)

            self.assertFalse(result.ok)
            self.assertEqual(frame.state, "FAILED_EXECUTION")


if __name__ == "__main__":
    unittest.main()
