from __future__ import annotations
import pytest


def test_controlled_live_profile_exists():
    from src.controlled_live_profile import CONTROLLED_LIVE_READ_PROFILE
    assert CONTROLLED_LIVE_READ_PROFILE["profile_id"] == "controlled_live_read"


def test_controlled_live_profile_allows_live_reads():
    from src.controlled_live_profile import CONTROLLED_LIVE_READ_PROFILE
    assert CONTROLLED_LIVE_READ_PROFILE["allow_live_reads"] is True


def test_controlled_live_profile_blocks_live_side_effects():
    from src.controlled_live_profile import CONTROLLED_LIVE_READ_PROFILE
    assert CONTROLLED_LIVE_READ_PROFILE["allow_live_side_effects"] is False


def test_live_read_requires_tool_governance():
    from src.controlled_live_profile import CONTROLLED_LIVE_READ_PROFILE
    assert CONTROLLED_LIVE_READ_PROFILE["require_tool_governance"] is True


def test_live_read_blocks_non_read_tool():
    from src.controlled_live_profile import is_live_read_allowed
    allowed, reason = is_live_read_allowed("gmail/send", {"side_effect": True, "allow_live": False})
    assert not allowed


def test_gmail_send_blocked_in_controlled_live_profile():
    from src.controlled_live_profile import is_live_side_effect_blocked
    blocked, _ = is_live_side_effect_blocked("gmail/send")
    assert blocked


def test_calendar_create_blocked_in_controlled_live_profile():
    from src.controlled_live_profile import is_live_side_effect_blocked
    blocked, _ = is_live_side_effect_blocked("calendar/create")
    assert blocked


def test_sheet_write_blocked_in_controlled_live_profile():
    from src.controlled_live_profile import is_live_side_effect_blocked
    blocked, _ = is_live_side_effect_blocked("sheet/write")
    assert blocked


def test_rpa_blocked_in_controlled_live_profile():
    from src.controlled_live_profile import is_live_read_allowed
    allowed, reason = is_live_read_allowed("rpa/click", {"side_effect": True, "allow_live": False})
    assert not allowed
    assert "rpa" in reason.lower() or "side_effect" in reason.lower()


def test_profile_status_report_has_required_shape():
    from src.live_profile_status import build_controlled_live_profile_status
    status = build_controlled_live_profile_status()
    assert "ok" in status
    assert status["profile_id"] == "controlled_live_read"
    assert status["allow_live_reads"] is True
    assert status["allow_live_side_effects"] is False
    assert "governance_ok" in status
    assert "google_workspace_readiness" in status
    assert "blocked_tool_classes" in status
    assert "allowed_read_tools" in status
    assert "blocked_side_effect_tools" in status
    assert "warnings" in status
    assert "errors" in status


def test_cli_controlled_live_status_command_exists():
    from src.taskframe_cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["profile", "controlled-live-status", "--json"])
    assert args.profile_command == "controlled-live-status"


def test_operator_ui_mentions_controlled_live_read_status():
    import inspect
    import src.operator_ui as ui_module
    source = inspect.getsource(ui_module)
    assert "controlled_live_read" in source.lower() or "controlled live read" in source.lower()
