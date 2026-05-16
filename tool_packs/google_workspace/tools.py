from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from . import auth
from .schemas import (
    CALENDAR_ENTRY_LIST_TYPE,
    DEFAULT_LIVE_GUARDRAIL,
    DEFAULT_TOOL_RESULT_ERROR,
    GMAIL_MESSAGE_METADATA_LIST_TYPE,
    GMAIL_MESSAGE_METADATA_TYPE,
    GOOGLE_AUTH_STATUS_TYPE,
    GOOGLE_WORKSPACE_SERVICE_NAMES,
    SHEETS_RANGE_VALUES_TYPE,
)


def google_auth_status(service: str = "", live: bool = False) -> dict[str, Any]:
    dependency_state = auth.google_dependency_state()
    auth_files = auth.google_auth_files()
    configured_services = list(auth_files.get("configured_services", [])) if dependency_state.get("ok") else []
    if not auth_files.get("credentials_file_present") and not auth_files.get("token_file_present"):
        configured_services = []
    if service.strip():
        configured_services = [service.strip()] if service.strip() in GOOGLE_WORKSPACE_SERVICE_NAMES and configured_services else []

    live_checked = False
    live_service = ""
    live_error = ""
    if live and dependency_state.get("ok") and (auth_files.get("credentials_file_present") or auth_files.get("token_file_present")):
        probe_service = service.strip() if service.strip() in GOOGLE_WORKSPACE_SERVICE_NAMES else (configured_services[0] if configured_services else "gmail")
        try:
            _probe_service(probe_service)
            live_checked = True
            live_service = probe_service
        except Exception as exc:
            live_checked = True
            live_service = probe_service
            live_error = str(exc)

    data = {
        "dependencies_ok": bool(dependency_state.get("ok")),
        "credentials_file_present": bool(auth_files.get("credentials_file_present")),
        "token_file_present": bool(auth_files.get("token_file_present")),
        "configured_services": configured_services,
        "live_checked": live_checked,
    }
    evidence = {
        "tool": "google/auth_status",
        "mode": "live_probe" if live_checked else "local_static_check",
        "auth_files": auth.redact_google_auth_state(auth_files),
    }
    if live_error:
        evidence["live_error"] = live_error
    ok = bool(dependency_state.get("ok"))
    if not ok:
        error = "MISSING_GOOGLE_DEPENDENCIES"
        ok = False
    elif not (auth_files.get("credentials_file_present") or auth_files.get("token_file_present")):
        error = "GOOGLE_AUTH_NOT_CONFIGURED"
        ok = False
    elif live and live_error:
        error = "GOOGLE_LIVE_PROBE_FAILED"
        ok = False
    else:
        error = DEFAULT_TOOL_RESULT_ERROR
    return {
        "ok": ok,
        "type": GOOGLE_AUTH_STATUS_TYPE,
        "data": data,
        "evidence": evidence,
        "error": error,
    }


def gmail_list_unread(max_results: int = 5) -> dict[str, Any]:
    return _gmail_search("is:unread in:inbox", max_results=max_results, output_type=GMAIL_MESSAGE_METADATA_LIST_TYPE)


def gmail_search(query: str, max_results: int = 10) -> dict[str, Any]:
    return _gmail_search(query, max_results=max_results, output_type=GMAIL_MESSAGE_METADATA_LIST_TYPE)


def gmail_read_metadata(message_id: str) -> dict[str, Any]:
    message_id = str(message_id or "").strip()
    if not message_id:
        return {
            "ok": False,
            "type": GMAIL_MESSAGE_METADATA_TYPE,
            "data": {},
            "evidence": {"tool": "gmail/read_metadata", "mode": "local_static_check"},
            "error": "MESSAGE_ID_REQUIRED",
        }
    try:
        service = auth.build_google_service("gmail", "v1")
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata", metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        payload = msg.get("payload", {}) if isinstance(msg, dict) else {}
        headers = payload.get("headers", []) if isinstance(payload, dict) else []
        metadata = _message_metadata(msg, headers)
        return {
            "ok": True,
            "type": GMAIL_MESSAGE_METADATA_TYPE,
            "data": metadata,
            "evidence": {"tool": "gmail/read_metadata", "message_id": message_id},
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "type": GMAIL_MESSAGE_METADATA_TYPE,
            "data": {},
            "evidence": {"tool": "gmail/read_metadata", "message_id": message_id},
            "error": _safe_error(exc),
        }


