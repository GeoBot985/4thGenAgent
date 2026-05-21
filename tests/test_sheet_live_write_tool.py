from __future__ import annotations

import unittest

from runtime.sheet_write_tool import (
    SHEET_WRITE_AUDIT_EVENT_BLOCKED,
    SHEET_WRITE_AUDIT_EVENT_EXECUTED,
    SHEET_WRITE_DEFAULT_CONFIG,
    SHEET_WRITE_TOOL_KEY,
    build_sheet_write_pending_action,
    normalize_sheet_write_config,
    sheet_write_dry_run,
    sheet_write_live_execute,
    validate_sheet_write_payload,
)


def _approved_action(
    *,
    spreadsheet_id: str = "sheet-abc123",
    range_name: str = "ExceptionRegister!A:H",
    rows: list | None = None,
    write_mode: str = "append",
    business_ref: str = "INV-10042",
    idempotency_key: str = "idem-sheet-001",
) -> dict:
    return build_sheet_write_pending_action(
        action_id="pa-sheet-001",
        business_ref=business_ref,
        idempotency_key=idempotency_key,
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        rows=rows or [["INV-10042", "PO mismatch", "open"]],
        write_mode=write_mode,
        approved_by="operator@example.com",
        approved_at="2026-01-01T00:00:00Z",
        status="APPROVED",
    )


def _live_tool_spec() -> dict:
    return {
        "side_effect": True,
        "requires_approval": True,
        "allow_live": True,
        "allow_live_side_effect": True,
        "live_guardrail": "sheet_write_rows_guardrail",
    }


def _live_manifest() -> dict:
    return {
        "enabled": True,
        "allowed_tools": ["sheet/write_rows"],
        "allowed_actions": [],
        "max_live_actions": 1,
        "requires_operator_confirmation": True,
    }


def _enabled_config() -> dict:
    return {
        "sheet_write": {
            "enabled": True,
            "allowed_spreadsheets": ["sheet-abc123"],
            "allowed_ranges": ["ExceptionRegister!A:H"],
            "blocked_ranges": [],
            "max_rows_per_action": 50,
            "allow_update_mode": False,
            "allow_append_mode": True,
        }
    }


class TestSheetWriteToolKey(unittest.TestCase):
    def test_tool_key_is_sheet_write_rows(self):
        self.assertEqual(SHEET_WRITE_TOOL_KEY, "sheet/write_rows")


