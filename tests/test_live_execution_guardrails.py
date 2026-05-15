from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from runtime.approval import approve_action
from runtime.errors import LiveExecutionBlocked, LiveExecutionNotAllowedForTool, LiveExecutionPolicyError
from runtime.live_execution import (
    assert_live_execution_allowed,
    manifest_allows_live_tool,
    normalize_live_execution_policy,
    tool_allows_live_side_effect,
    validate_live_execution_policy,
)
from runtime.live_guardrails import guardrail_blocked, guardrail_sheet_create, guardrail_sheet_write, run_live_guardrail
from runtime.manifest_loader import load_manifest
from runtime.memory_store import MemoryStore
from runtime.runtime_engine import RuntimeEngine
from runtime.tool_registry import TOOL_REGISTRY
from runtime.tool_runner import ToolRunner


SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
SMOKE_ROUTES_PATH = SMOKE_MANIFEST_DIR / "event_routes.json"

def smoke_manifest_path(name: str) -> Path:
    return SMOKE_MANIFEST_DIR / name


class LiveExecutionGuardrailTests(unittest.TestCase):
    def _staged_live_frame(self, manifest_path: str, payload: dict[str, object] | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            frame = engine.handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_create_allowed" if "sheet_create" in manifest_path else "manual.live_sheet_write_allowed",
                    "manual",
                    payload=payload or {},
                ),
                dry_run=True,
            )
            manifest = load_manifest(manifest_path)
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            return runtime_dir, frame, manifest

    def test_normalize_live_execution_policy_defaults_disabled(self):
        policy = normalize_live_execution_policy(None)
        self.assertEqual(policy["enabled"], False)
        self.assertEqual(policy["allowed_tools"], [])
        self.assertTrue(policy["requires_approval"])

    def test_validate_live_execution_policy_accepts_valid_enabled_policy(self):
        policy = {"enabled": True, "allowed_tools": ["sheet/write"], "requires_approval": True}
        validate_live_execution_policy(policy)

    def test_validate_live_execution_policy_rejects_non_dict(self):
        with self.assertRaises(LiveExecutionPolicyError):
            validate_live_execution_policy("bad")  # type: ignore[arg-type]

    def test_validate_live_execution_policy_rejects_non_bool_enabled(self):
        with self.assertRaises(LiveExecutionPolicyError):
            validate_live_execution_policy({"enabled": "yes", "allowed_tools": [], "requires_approval": True})

    def test_validate_live_execution_policy_rejects_non_list_allowed_tools(self):
        with self.assertRaises(LiveExecutionPolicyError):
            validate_live_execution_policy({"enabled": True, "allowed_tools": "sheet/write", "requires_approval": True})

    def test_validate_live_execution_policy_rejects_non_string_allowed_tool(self):
        with self.assertRaises(LiveExecutionPolicyError):
            validate_live_execution_policy({"enabled": True, "allowed_tools": ["sheet/write", 1], "requires_approval": True})

    def test_validate_live_execution_policy_rejects_requires_approval_false(self):
        with self.assertRaises(LiveExecutionPolicyError):
            validate_live_execution_policy({"enabled": True, "allowed_tools": ["sheet/write"], "requires_approval": False})

    def test_live_sheet_create_allowed_loads_from_smoke_fixture(self):
        manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
        self.assertEqual(manifest.manifest_id, "smoke.live_sheet_create_allowed")

    def test_live_sheet_write_allowed_loads_from_smoke_fixture(self):
        manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_write_allowed.manifest.json"))
        self.assertEqual(manifest.manifest_id, "smoke.live_sheet_write_allowed")

    def test_live_side_effect_blocked_by_tool_loads_from_smoke_fixture(self):
        manifest = load_manifest(smoke_manifest_path("smoke_live_side_effect_blocked_by_tool.manifest.json"))
        self.assertEqual(manifest.manifest_id, "smoke.live_side_effect_blocked_by_tool")

    def test_manifest_allows_live_tool_true_when_enabled_and_listed(self):
        manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_write_allowed.manifest.json"))
        self.assertTrue(manifest_allows_live_tool(manifest, "sheet/write"))

    def test_manifest_allows_live_tool_false_when_disabled(self):
        manifest = load_manifest(smoke_manifest_path("smoke_live_side_effect_blocked_by_manifest.manifest.json"))
        self.assertFalse(manifest_allows_live_tool(manifest, "sheet/create"))

    def test_manifest_allows_live_tool_false_when_tool_missing(self):
        manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
        self.assertFalse(manifest_allows_live_tool(manifest, "sheet/write"))

    def test_tool_allows_live_side_effect_true_for_sheet_create(self):
        self.assertTrue(tool_allows_live_side_effect(TOOL_REGISTRY["sheet/create"]))

    def test_tool_allows_live_side_effect_true_for_sheet_write(self):
        self.assertTrue(tool_allows_live_side_effect(TOOL_REGISTRY["sheet/write"]))

    def test_tool_allows_live_side_effect_false_for_whatsapp_send(self):
        self.assertFalse(tool_allows_live_side_effect(TOOL_REGISTRY["wa/send"]))

    def test_tool_allows_live_side_effect_false_for_gmail_send(self):
        self.assertFalse(tool_allows_live_side_effect(TOOL_REGISTRY["g/send"]))

    def test_tool_allows_live_side_effect_false_for_gobook_book(self):
        self.assertFalse(tool_allows_live_side_effect(TOOL_REGISTRY["gb/book"]))

    def test_assert_live_execution_allowed_passes_all_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            frame = engine.handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_create_allowed",
                    "manual",
                    payload={"title": "Live Guardrail"},
                ),
                dry_run=True,
            )
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])
            assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=True)

    def test_assert_live_execution_allowed_blocks_runtime_live_mode_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            frame = engine.handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_create_allowed",
                    "manual",
                    payload={"title": "Live Guardrail"},
                ),
                dry_run=True,
            )
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])
            with self.assertRaises(LiveExecutionBlocked):
                assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=False)

    def test_assert_live_execution_allowed_blocks_wrong_frame_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
            frame = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH).handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_create_allowed",
                    "manual",
                    payload={"title": "Live Guardrail"},
                ),
                dry_run=True,
            )
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            frame.state = "READY"
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])
            with self.assertRaises(LiveExecutionBlocked):
                assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=True)

    def test_assert_live_execution_allowed_blocks_non_approved_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
            frame = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH).handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_create_allowed",
                    "manual",
                    payload={"title": "Live Guardrail"},
                ),
                dry_run=True,
            )
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])
            with self.assertRaises(LiveExecutionBlocked):
                assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=True)

    def test_assert_live_execution_allowed_blocks_manifest_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            engine = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH)
            frame = engine.handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_side_effect_blocked_by_manifest",
                    "manual",
                    payload={"title": "Blocked"},
                ),
                dry_run=True,
            )
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            manifest = load_manifest(smoke_manifest_path("smoke_live_side_effect_blocked_by_manifest.manifest.json"))
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])
            with self.assertRaises(LiveExecutionBlocked):
                assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=True)

    def test_assert_live_execution_allowed_blocks_tool_not_in_manifest_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
            frame = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH).handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_write_allowed",
                    "manual",
                    payload={
                        "spreadsheet_id": "sheet-123",
                        "range_name": "Sheet1!A1:B2",
                        "values_json": "[[\"a\", \"b\"]]",
                        "mode": "append",
                    },
                ),
                dry_run=True,
            )
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/write"])
            with self.assertRaises(LiveExecutionBlocked):
                assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=True)

    def test_assert_live_execution_allowed_blocks_tool_registry_disallow(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            manifest = load_manifest(smoke_manifest_path("smoke_live_sheet_create_allowed.manifest.json"))
            frame = RuntimeEngine(runtime_data_dir=runtime_dir, persist_runs=False, manifest_dir=SMOKE_MANIFEST_DIR, routes_path=SMOKE_ROUTES_PATH).handle_event(
                __import__("runtime.events", fromlist=["create_event"]).create_event(
                    "manual.live_sheet_create_allowed",
                    "manual",
                    payload={"title": "Live Guardrail"},
                ),
                dry_run=True,
            )
            approve_action(frame, frame.pending_actions[0]["action_id"], approved_by="tester", reason="approve")
            tool_spec = deepcopy(TOOL_REGISTRY["sheet/create"])
            tool_spec["allow_live_side_effect"] = False
            with self.assertRaises(LiveExecutionNotAllowedForTool):
                assert_live_execution_allowed(frame, manifest, frame.pending_actions[0], tool_spec, runtime_live_mode=True)

    def test_sheet_create_guardrail_passes_valid_title(self):
        result = guardrail_sheet_create({"args": {"title": "Sheet Title"}}, {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["guardrail"], "sheet_create")

    def test_sheet_create_guardrail_fails_empty_title(self):
        result = guardrail_sheet_create({"args": {"title": ""}}, {})
        self.assertFalse(result["ok"])

    def test_sheet_create_guardrail_fails_long_title(self):
        result = guardrail_sheet_create({"args": {"title": "x" * 121}}, {})
        self.assertFalse(result["ok"])

    def test_sheet_create_guardrail_fails_path_separator(self):
        result = guardrail_sheet_create({"args": {"title": "bad/title"}}, {})
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_passes_valid_append(self):
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": "[[\"a\", \"b\"]]", "mode": "append"}},
            {},
        )
        self.assertTrue(result["ok"])

    def test_sheet_write_guardrail_fails_missing_spreadsheet_id(self):
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "", "range_name": "Sheet1!A1:B2", "values_json": "[[\"a\"]]", "mode": "append"}},
            {},
        )
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_fails_invalid_values_json(self):
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": "bad", "mode": "append"}},
            {},
        )
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_fails_non_2d_values_json(self):
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": "[1, 2, 3]", "mode": "append"}},
            {},
        )
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_fails_too_many_rows(self):
        values = [[1] for _ in range(101)]
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": json.dumps(values), "mode": "append"}},
            {},
        )
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_fails_too_many_columns(self):
        values = [list(range(51))]
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": json.dumps(values), "mode": "append"}},
            {},
        )
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_fails_too_many_cells(self):
        values = [list(range(51)) for _ in range(20)]
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": json.dumps(values), "mode": "append"}},
            {},
        )
        self.assertFalse(result["ok"])

    def test_sheet_write_guardrail_records_formula_cell_count(self):
        result = guardrail_sheet_write(
            {"args": {"spreadsheet_id": "sheet-123", "range_name": "Sheet1!A1:B2", "values_json": "[[\"=SUM(A1:A2)\", \"x\"]]", "mode": "append"}},
            {},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["formula_cells_detected"], 1)

    def test_blocked_guardrail_always_fails(self):
        result = guardrail_blocked({}, {"live_guardrail": "blocked"})
        self.assertFalse(result["ok"])
        self.assertEqual(run_live_guardrail("blocked", {}, {"live_guardrail": "blocked"})["ok"], False)


if __name__ == "__main__":
    unittest.main()
