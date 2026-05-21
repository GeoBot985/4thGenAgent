from __future__ import annotations

import unittest
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.release


class TestSheetWriteToolModuleExists(unittest.TestCase):
    def test_sheet_write_tool_module_exists(self):
        self.assertTrue((ROOT / "runtime" / "sheet_write_tool.py").is_file())

    def test_sheet_write_doc_exists(self):
        self.assertTrue((ROOT / "docs" / "live_google_sheets_write.md").is_file())


class TestSheetWriteToolImports(unittest.TestCase):
    def test_sheet_write_tool_imports(self):
        from runtime.sheet_write_tool import (
            SHEET_WRITE_TOOL_KEY,
            SHEET_WRITE_DEFAULT_CONFIG,
            SHEET_WRITE_AUDIT_EVENT_EXECUTED,
            SHEET_WRITE_AUDIT_EVENT_BLOCKED,
            build_sheet_write_pending_action,
            sheet_write_dry_run,
            sheet_write_live_execute,
            validate_sheet_write_payload,
            normalize_sheet_write_config,
            build_sheet_write_report,
            write_sheet_write_report,
            build_sheet_write_audit_event,
        )
        self.assertEqual(SHEET_WRITE_TOOL_KEY, "sheet/write_rows")

    def test_sheet_write_rows_guardrail_importable(self):
        from runtime.live_guardrails import guardrail_sheet_write_rows
        self.assertTrue(callable(guardrail_sheet_write_rows))


class TestSheetWriteDefaultConfigSafety(unittest.TestCase):
    def test_sheet_write_disabled_by_default(self):
        from runtime.sheet_write_tool import SHEET_WRITE_DEFAULT_CONFIG
        self.assertFalse(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]["enabled"])

    def test_max_rows_per_action_is_50(self):
        from runtime.sheet_write_tool import SHEET_WRITE_DEFAULT_CONFIG
        self.assertEqual(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]["max_rows_per_action"], 50)

    def test_allow_append_mode_true(self):
        from runtime.sheet_write_tool import SHEET_WRITE_DEFAULT_CONFIG
        self.assertTrue(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]["allow_append_mode"])

    def test_allow_update_mode_false(self):
        from runtime.sheet_write_tool import SHEET_WRITE_DEFAULT_CONFIG
        self.assertFalse(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]["allow_update_mode"])

    def test_allowed_spreadsheets_empty(self):
        from runtime.sheet_write_tool import SHEET_WRITE_DEFAULT_CONFIG
        self.assertEqual(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]["allowed_spreadsheets"], [])

    def test_allowed_ranges_empty(self):
        from runtime.sheet_write_tool import SHEET_WRITE_DEFAULT_CONFIG
        self.assertEqual(SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]["allowed_ranges"], [])