class TestSheetWriteDefaultConfig(unittest.TestCase):
    def test_enabled_is_false_by_default(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertFalse(cfg["enabled"])

    def test_max_rows_per_action_default_is_50(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertEqual(cfg["max_rows_per_action"], 50)

    def test_allow_append_mode_is_true_by_default(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertTrue(cfg["allow_append_mode"])

    def test_allow_update_mode_is_false_by_default(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertFalse(cfg["allow_update_mode"])

    def test_allowed_spreadsheets_empty_by_default(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertEqual(cfg["allowed_spreadsheets"], [])

    def test_allowed_ranges_empty_by_default(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertEqual(cfg["allowed_ranges"], [])

    def test_blocked_ranges_empty_by_default(self):
        cfg = SHEET_WRITE_DEFAULT_CONFIG["sheet_write"]
        self.assertEqual(cfg["blocked_ranges"], [])


class TestNormalizeSheetWriteConfig(unittest.TestCase):
    def test_none_returns_defaults(self):
        cfg = normalize_sheet_write_config(None)
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["max_rows_per_action"], 50)

    def test_missing_section_returns_defaults(self):
        cfg = normalize_sheet_write_config({})
        self.assertFalse(cfg["enabled"])

    def test_enabled_flag_can_be_set(self):
        cfg = normalize_sheet_write_config({"sheet_write": {"enabled": True}})
        self.assertTrue(cfg["enabled"])

    def test_max_rows_can_be_overridden(self):
        cfg = normalize_sheet_write_config({"sheet_write": {"max_rows_per_action": 10}})
        self.assertEqual(cfg["max_rows_per_action"], 10)

    def test_unknown_keys_ignored(self):
        cfg = normalize_sheet_write_config({"sheet_write": {"unknown_key": "value"}})
        self.assertNotIn("unknown_key", cfg)


class TestAuditEventConstants(unittest.TestCase):
    def test_executed_event_name(self):
        self.assertEqual(SHEET_WRITE_AUDIT_EVENT_EXECUTED, "LIVE_SHEET_ROWS_WRITTEN")

    def test_blocked_event_name(self):
        self.assertEqual(SHEET_WRITE_AUDIT_EVENT_BLOCKED, "LIVE_SHEET_WRITE_BLOCKED")


class TestBuildSheetWritePendingAction(unittest.TestCase):
    def test_returns_dict_with_required_fields(self):
        action = _approved_action()
        self.assertEqual(action["tool"], "sheet/write_rows")
        self.assertEqual(action["operation"], "side_effect")
        self.assertTrue(action["live_capable"])
        self.assertFalse(action["live_executed"])
        self.assertEqual(action["idempotency_key"], "idem-sheet-001")

    def test_payload_has_required_fields(self):
        action = _approved_action()
        payload = action["payload"]
        self.assertIn("spreadsheet_id", payload)
        self.assertIn("range_name", payload)
        self.assertIn("rows", payload)
        self.assertIn("write_mode", payload)

    def test_rows_are_copied(self):
        rows = [["a", "b"]]
        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=rows,
        )
        rows.append(["c", "d"])
        self.assertEqual(len(action["payload"]["rows"]), 1)

    def test_default_status_is_pending_approval(self):
        action = build_sheet_write_pending_action(
            action_id="pa-001",
            business_ref="ref-001",
            idempotency_key="idem-001",
            spreadsheet_id="sheet-001",
            range_name="Sheet1!A:B",
            rows=[["x"]],
        )
        self.assertEqual(action["status"], "PENDING_APPROVAL")


class TestValidateSheetWritePayload(unittest.TestCase):
    def _payload(self, **overrides):
        base = {
            "spreadsheet_id": "sheet-abc123",
            "range_name": "Sheet1!A:C",
            "rows": [["a", "b", "c"]],
            "write_mode": "append",
        }
        base.update(overrides)
        return base

    def test_valid_payload_returns_ok(self):
        result = validate_sheet_write_payload(
            self._payload(),
            config={"sheet_write": {"enabled": True, "allow_append_mode": True, "allow_update_mode": False, "max_rows_per_action": 50}},
        )
        self.assertTrue(result["ok"])

    def test_empty_rows_returns_error(self):
        result = validate_sheet_write_payload(self._payload(rows=[]))
        self.assertFalse(result["ok"])
        self.assertTrue(any("rows" in e for e in result["errors"]))

    def test_empty_spreadsheet_id_returns_error(self):
        result = validate_sheet_write_payload(self._payload(spreadsheet_id=""))
        self.assertFalse(result["ok"])

    def test_empty_range_name_returns_error(self):
        result = validate_sheet_write_payload(self._payload(range_name=""))
        self.assertFalse(result["ok"])

    def test_row_count_exceeded_returns_error(self):
        rows = [["x"]] * 51
        result = validate_sheet_write_payload(
            self._payload(rows=rows),
            config={"sheet_write": {"max_rows_per_action": 50, "allow_append_mode": True, "allow_update_mode": False}},
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("exceeds" in e for e in result["errors"]))

    def test_update_mode_blocked_when_disabled(self):
        result = validate_sheet_write_payload(
            self._payload(write_mode="update"),
            config={"sheet_write": {"allow_append_mode": True, "allow_update_mode": False, "max_rows_per_action": 50}},
        )
        self.assertFalse(result["ok"])

    def test_update_mode_allowed_when_enabled(self):
        result = validate_sheet_write_payload(
            self._payload(write_mode="update"),
            config={"sheet_write": {"allow_append_mode": True, "allow_update_mode": True, "max_rows_per_action": 50}},
        )
        self.assertTrue(result["ok"])

    def test_column_count_mismatch_with_expected_headers(self):
        result = validate_sheet_write_payload(
            self._payload(rows=[["a", "b"]], expected_headers=["H1", "H2", "H3"]),
            config={"sheet_write": {"allow_append_mode": True, "allow_update_mode": False, "max_rows_per_action": 50}},
        )
        self.assertFalse(result["ok"])

    def test_column_count_matches_expected_headers(self):
        result = validate_sheet_write_payload(
            self._payload(rows=[["a", "b", "c"]], expected_headers=["H1", "H2", "H3"]),
            config={"sheet_write": {"allow_append_mode": True, "allow_update_mode": False, "max_rows_per_action": 50}},
        )
        self.assertTrue(result["ok"])


class TestSheetWriteDryRun(unittest.TestCase):
    def test_dry_run_returns_dry_run_true(self):
        action = _approved_action()
        result = sheet_write_dry_run(action, config=_enabled_config())
        self.assertTrue(result["data"]["dry_run"])

    def test_dry_run_returns_written_false(self):
        action = _approved_action()
        result = sheet_write_dry_run(action, config=_enabled_config())
        self.assertFalse(result["data"]["written"])

    def test_dry_run_marks_action_dry_run_executed(self):
        action = _approved_action()
        sheet_write_dry_run(action, config=_enabled_config())
        self.assertTrue(action["dry_run_executed"])

    def test_dry_run_returns_row_count(self):
        action = _approved_action(rows=[["a"], ["b"], ["c"]])
        result = sheet_write_dry_run(action, config=_enabled_config())
        self.assertEqual(result["data"]["row_count"], 3)

    def test_dry_run_type_is_sheet_write_result(self):
        action = _approved_action()
        result = sheet_write_dry_run(action, config=_enabled_config())
        self.assertEqual(result["type"], "sheet_write_result")


class TestSheetWriteLiveExecuteBlocked(unittest.TestCase):
    def test_blocked_when_dry_run_not_false(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
        )
        # dry_run parameter not set to False — should be blocked by preflight
        self.assertFalse(result["data"]["written"])

    def test_blocked_without_typed_confirmation(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            confirmation="WRONG",
            config=_enabled_config(),
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("blocked"))

    def test_blocked_for_demo_profile(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="demo",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("blocked"))

    def test_blocked_for_pilot_profile(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="pilot",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
        )
        self.assertFalse(result["ok"])

    def test_blocked_without_manifest_allowlist(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution={"enabled": False, "allowed_tools": []},
            profile_name="live",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
        )
        self.assertFalse(result["ok"])

    def test_blocked_when_action_not_approved(self):
        action = _approved_action()
        action["status"] = "PENDING_APPROVAL"
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
        )
        self.assertFalse(result["ok"])

    def test_blocked_without_idempotency_key(self):
        action = _approved_action(idempotency_key="")
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
        )
        self.assertFalse(result["ok"])

    def test_blocked_when_sheet_write_config_disabled(self):
        action = _approved_action()
        disabled_config = {"sheet_write": {"enabled": False, "allow_append_mode": True, "max_rows_per_action": 50}}
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=disabled_config,
        )
        self.assertFalse(result["ok"])


class TestSheetWriteLiveExecuteMocked(unittest.TestCase):
    def _mock_write_fn(self, **kwargs):
        range_name = kwargs.get("range_name", "Sheet1!A:H")
        rows = kwargs.get("rows", [])
        return {
            "ok": True,
            "updated_range": f"{range_name.split('!')[0]}!A42:H{41 + len(rows)}",
            "row_count": len(rows),
        }

    def test_mocked_live_write_returns_written_true(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=self._mock_write_fn,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["written"])
        self.assertFalse(result["data"]["dry_run"])

    def test_mocked_live_write_returns_updated_range(self):
        action = _approved_action(rows=[["a"], ["b"], ["c"]])
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=self._mock_write_fn,
        )
        self.assertTrue(result["ok"])
        self.assertNotEqual(result["data"]["updated_range"], "")

    def test_mocked_live_write_marks_action_live_executed(self):
        action = _approved_action()
        sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=self._mock_write_fn,
        )
        self.assertTrue(action["live_executed"])
        self.assertNotEqual(action["live_executed_at"], "")

    def test_mocked_live_write_stores_guardrail_result(self):
        action = _approved_action()
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=self._mock_write_fn,
        )
        self.assertIn("guardrail_result", result)
        self.assertTrue(result["guardrail_result"]["ok"])

    def test_duplicate_idempotency_key_blocked(self):
        action = _approved_action(idempotency_key="idem-dup-001")
        executed = [{"action_id": "pa-old", "idempotency_key": "idem-dup-001", "status": "EXECUTED"}]
        result = sheet_write_live_execute(
            action,
            _live_tool_spec(),
            manifest_live_execution=_live_manifest(),
            profile_name="live",
            profile_data={"allow_live_side_effects": True},
            executed_actions=executed,
            confirmation="LIVE-EXECUTE",
            config=_enabled_config(),
            _sheets_api_write_fn=self._mock_write_fn,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "DUPLICATE_SIDE_EFFECT_BLOCKED")


if __name__ == "__main__":
    unittest.main()
