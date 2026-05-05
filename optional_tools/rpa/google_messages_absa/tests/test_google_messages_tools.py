from __future__ import annotations

import pytest


def test_messages_tool_registered():
    from runtime.tool_registry import TOOL_REGISTRY

    spec = TOOL_REGISTRY["messages/read_recent"]
    assert spec["module"] == "runtime.messages_tools"
    assert spec["function"] == "messages_read_recent"
    assert spec["side_effect"] is False
    assert spec["requires_approval"] is False


def test_sheet_write_rows_live_mode_allowed():
    from runtime.tool_registry import TOOL_REGISTRY

    spec = TOOL_REGISTRY["sheet/write_rows"]
    assert spec["allow_live"] is True
    assert spec["allow_live_side_effect"] is True
    assert spec["live_guardrail"] == "sheet_write"


def test_messages_thread_candidates_normalize():
    from runtime.messages_tools import _thread_candidates

    assert _thread_candidates("  +1 (555) 123-4567 ") == ["+1 (555) 123-4567"]
    assert _thread_candidates("Alice/Bob") == ["Alice/Bob", "Alice Bob", "AliceBob"]


@pytest.mark.asyncio
async def test_messages_read_recent_handles_missing_playwright(monkeypatch):
    import runtime.messages_tools as messages_tools

    monkeypatch.setattr(messages_tools, "async_playwright", None)

    result = await messages_tools.messages_read_recent("Test Thread")

    assert result["ok"] is False
    assert result["error"] == "Playwright unavailable."


def test_sheet_write_rows_live_calls_writer(monkeypatch):
    import runtime.google_sheet_tools as sheet_tools

    called = {}

    def fake_writer(*, spreadsheet_id, range_name, values, mode="append"):
        called["spreadsheet_id"] = spreadsheet_id
        called["range_name"] = range_name
        called["values"] = values
        called["mode"] = mode
        return {"updates": {"updatedRange": range_name, "updatedRows": len(values)}}

    monkeypatch.setattr(sheet_tools, "write_sheet_entries", fake_writer)

    result = sheet_tools.sheet_write_rows("sheet-123", "Sheet1!A:B", [["a", "b"]], dry_run=False)

    assert result["ok"] is True
    assert result["written"] is True
    assert called["spreadsheet_id"] == "sheet-123"
    assert called["range_name"] == "Sheet1!A:B"