class TestSheetWriteToolRegistryEntry(unittest.TestCase):
    def test_sheet_write_rows_in_tool_registry(self):
        from runtime.tool_registry import TOOL_REGISTRY
        self.assertIn("sheet/write_rows", TOOL_REGISTRY)

    def test_sheet_write_rows_spec_side_effect_true(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("sheet/write_rows", {})
        self.assertTrue(spec.get("side_effect"))

    def test_sheet_write_rows_spec_requires_approval_true(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("sheet/write_rows", {})
        self.assertTrue(spec.get("requires_approval"))

    def test_sheet_write_rows_spec_allow_live_side_effect_true(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("sheet/write_rows", {})
        self.assertTrue(spec.get("allow_live_side_effect"))

    def test_sheet_write_rows_spec_live_guardrail_correct(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("sheet/write_rows", {})
        self.assertEqual(spec.get("live_guardrail"), "sheet_write_rows_guardrail")

    def test_sheet_write_rows_spec_output_type(self):
        from runtime.tool_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("sheet/write_rows", {})
        self.assertEqual(spec.get("output_type"), "sheet_write_result")


class TestSheetWriteNeverEnabledInNonLiveProfiles(unittest.TestCase):
    def test_demo_profile_blocks_sheet_write(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("demo"))

    def test_pilot_profile_blocks_sheet_write(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("pilot"))

    def test_release_profile_blocks_sheet_write(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("release"))

    def test_test_profile_blocks_sheet_write(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("test"))

    def test_dev_profile_blocks_sheet_write(self):
        from runtime.live_side_effect_contract import profile_allows_live_side_effects
        self.assertFalse(profile_allows_live_side_effects("dev"))


class TestSheetWriteAuditConstants(unittest.TestCase):
    def test_executed_event_name(self):
        from runtime.sheet_write_tool import SHEET_WRITE_AUDIT_EVENT_EXECUTED
        self.assertEqual(SHEET_WRITE_AUDIT_EVENT_EXECUTED, "LIVE_SHEET_ROWS_WRITTEN")

    def test_blocked_event_name(self):
        from runtime.sheet_write_tool import SHEET_WRITE_AUDIT_EVENT_BLOCKED
        self.assertEqual(SHEET_WRITE_AUDIT_EVENT_BLOCKED, "LIVE_SHEET_WRITE_BLOCKED")


class TestSheetWriteDefaultConfigPreventsLive(unittest.TestCase):
    def test_default_config_sheet_write_not_enabled(self):
        from runtime.sheet_write_tool import normalize_sheet_write_config
        cfg = normalize_sheet_write_config(None)
        self.assertFalse(cfg["enabled"])

    def test_demo_workflow_cannot_live_write(self):
        from runtime.sheet_write_tool import (
            build_sheet_write_pending_action,
            sheet_write_live_execute,
        )
        from runtime.tool_registry import TOOL_REGISTRY

        action = build_sheet_write_pending_action(
            action_id="pa-demo-001",
            business_ref="INV-demo",
            idempotency_key="idem-demo-001",
            spreadsheet_id="demo-sheet",
            range_name="Sheet1!A:B",
            rows=[["x"]],
            approved_by="operator",
            approved_at="2026-01-01T00:00:00Z",
            status="APPROVED",
        )
        spec = TOOL_REGISTRY.get("sheet/write_rows", {})
        result = sheet_write_live_execute(
            action,
            spec,
            manifest_live_execution={"enabled": True, "allowed_tools": ["sheet/write_rows"]},
            profile_name="demo",
            confirmation="LIVE-EXECUTE",
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["data"]["written"])


class TestSheetWriteRequiresApprovalAndConfirmation(unittest.TestCase):
    def test_live_write_requires_approved_action(self):
        from runtime.sheet_write_tool import (
            build_sheet_write_pending_action,
            sheet_write_live_execute,
        )

        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
            status="PENDING_APPROVAL",
        )
        result = sheet_write_live_execute(
            action,
            {"side_effect": True, "requires_approval": True, "allow_live_side_effect": True, "live_guardrail": "sheet_write_rows_guardrail"},
            manifest_live_execution={"enabled": True, "allowed_tools": ["sheet/write_rows"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
        )
        self.assertFalse(result["ok"])

    def test_live_write_requires_typed_confirmation(self):
        from runtime.sheet_write_tool import (
            build_sheet_write_pending_action,
            sheet_write_live_execute,
        )

        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
            approved_by="op",
            approved_at="2026-01-01T00:00:00Z",
            status="APPROVED",
        )
        result = sheet_write_live_execute(
            action,
            {"side_effect": True, "requires_approval": True, "allow_live_side_effect": True, "live_guardrail": "sheet_write_rows_guardrail"},
            manifest_live_execution={"enabled": True, "allowed_tools": ["sheet/write_rows"]},
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="wrong",
        )
        self.assertFalse(result["ok"])


class TestSheetWriteGuardrailChecks(unittest.TestCase):
    def test_guardrail_dispatched_by_run_live_guardrail(self):
        from runtime.live_guardrails import run_live_guardrail
        from runtime.sheet_write_tool import build_sheet_write_pending_action

        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
            status="APPROVED",
        )
        spec = {
            "side_effect": True,
            "requires_approval": True,
            "allow_live_side_effect": True,
            "live_guardrail": "sheet_write_rows_guardrail",
        }
        config = {
            "sheet_write": {
                "enabled": True,
                "allowed_spreadsheets": [],
                "allowed_ranges": [],
                "max_rows_per_action": 50,
                "allow_append_mode": True,
                "allow_update_mode": False,
            }
        }
        result = run_live_guardrail("sheet_write_rows_guardrail", action, spec, config=config)
        self.assertEqual(result["guardrail"], "sheet_write_rows_guardrail")

    def test_missing_idempotency_key_blocks_write(self):
        from runtime.live_guardrails import guardrail_sheet_write_rows
        from runtime.sheet_write_tool import build_sheet_write_pending_action

        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
            status="APPROVED",
        )
        action["idempotency_key"] = ""
        spec = {
            "side_effect": True,
            "requires_approval": True,
            "allow_live_side_effect": True,
            "live_guardrail": "sheet_write_rows_guardrail",
        }
        config = {
            "sheet_write": {
                "enabled": True,
                "allowed_spreadsheets": [],
                "allowed_ranges": [],
                "max_rows_per_action": 50,
                "allow_append_mode": True,
                "allow_update_mode": False,
            }
        }
        result = guardrail_sheet_write_rows(action, spec, config=config)
        self.assertFalse(result["ok"])

    def test_row_count_limit_enforced_in_guardrail(self):
        from runtime.live_guardrails import guardrail_sheet_write_rows
        from runtime.sheet_write_tool import build_sheet_write_pending_action

        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]] * 51,
            status="APPROVED",
        )
        spec = {
            "side_effect": True,
            "requires_approval": True,
            "allow_live_side_effect": True,
            "live_guardrail": "sheet_write_rows_guardrail",
        }
        config = {
            "sheet_write": {
                "enabled": True,
                "max_rows_per_action": 50,
                "allow_append_mode": True,
                "allow_update_mode": False,
            }
        }
        result = guardrail_sheet_write_rows(action, spec, config=config)
        self.assertFalse(result["ok"])


class TestSheetWriteDocContent(unittest.TestCase):
    def _read_doc(self) -> str:
        doc = ROOT / "docs" / "live_google_sheets_write.md"
        if doc.is_file():
            return doc.read_text(encoding="utf-8")
        return ""

    def test_doc_mentions_spec_134(self):
        doc = self._read_doc()
        self.assertIn("134", doc)

    def test_doc_mentions_tool_key(self):
        doc = self._read_doc()
        self.assertIn("sheet/write_rows", doc)

    def test_doc_mentions_disabled_by_default(self):
        doc = self._read_doc()
        self.assertIn("disabled", doc.lower())

    def test_doc_mentions_demo_profile_restriction(self):
        doc = self._read_doc()
        self.assertIn("demo", doc.lower())

    def test_doc_mentions_dry_run(self):
        doc = self._read_doc()
        self.assertIn("dry-run", doc.lower())

    def test_doc_mentions_append_mode(self):
        doc = self._read_doc()
        self.assertIn("append", doc.lower())

    def test_doc_mentions_idempotency(self):
        doc = self._read_doc()
        self.assertIn("idempotency", doc.lower())


if __name__ == "__main__":
    unittest.main()
