from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

from runtime.approval import approve_action
from runtime.approval_commands import ApprovalCommandRunner
from runtime.events import create_event
from runtime.manifest_loader import load_manifest
from runtime.persistence import PersistenceManager, load_taskframe_dict, save_taskframe, taskframe_exists
from runtime.run_ledger import find_ledger_record
from runtime.runtime_engine import RuntimeEngine
from runtime.taskframe import create_taskframe
from runtime.tool_registry import TOOL_REGISTRY


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
SMOKE_ROUTES_PATH = SMOKE_MANIFEST_DIR / "event_routes.json"


class LiveExecutionPersistenceTests(unittest.TestCase):
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

    def _install_sheet_tools(self, module_name: str = "fake_persist_live_sheet_tools") -> None:
        module = types.ModuleType(module_name)

        def sheet_create(title: str):
            return {
                "spreadsheetId": "fake_sheet_123",
                "title": title,
                "spreadsheetUrl": "https://example.test/fake_sheet_123",
            }

        def sheet_write(spreadsheet_id: str, range_name: str, values_json: str, mode: str = "append"):
            return {
                "spreadsheetId": spreadsheet_id,
                "rangeName": range_name,
                "mode": mode,
                "updatedRange": range_name,
                "updatedRows": 1,
                "updatedColumns": 2,
            }

        module.sheet_create = sheet_create
        module.sheet_write = sheet_write
        sys.modules[module_name] = module
        self._modules_to_cleanup.append(module_name)
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

    def _make_live_command_frame(self, target_frame_id: str, confirm_live: str = "true"):
        manifest = load_manifest("manifests/smoke_approve_pending_action.manifest.json")
        frame = create_taskframe(
            manifest,
            inputs={
                "frame_id": target_frame_id,
                "action_id": "pa_1",
                "approved_by": "tester",
                "reason": "live execution",
                "confirm_live": confirm_live,
            },
        )
        frame.steps[0].command = f"[a:execute_live_approved -> result] frame_id=$inputs.frame_id; confirm_live={confirm_live}"
        frame.steps[0].action = "execute_live_approved"
        frame.steps[0].output_alias = "result"
        return frame

    def _stage_target(self, runtime_dir: Path, event_type: str, payload: dict[str, object]):
        engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=True, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
        target = engine.handle_event(create_event(event_type, "manual", payload=payload), dry_run=True)
        action_id = target.pending_actions[0]["action_id"]
        approval_frame = engine.handle_event(
            create_event(
                "manual.approve_pending_action",
                "manual",
                payload={
                    "frame_id": target.frame_id,
                    "action_id": action_id,
                    "approved_by": "manual_smoke",
                    "reason": "approve for live",
                },
            ),
            dry_run=True,
        )
        self.assertEqual(approval_frame.state, "COMPLETED")
        return engine, target, action_id

    def test_execute_live_approved_without_confirm_live_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine, target, action_id = self._stage_target(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Live"})
            self._install_sheet_tools()
            command_frame = self._make_live_command_frame(target.frame_id, confirm_live="false")
            command_frame.inputs["action_id"] = action_id
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, manifest_dir=SMOKE_MANIFEST_DIR)

            result = runner.run_step(command_frame, command_frame.steps[0])

            self.assertFalse(result.ok)
            self.assertIn("confirm_live", result.error)

    def test_execute_live_approved_against_manifest_disabled_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine, target, action_id = self._stage_target(runtime_dir, "manual.live_side_effect_blocked_by_manifest", {"title": "Blocked"})
            self._install_sheet_tools()
            command_frame = self._make_live_command_frame(target.frame_id, confirm_live="true")
            command_frame.inputs["action_id"] = action_id
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, manifest_dir=SMOKE_MANIFEST_DIR)

            result = runner.run_step(command_frame, command_frame.steps[0])

            self.assertFalse(result.ok)
            target_snapshot = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertIn(target_snapshot["state"], {"FAILED_EXECUTION", "WAITING_FOR_EXECUTE"})

    def test_execute_live_approved_against_blocked_tool_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine, target, action_id = self._stage_target(runtime_dir, "manual.live_side_effect_blocked_by_tool", {})
            self._install_sheet_tools()
            command_frame = self._make_live_command_frame(target.frame_id, confirm_live="true")
            command_frame.inputs["action_id"] = action_id
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, manifest_dir=SMOKE_MANIFEST_DIR)

            result = runner.run_step(command_frame, command_frame.steps[0])

            self.assertFalse(result.ok)
            target_snapshot = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertIn(target_snapshot["state"], {"FAILED_EXECUTION", "WAITING_FOR_EXECUTE"})

    def test_persisted_live_approval_flow_updates_target_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._install_sheet_tools()
            engine, target, action_id = self._stage_target(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})
            command_frame = self._make_live_command_frame(target.frame_id, confirm_live="true")
            command_frame.inputs["action_id"] = action_id
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, manifest_dir=SMOKE_MANIFEST_DIR)

            result = runner.run_step(command_frame, command_frame.steps[0])
            PersistenceManager(runtime_dir).save_snapshot(command_frame)

            self.assertTrue(result.ok)
            self.assertEqual(command_frame.outputs["result"]["target_frame_state"], "COMPLETED")

            target_snapshot = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(target_snapshot["state"], "COMPLETED")
            self.assertEqual(target_snapshot["pending_actions"][0]["status"], "EXECUTED")
            self.assertTrue(target_snapshot["executed_actions"][0]["live_side_effect"])
            self.assertEqual(find_ledger_record(target.frame_id, runtime_dir)["state"], "COMPLETED")
            self.assertTrue(taskframe_exists(command_frame.frame_id, runtime_dir))
            self.assertNotEqual(command_frame.frame_id, target.frame_id)

    def test_persisted_live_approval_flow_with_live_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._install_sheet_tools()
            engine, target, action_id = self._stage_target(
                runtime_dir,
                "manual.live_sheet_write_allowed",
                {
                    "spreadsheet_id": "sheet-123",
                    "range_name": "Sheet1!A1:B2",
                    "values_json": "[[\"a\", \"b\"]]",
                    "mode": "append",
                },
            )
            command_frame = self._make_live_command_frame(target.frame_id, confirm_live="true")
            command_frame.inputs["action_id"] = action_id
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, manifest_dir=SMOKE_MANIFEST_DIR)

            result = runner.run_step(command_frame, command_frame.steps[0])
            PersistenceManager(runtime_dir).save_snapshot(command_frame)

            self.assertTrue(result.ok)
            target_snapshot = load_taskframe_dict(target.frame_id, runtime_dir)
            self.assertEqual(target_snapshot["state"], "COMPLETED")
            self.assertEqual(target_snapshot["pending_actions"][0]["status"], "EXECUTED")

    def test_approval_command_frame_is_separate_from_target_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._install_sheet_tools()
            engine, target, action_id = self._stage_target(runtime_dir, "manual.live_sheet_create_allowed", {"title": "Runtime Live Smoke"})
            command_frame = self._make_live_command_frame(target.frame_id, confirm_live="true")
            command_frame.inputs["action_id"] = action_id
            runner = ApprovalCommandRunner(runtime_data_dir=runtime_dir, manifest_dir=SMOKE_MANIFEST_DIR)

            result = runner.run_step(command_frame, command_frame.steps[0])
            PersistenceManager(runtime_dir).save_snapshot(command_frame)

            self.assertTrue(result.ok)
            self.assertNotEqual(command_frame.frame_id, target.frame_id)
            self.assertTrue(taskframe_exists(command_frame.frame_id, runtime_dir))
            self.assertTrue(taskframe_exists(target.frame_id, runtime_dir))


if __name__ == "__main__":
    unittest.main()