def calendar_search(
    query: str = "",
    calendar_id: str = "",
    time_min: str | None = None,
    time_max: str | None = None,
    days: int | None = None,
    max_results: int = 20,
) -> dict[str, Any]:
    try:
        service = auth.build_google_service("calendar", "v3")
        calendar_ids = [calendar_id] if str(calendar_id or "").strip() else _list_calendar_ids(service)
        if not calendar_ids:
            calendar_ids = ["primary"]
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()
        if days is not None and not time_max:
            time_max = (datetime.now(timezone.utc) + timedelta(days=int(days))).isoformat()

        entries: list[dict[str, Any]] = []
        for cal_id in calendar_ids:
            request_kwargs = {
                "calendarId": cal_id,
                "timeMin": time_min,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if query.strip():
                request_kwargs["q"] = query.strip()
            if time_max:
                request_kwargs["timeMax"] = time_max
            result = service.events().list(**request_kwargs).execute()
            for event in result.get("items", []) if isinstance(result, dict) else []:
                entries = [*entries, _calendar_entry(event, cal_id)]
        entries.sort(key=lambda entry: entry.get("start", ""))
        return {
            "ok": True,
            "type": CALENDAR_ENTRY_LIST_TYPE,
            "data": entries,
            "evidence": {"tool": "calendar/search", "query": query, "calendar_ids": calendar_ids},
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "type": CALENDAR_ENTRY_LIST_TYPE,
            "data": [],
            "evidence": {"tool": "calendar/search", "query": query},
            "error": _safe_error(exc),
        }


def calendar_list_upcoming(
    calendar_id: str = "",
    days: int = 7,
    max_results: int = 20,
) -> dict[str, Any]:
    return calendar_search(query="", calendar_id=calendar_id, days=days, max_results=max_results)


def sheets_read_range(
    spreadsheet_id: str,
    range_name: str,
    major_dimension: str = "ROWS",
) -> dict[str, Any]:
    spreadsheet_id = str(spreadsheet_id or "").strip()
    range_name = str(range_name or "").strip()
    if not spreadsheet_id:
        return {
            "ok": False,
            "type": SHEETS_RANGE_VALUES_TYPE,
            "data": {"rows": [], "row_count": 0},
            "evidence": {"tool": "sheets/read_range", "mode": "local_static_check"},
            "error": "SPREADSHEET_ID_REQUIRED",
        }
    if not range_name:
        return {
            "ok": False,
            "type": SHEETS_RANGE_VALUES_TYPE,
            "data": {"rows": [], "row_count": 0},
            "evidence": {"tool": "sheets/read_range", "spreadsheet_id": spreadsheet_id},
            "error": "RANGE_NAME_REQUIRED",
        }
    try:
        service = auth.build_google_service("sheets", "v4")
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name, majorDimension=major_dimension)
            .execute()
        )
        rows = result.get("values", []) if isinstance(result, dict) else []
        return {
            "ok": True,
            "type": SHEETS_RANGE_VALUES_TYPE,
            "data": {
                "spreadsheet_id": spreadsheet_id,
                "range_name": range_name,
                "major_dimension": major_dimension,
                "rows": rows,
                "row_count": len(rows),
            },
            "evidence": {"tool": "sheets/read_range", "spreadsheet_id": spreadsheet_id, "range_name": range_name},
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "type": SHEETS_RANGE_VALUES_TYPE,
            "data": {"spreadsheet_id": spreadsheet_id, "range_name": range_name, "major_dimension": major_dimension, "rows": [], "row_count": 0},
            "evidence": {"tool": "sheets/read_range", "spreadsheet_id": spreadsheet_id, "range_name": range_name},
            "error": _safe_error(exc),
        }


