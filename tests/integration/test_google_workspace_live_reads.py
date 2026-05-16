from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(os.getenv("RUN_GOOGLE_WORKSPACE_INTEGRATION", "").strip() != "1", reason="Google Workspace live integration tests are disabled.")


def _integration_ready() -> bool:
    from tool_packs.google_workspace import auth

    deps = auth.google_dependency_state()
    files = auth.google_auth_files()
    return bool(deps.get("ok")) and (bool(files.get("credentials_file_present")) or bool(files.get("token_file_present")))


def _skip_if_not_ready() -> None:
    if not _integration_ready():
        pytest.skip("Google Workspace dependencies or credentials are not available.")


def test_live_google_auth_status() -> None:
    _skip_if_not_ready()
    from tool_packs.google_workspace import tools

    result = tools.google_auth_status(live=False)
    assert result["type"] == "google_auth_status"


def test_live_gmail_list_unread() -> None:
    _skip_if_not_ready()
    from tool_packs.google_workspace import tools

    result = tools.gmail_list_unread(max_results=2)
    assert result["type"] == "gmail_message_metadata_list"
    assert isinstance(result["data"], list)


def test_live_calendar_list_upcoming() -> None:
    _skip_if_not_ready()
    from tool_packs.google_workspace import tools

    result = tools.calendar_list_upcoming(days=7, max_results=2)
    assert result["type"] == "calendar_entry_list"
    assert isinstance(result["data"], list)


def test_live_sheets_read_range() -> None:
    _skip_if_not_ready()
    spreadsheet_id = os.getenv("GOOGLE_WORKSPACE_TEST_SPREADSHEET_ID", "").strip()
    range_name = os.getenv("GOOGLE_WORKSPACE_TEST_RANGE", "").strip()
    if not spreadsheet_id or not range_name:
        pytest.skip("Spreadsheet test environment variables are not configured.")
    from tool_packs.google_workspace import tools

    result = tools.sheets_read_range(spreadsheet_id, range_name)
    assert result["type"] == "sheets_range_values"
    assert "rows" in result["data"]
