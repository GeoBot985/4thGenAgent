from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class _FakeExecute:
    def __init__(self, payload: Any):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeGmailMessages:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def list(self, **kwargs):
        self.responses["list_kwargs"] = kwargs
        return _FakeExecute(self.responses.get("list_result", {}))

    def get(self, **kwargs):
        self.responses.setdefault("get_kwargs", []).append(kwargs)
        message_id = kwargs.get("id", "")
        payload = self.responses.get("messages", {}).get(message_id, {})
        return _FakeExecute(payload)


class _FakeGmailUsers:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def messages(self):
        return _FakeGmailMessages(self.responses)

    def getProfile(self, **kwargs):
        self.responses["profile_kwargs"] = kwargs
        return _FakeExecute(self.responses.get("profile_result", {"emailAddress": "user@example.com"}))


class _FakeGmailService:
    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}

    def users(self):
        return _FakeGmailUsers(self.responses)


class _FakeCalendarEvents:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def list(self, **kwargs):
        self.responses.setdefault("events_list_kwargs", []).append(kwargs)
        return _FakeExecute(self.responses.get("events_result", {}))


class _FakeCalendarList:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def list(self, **kwargs):
        self.responses["calendar_list_kwargs"] = kwargs
        return _FakeExecute(self.responses.get("calendar_list_result", {}))


class _FakeCalendarService:
    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}

    def events(self):
        return _FakeCalendarEvents(self.responses)

    def calendarList(self):
        return _FakeCalendarList(self.responses)


class _FakeSheetsValues:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def get(self, **kwargs):
        self.responses["sheets_get_kwargs"] = kwargs
        return _FakeExecute(self.responses.get("values_result", {}))


class _FakeSheetsSpreadsheets:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    def values(self):
        return _FakeSheetsValues(self.responses)

    def get(self, **kwargs):
        self.responses["spreadsheet_get_kwargs"] = kwargs
        return _FakeExecute(self.responses.get("spreadsheet_result", {}))


class _FakeSheetsService:
    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}

    def spreadsheets(self):
        return _FakeSheetsSpreadsheets(self.responses)


def _patch_service(monkeypatch, service):
    from tool_packs.google_workspace import auth

    monkeypatch.setattr(auth, "build_google_service", lambda service_name, version: service)
    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(
        auth,
        "google_auth_files",
        lambda: {
            "credentials_file_present": True,
            "token_file_present": True,
            "configured_services": ["gmail", "calendar", "sheets"],
            "profile": "default",
            "config_dir": ".",
        },
    )


def test_gmail_unread_maps_fake_response(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    responses = {
        "list_result": {"messages": [{"id": "msg-1"}]},
        "messages": {
            "msg-1": {
                "id": "msg-1",
                "threadId": "thread-1",
                "snippet": "Hello there",
                "payload": {"headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Subject line"},
                    {"name": "Date", "value": "Mon, 01 Jan 2026 10:00:00 +0200"},
                ]},
            }
        },
    }
    _patch_service(monkeypatch, _FakeGmailService(responses))
    result = tools.gmail_list_unread(max_results=5)
    assert result["ok"] is True
    assert result["type"] == "gmail_message_metadata_list"
    assert result["data"][0]["from"] == "sender@example.com"
    assert result["data"][0]["subject"] == "Subject line"
    assert result["data"][0]["snippet"] == "Hello there"
    assert result["evidence"]["tool"] == "gmail/list_unread"
    assert result["evidence"]["mode"] == "live_read"
    assert result["evidence"]["record_count"] == 1


