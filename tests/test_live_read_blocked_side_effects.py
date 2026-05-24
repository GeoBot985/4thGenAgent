from __future__ import annotations

import pytest
from runtime.live_read_proof import validate_live_read_boundary


def test_boundary_returns_list():
    result = validate_live_read_boundary()
    assert isinstance(result, list)


def test_boundary_all_blocked():
    result = validate_live_read_boundary()
    for check in result:
        assert check.get("status") == "BLOCKED", (
            f"Expected BLOCKED for {check.get('tool')}, got {check.get('status')}"
        )


def test_boundary_no_side_effects_performed():
    result = validate_live_read_boundary()
    for check in result:
        assert check.get("side_effect_performed") is False


def test_boundary_gmail_send_blocked():
    result = validate_live_read_boundary()
    gmail_send = next((c for c in result if c.get("tool") == "gmail/send"), None)
    assert gmail_send is not None
    assert gmail_send.get("status") == "BLOCKED"


def test_boundary_calendar_create_blocked():
    result = validate_live_read_boundary()
    cal_create = next((c for c in result if c.get("tool") == "calendar/create"), None)
    assert cal_create is not None
    assert cal_create.get("status") == "BLOCKED"


def test_boundary_calendar_update_blocked():
    result = validate_live_read_boundary()
    cal_update = next((c for c in result if c.get("tool") == "calendar/update"), None)
    assert cal_update is not None
    assert cal_update.get("status") == "BLOCKED"


def test_boundary_calendar_delete_blocked():
    result = validate_live_read_boundary()
    cal_delete = next((c for c in result if c.get("tool") == "calendar/delete"), None)
    assert cal_delete is not None
    assert cal_delete.get("status") == "BLOCKED"


def test_boundary_sheet_write_blocked():
    result = validate_live_read_boundary()
    sheet_write = next((c for c in result if c.get("tool") == "sheet/write"), None)
    assert sheet_write is not None
    assert sheet_write.get("status") == "BLOCKED"


def test_boundary_sheet_write_rows_blocked():
    result = validate_live_read_boundary()
    sheet_rows = next((c for c in result if c.get("tool") == "sheet/write_rows"), None)
    assert sheet_rows is not None
    assert sheet_rows.get("status") == "BLOCKED"


def test_boundary_rpa_blocked():
    result = validate_live_read_boundary()
    rpa_checks = [c for c in result if "rpa" in str(c.get("tool", "")).lower()]
    assert len(rpa_checks) > 0
    for check in rpa_checks:
        assert check.get("status") == "BLOCKED", (
            f"RPA tool {check.get('tool')} not blocked"
        )


def test_boundary_each_check_has_tool_field():
    result = validate_live_read_boundary()
    for check in result:
        assert "tool" in check
        assert check["tool"]


def test_boundary_each_check_has_reason():
    result = validate_live_read_boundary()
    for check in result:
        assert "reason" in check


def test_boundary_profile_controlled_live_read():
    result = validate_live_read_boundary(profile="controlled_live_read")
    assert len(result) > 0
    for check in result:
        evidence = check.get("evidence", {})
        assert evidence.get("profile") == "controlled_live_read"