def _gmail_search(query: str, *, max_results: int, output_type: str) -> dict[str, Any]:
    query = str(query or "").strip()
    if not query:
        query = "is:unread in:inbox"
    try:
        service = auth.build_google_service("gmail", "v1")
        results = service.users().messages().list(userId="me", q=query, maxResults=int(max_results)).execute()
        messages = []
        for message_ref in results.get("messages", []) if isinstance(results, dict) else []:
            msg = service.users().messages().get(userId="me", id=message_ref.get("id", ""), format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
            payload = msg.get("payload", {}) if isinstance(msg, dict) else {}
            headers = payload.get("headers", []) if isinstance(payload, dict) else []
            messages = [*messages, _message_metadata(msg, headers)]
        return {
            "ok": True,
            "type": output_type,
            "data": messages,
            "evidence": {"tool": "gmail/search", "query": query, "count": len(messages)},
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "type": output_type,
            "data": [],
            "evidence": {"tool": "gmail/search", "query": query},
            "error": _safe_error(exc),
        }


def _list_calendar_ids(service: Any) -> list[str]:
    try:
        result = service.calendarList().list().execute()
    except Exception:
        return []
    items = result.get("items", []) if isinstance(result, dict) else []
    ordered: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cal_id = str(item.get("id", "")).strip()
        if not cal_id:
            continue
        if item.get("primary") or item.get("accessRole") in {"owner", "writer"}:
            ordered = [*ordered, cal_id]
    return ordered or [str(item.get("id", "")).strip() for item in items if isinstance(item, dict) and str(item.get("id", "")).strip()]


def _message_metadata(message: dict[str, Any], headers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(message.get("id", "")),
        "thread_id": str(message.get("threadId", "")),
        "from": _header_value(headers, "From"),
        "subject": _header_value(headers, "Subject"),
        "date": _format_gmail_date(_header_value(headers, "Date")),
        "snippet": str(message.get("snippet", "")),
    }


def _header_value(headers: list[dict[str, Any]], name: str) -> str:
    for header in headers:
        if not isinstance(header, dict):
            continue
        if str(header.get("name", "")).lower() == name.lower():
            return str(header.get("value", ""))
    return ""


def _format_gmail_date(date_text: str) -> str:
    if not date_text:
        return "unknown"
    try:
        return parsedate_to_datetime(date_text).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return date_text


def _calendar_entry(event: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    start = event.get("start", {}) if isinstance(event, dict) else {}
    end = event.get("end", {}) if isinstance(event, dict) else {}
    return {
        "id": str(event.get("id", "")),
        "calendar_id": calendar_id,
        "summary": str(event.get("summary", "(No title)")),
        "description": str(event.get("description", "")),
        "location": str(event.get("location", "")),
        "start": str(start.get("dateTime") or start.get("date") or ""),
        "end": str(end.get("dateTime") or end.get("date") or ""),
        "html_link": str(event.get("htmlLink", "")),
        "status": str(event.get("status", "")),
    }


def _probe_service(service_name: str) -> None:
    if service_name == "gmail":
        service = auth.build_google_service("gmail", "v1")
        service.users().getProfile(userId="me").execute()
        return
    if service_name == "calendar":
        service = auth.build_google_service("calendar", "v3")
        service.calendarList().list(maxResults=1).execute()
        return
    if service_name == "sheets":
        # Sheets auth readiness is confirmed by service construction. A spreadsheet id is
        # required for a live read, so we keep this probe local and non-mutating.
        auth.build_google_service("sheets", "v4")
        return
    raise RuntimeError(f"Unsupported service: {service_name}")


def _safe_error(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return "GOOGLE_WORKSPACE_REQUEST_FAILED"
    return text.replace("\n", " ")[:500]