def test_gmail_search_maps_fake_response(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    responses = {"list_result": {"messages": []}}
    _patch_service(monkeypatch, _FakeGmailService(responses))
    result = tools.gmail_search(query="from:test@example.com", max_results=10)
    assert result["ok"] is True
    assert result["type"] == "gmail_message_metadata_list"
    assert result["data"] == []
    assert result["evidence"]["query"] == "from:test@example.com"
    assert result["evidence"]["record_count"] == 0


def test_gmail_read_metadata_maps_fake_message(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    responses = {
        "messages": {
            "msg-2": {
                "id": "msg-2",
                "threadId": "thread-2",
                "snippet": "Snippet",
                "payload": {"headers": [
                    {"name": "From", "value": "reader@example.com"},
                    {"name": "Subject", "value": "Read metadata"},
                    {"name": "Date", "value": "Tue, 02 Jan 2026 10:00:00 +0200"},
                ]},
            }
        }
    }
    _patch_service(monkeypatch, _FakeGmailService(responses))
    result = tools.gmail_read_metadata("msg-2")
    assert result["ok"] is True
    assert result["type"] == "gmail_message_metadata"
    assert result["data"]["id"] == "msg-2"
    assert result["data"]["from"] == "reader@example.com"
    assert result["evidence"]["tool"] == "gmail/read_metadata"
    assert result["evidence"]["mode"] == "live_read"


def test_calendar_search_maps_fake_response(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    responses = {
        "calendar_list_result": {"items": [{"id": "primary", "primary": True}]},
        "events_result": {
            "items": [
                {
                    "id": "evt-1",
                    "summary": "Planning",
                    "description": "Discuss work",
                    "location": "Room 1",
                    "start": {"dateTime": "2026-05-01T09:00:00+02:00"},
                    "end": {"dateTime": "2026-05-01T10:00:00+02:00"},
                    "htmlLink": "https://example.test",
                    "status": "confirmed",
                }
            ]
        },
    }
    _patch_service(monkeypatch, _FakeCalendarService(responses))
    result = tools.calendar_search(query="planning", days=7, max_results=20)
    assert result["ok"] is True
    assert result["type"] == "calendar_entry_list"
    assert result["data"][0]["summary"] == "Planning"
    assert result["data"][0]["calendar_id"] == "primary"
    assert result["evidence"]["tool"] == "calendar/search"
    assert result["evidence"]["record_count"] == 1


def test_calendar_list_upcoming_calls_search_behavior(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    responses = {
        "calendar_list_result": {"items": [{"id": "primary", "primary": True}]},
        "events_result": {"items": []},
    }
    _patch_service(monkeypatch, _FakeCalendarService(responses))
    result = tools.calendar_list_upcoming(days=7, max_results=5)
    assert result["ok"] is True
    assert result["type"] == "calendar_entry_list"
    assert result["data"] == []
    assert result["evidence"]["tool"] == "calendar/search"


def test_sheets_read_range_maps_fake_response(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    responses = {"values_result": {"values": [["A", "B"], ["1", "2"]]}}
    _patch_service(monkeypatch, _FakeSheetsService(responses))
    result = tools.sheets_read_range("sheet-1", "Sheet1!A1:B2")
    assert result["ok"] is True
    assert result["type"] == "sheets_range_values"
    assert result["data"]["row_count"] == 2
    assert result["data"]["rows"][0] == ["A", "B"]
    assert result["evidence"]["tool"] == "sheets/read_range"
    assert result["evidence"]["record_count"] == 2


def test_tools_return_standard_shape_on_exception(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(auth, "build_google_service", boom)
    result = tools.gmail_search("status:open", max_results=1)
    assert result["ok"] is False
    assert result["type"] == "gmail_message_metadata_list"
    assert result["error"]


def test_empty_result_is_ok_for_gmail_and_calendar(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    _patch_service(monkeypatch, _FakeGmailService({"list_result": {"messages": []}}))
    gmail = tools.gmail_list_unread()
    assert gmail["ok"] is True
    assert gmail["data"] == []

    _patch_service(monkeypatch, _FakeCalendarService({"calendar_list_result": {"items": [{"id": "primary", "primary": True}]}, "events_result": {"items": []}}))
    calendar = tools.calendar_search(query="", days=1)
    assert calendar["ok"] is True
    assert calendar["data"] == []


def test_google_auth_status_returns_tool_result_shape(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(
        auth,
        "google_auth_files",
        lambda: {
            "credentials_file_present": True,
            "token_file_present": True,
            "configured_services": ["gmail", "calendar", "sheets"],
            "profile": "default",
            "config_dir": ".",
        },
    )
    result = tools.google_auth_status(live=False)
    assert result["ok"] is True
    assert result["type"] == "google_auth_status"
    assert result["evidence"]["tool"] == "google/auth_status"
    assert result["evidence"]["mode"] == "local_static_check"
    assert result["evidence"]["operation"] == "health"


def test_google_auth_status_does_not_build_live_service_when_live_false(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    called = {"count": 0}

    def fake_build(*args, **kwargs):
        called["count"] += 1
        raise AssertionError("build_google_service should not be called")

    monkeypatch.setattr(auth, "build_google_service", fake_build)
    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(
        auth,
        "google_auth_files",
        lambda: {
            "credentials_file_present": False,
            "token_file_present": False,
            "configured_services": [],
            "profile": "default",
            "config_dir": ".",
        },
    )
    result = tools.google_auth_status(live=False)
    assert result["ok"] is False
    assert called["count"] == 0


def test_gmail_search_without_auth_returns_safe_error(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": "."})
    result = tools.gmail_search("from:test@example.com")
    assert result["ok"] is False
    assert result["error"] == "GOOGLE_AUTH_NOT_CONFIGURED"
    assert result["evidence"]["safe_error_code"] == "GOOGLE_AUTH_NOT_CONFIGURED"


def test_gmail_read_metadata_requires_message_id() -> None:
    from tool_packs.google_workspace import tools

    result = tools.gmail_read_metadata("")
    assert result["ok"] is False
    assert result["error"] == "MESSAGE_ID_REQUIRED"
    assert result["evidence"]["safe_error_code"] == "MESSAGE_ID_REQUIRED"


def test_calendar_search_without_auth_returns_safe_error(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": "."})
    result = tools.calendar_search(query="planning")
    assert result["ok"] is False
    assert result["error"] == "GOOGLE_AUTH_NOT_CONFIGURED"
    assert result["evidence"]["safe_error_code"] == "GOOGLE_AUTH_NOT_CONFIGURED"


def test_calendar_list_upcoming_without_auth_returns_safe_error(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": "."})
    result = tools.calendar_list_upcoming()
    assert result["ok"] is False
    assert result["error"] == "GOOGLE_AUTH_NOT_CONFIGURED"


def test_sheets_read_range_requires_spreadsheet_id_and_range() -> None:
    from tool_packs.google_workspace import tools

    result = tools.sheets_read_range("", "")
    assert result["ok"] is False
    assert result["error"] == "SPREADSHEET_ID_REQUIRED"
    result = tools.sheets_read_range("sheet-1", "")
    assert result["ok"] is False
    assert result["error"] == "RANGE_NAME_REQUIRED"


def test_sheets_read_range_without_auth_returns_safe_error(monkeypatch) -> None:
    from tool_packs.google_workspace import auth, tools

    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(auth, "google_auth_files", lambda: {"credentials_file_present": False, "token_file_present": False, "configured_services": [], "profile": "default", "config_dir": "."})
    result = tools.sheets_read_range("sheet-1", "Sheet1!A1:B2")
    assert result["ok"] is False
    assert result["error"] == "GOOGLE_AUTH_NOT_CONFIGURED"
    assert result["evidence"]["safe_error_code"] == "GOOGLE_AUTH_NOT_CONFIGURED"


def test_all_results_include_non_empty_evidence(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    _patch_service(monkeypatch, _FakeGmailService({"list_result": {"messages": []}}))
    results = [
        tools.google_auth_status(live=False),
        tools.gmail_list_unread(),
        tools.gmail_search("in:inbox"),
        tools.gmail_read_metadata("msg-1"),
    ]
    _patch_service(monkeypatch, _FakeCalendarService({"calendar_list_result": {"items": [{"id": "primary", "primary": True}]}, "events_result": {"items": []}}))
    results.extend([tools.calendar_search(query="planning"), tools.calendar_list_upcoming()])
    _patch_service(monkeypatch, _FakeSheetsService({"values_result": {"values": [["A"]]}}))
    results.append(tools.sheets_read_range("sheet-1", "Sheet1!A1:A1"))
    assert all(isinstance(result["evidence"], dict) and result["evidence"] for result in results)


def test_no_result_exposes_token_or_credentials_path(monkeypatch) -> None:
    from tool_packs.google_workspace import tools

    _patch_service(monkeypatch, _FakeGmailService({"list_result": {"messages": []}}))
    result = tools.google_auth_status(live=False)
    text = str(result)
    assert "token.json" not in text
    assert "credentials.json" not in text
