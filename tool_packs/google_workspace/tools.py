from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from runtime.tool_result_contract import build_tool_evidence

from . import auth
from .schemas import (
    CALENDAR_ENTRY_LIST_TYPE,
    DEFAULT_TOOL_RESULT_ERROR,
    GMAIL_MESSAGE_METADATA_LIST_TYPE,
    GMAIL_MESSAGE_METADATA_TYPE,
    GOOGLE_AUTH_STATUS_TYPE,
    GOOGLE_WORKSPACE_SERVICE_NAMES,
    SHEETS_RANGE_VALUES_TYPE,
)

_SOURCE = "external_toolpack"


def google_auth_status(service: str = "", live: bool = False) -> dict[str, Any]:
    dependency_state = auth.google_dependency_state()
    auth_files = auth.google_auth_files()
    files_ready = bool(auth_files.get("credentials_file_present")) or bool(auth_files.get("token_file_present"))
    configured_services = list(GOOGLE_WORKSPACE_SERVICE_NAMES) if dependency_state.get("ok") and files_ready else []
    requested_service = service.strip()
    if requested_service and requested_service in GOOGLE_WORKSPACE_SERVICE_NAMES and files_ready:
        configured_services = [requested_service]

    live_checked = False
    live_service = ""
    live_error_code = ""
    live_error = ""
    if live and dependency_state.get("ok") and files_ready:
        probe_service = requested_service if requested_service in GOOGLE_WORKSPACE_SERVICE_NAMES else (configured_services[0] if configured_services else "gmail")
        live_service = probe_service
        try:
            _probe_service(probe_service)
            live_checked = True
        except Exception as exc:
            live_checked = True
            live_error_code = _safe_google_error(exc, fallback="GOOGLE_LIVE_PROBE_FAILED")
            live_error = _safe_error_text(exc)

    data = {
        "dependencies_ok": bool(dependency_state.get("ok")),
        "missing_dependencies": list(dependency_state.get("missing", [])),
        "credentials_file_present": bool(auth_files.get("credentials_file_present")),
        "token_file_present": bool(auth_files.get("token_file_present")),
        "configured_services": configured_services,
        "live_checked": live_checked,
        "live_service": live_service,
        "live_ok": live_checked and not live_error_code,
    }
    evidence = _build_evidence(
        "google/auth_status",
        mode="live_probe" if live_checked else "local_static_check",
        operation="health",
        service="google",
        input_refs=["service", "live"],
        output_ref="auth_status",
        extra={
            "requested_service": requested_service,
            "configured_services": configured_services,
            "live_checked": live_checked,
        },
    )
    if live_error_code:
        evidence["safe_error_code"] = live_error_code
    if live_error:
        evidence["live_error"] = live_error

    if not dependency_state.get("ok"):
        return _failure_result(
            GOOGLE_AUTH_STATUS_TYPE,
            error="MISSING_GOOGLE_DEPENDENCIES",
            evidence=evidence,
            data=data,
        )
    if not files_ready:
        return _failure_result(
            GOOGLE_AUTH_STATUS_TYPE,
            error="GOOGLE_AUTH_NOT_CONFIGURED",
            evidence=evidence,
            data=data,
        )
    if live and live_error_code:
        return _failure_result(
            GOOGLE_AUTH_STATUS_TYPE,
            error=live_error_code,
            evidence=evidence,
            data=data,
        )
    return _success_result(GOOGLE_AUTH_STATUS_TYPE, data=data, evidence=evidence)


def gmail_list_unread(max_results: int = 5) -> dict[str, Any]:
    return _gmail_search(
        "is:unread in:inbox",
        max_results=max_results,
        output_type=GMAIL_MESSAGE_METADATA_LIST_TYPE,
        output_ref="unread_messages",
        tool_name="gmail/list_unread",
    )


def gmail_search(query: str, max_results: int = 10) -> dict[str, Any]:
    return _gmail_search(
        query,
        max_results=max_results,
        output_type=GMAIL_MESSAGE_METADATA_LIST_TYPE,
        output_ref="messages",
        tool_name="gmail/search",
    )


def gmail_read_metadata(message_id: str) -> dict[str, Any]:
    message_id = str(message_id or "").strip()
    if not message_id:
        return _failure_result(
            GMAIL_MESSAGE_METADATA_TYPE,
            error="MESSAGE_ID_REQUIRED",
            evidence=_build_evidence(
                "gmail/read_metadata",
                mode="local_static_check",
                operation="read",
                service="gmail",
                input_refs=["message_id"],
                output_ref="message",
                extra={"safe_error_code": "MESSAGE_ID_REQUIRED"},
            ),
            data={},
        )
    prereq = _google_runtime_prereq("gmail/read_metadata", service="gmail", output_ref="message", input_refs=["message_id"])
    if prereq is not None:
        return prereq
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
        evidence = _build_evidence(
            "gmail/read_metadata",
            mode="live_read",
            operation="read",
            service="gmail",
            input_refs=["message_id"],
            output_ref="message",
            extra={"message_id": message_id, "record_count": 1},
        )
        return _success_result(GMAIL_MESSAGE_METADATA_TYPE, data=metadata, evidence=evidence)
    except Exception as exc:
        error_code = _safe_google_error(exc, fallback="GOOGLE_LIVE_READ_FAILED")
        evidence = _build_evidence(
            "gmail/read_metadata",
            mode="live_read",
            operation="read",
            service="gmail",
            input_refs=["message_id"],
            output_ref="message",
            extra={"message_id": message_id, "safe_error_code": error_code},
        )
        return _failure_result(GMAIL_MESSAGE_METADATA_TYPE, error=error_code, evidence=evidence, data={})


def calendar_search(
    query: str = "",
    calendar_id: str = "",
    time_min: str | None = None,
    time_max: str | None = None,
    days: int | None = None,
    max_results: int = 20,
) -> dict[str, Any]:
    query = str(query or "").strip()
    calendar_id = str(calendar_id or "").strip()
    time_min = str(time_min or "").strip() or None
    time_max = str(time_max or "").strip() or None
    days_value = _coerce_int(days, default=None)
    prereq = _google_runtime_prereq(
        "calendar/search",
        service="calendar",
        output_ref="calendar_entries",
        input_refs=["query", "calendar_id", "time_min", "time_max", "days", "max_results"],
    )
    if prereq is not None:
        return prereq
    try:
        service = auth.build_google_service("calendar", "v3")
        calendar_ids = [calendar_id] if calendar_id else _list_calendar_ids(service)
        if not calendar_ids:
            calendar_ids = ["primary"]
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()
        if days_value is not None and not time_max:
            time_max = (datetime.now(timezone.utc) + timedelta(days=days_value)).isoformat()

        entries: list[dict[str, Any]] = []
        for cal_id in calendar_ids:
            request_kwargs = {
                "calendarId": cal_id,
                "timeMin": time_min,
                "maxResults": int(max_results),
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if query:
                request_kwargs["q"] = query
            if time_max:
                request_kwargs["timeMax"] = time_max
            result = service.events().list(**request_kwargs).execute()
            for event in result.get("items", []) if isinstance(result, dict) else []:
                entries = [*entries, _calendar_entry(event, cal_id)]
        entries.sort(key=lambda entry: entry.get("start", ""))
        evidence = _build_evidence(
            "calendar/search",
            mode="live_read",
            operation="read",
            service="calendar",
            input_refs=["query", "calendar_id", "time_min", "time_max", "days", "max_results"],
            output_ref="calendar_entries",
            extra={
                "query": query,
                "calendar_ids": calendar_ids,
                "record_count": len(entries),
            },
        )
        return _success_result(CALENDAR_ENTRY_LIST_TYPE, data=entries, evidence=evidence)
    except Exception as exc:
        error_code = _safe_google_error(exc, fallback="GOOGLE_LIVE_READ_FAILED")
        evidence = _build_evidence(
            "calendar/search",
            mode="live_read",
            operation="read",
            service="calendar",
            input_refs=["query", "calendar_id", "time_min", "time_max", "days", "max_results"],
            output_ref="calendar_entries",
            extra={
                "query": query,
                "calendar_id": calendar_id,
                "safe_error_code": error_code,
            },
        )
        return _failure_result(CALENDAR_ENTRY_LIST_TYPE, error=error_code, evidence=evidence, data=[])


def calendar_list_upcoming(
    calendar_id: str = "",
    days: int = 7,
    max_results: int = 20,
) -> dict[str, Any]:
    return calendar_search(
        query="",
        calendar_id=calendar_id,
        days=days,
        max_results=max_results,
    )


def sheets_read_range(
    spreadsheet_id: str,
    range_name: str,
    major_dimension: str = "ROWS",
) -> dict[str, Any]:
    spreadsheet_id = str(spreadsheet_id or "").strip()
    range_name = str(range_name or "").strip()
    major_dimension = str(major_dimension or "ROWS").strip() or "ROWS"
    if not spreadsheet_id:
        return _failure_result(
            SHEETS_RANGE_VALUES_TYPE,
            error="SPREADSHEET_ID_REQUIRED",
            evidence=_build_evidence(
                "sheets/read_range",
                mode="local_static_check",
                operation="read",
                service="sheets",
                input_refs=["spreadsheet_id", "range_name"],
                output_ref="sheet_values",
                extra={"safe_error_code": "SPREADSHEET_ID_REQUIRED"},
            ),
            data={"spreadsheet_id": "", "range_name": range_name, "major_dimension": major_dimension, "rows": [], "row_count": 0},
        )
    if not range_name:
        return _failure_result(
            SHEETS_RANGE_VALUES_TYPE,
            error="RANGE_NAME_REQUIRED",
            evidence=_build_evidence(
                "sheets/read_range",
                mode="local_static_check",
                operation="read",
                service="sheets",
                input_refs=["spreadsheet_id", "range_name"],
                output_ref="sheet_values",
                extra={"spreadsheet_id": spreadsheet_id, "safe_error_code": "RANGE_NAME_REQUIRED"},
            ),
            data={"spreadsheet_id": spreadsheet_id, "range_name": "", "major_dimension": major_dimension, "rows": [], "row_count": 0},
        )
    prereq = _google_runtime_prereq(
        "sheets/read_range",
        service="sheets",
        output_ref="sheet_values",
        input_refs=["spreadsheet_id", "range_name", "major_dimension"],
    )
    if prereq is not None:
        return prereq
    try:
        service = auth.build_google_service("sheets", "v4")
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name, majorDimension=major_dimension)
            .execute()
        )
        rows = result.get("values", []) if isinstance(result, dict) else []
        data = {
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "major_dimension": major_dimension,
            "rows": rows,
            "row_count": len(rows),
        }
        evidence = _build_evidence(
            "sheets/read_range",
            mode="live_read",
            operation="read",
            service="sheets",
            input_refs=["spreadsheet_id", "range_name", "major_dimension"],
            output_ref="sheet_values",
            extra={"record_count": len(rows)},
        )
        return _success_result(SHEETS_RANGE_VALUES_TYPE, data=data, evidence=evidence)
    except Exception as exc:
        error_code = _safe_google_error(exc, fallback="GOOGLE_LIVE_READ_FAILED")
        evidence = _build_evidence(
            "sheets/read_range",
            mode="live_read",
            operation="read",
            service="sheets",
            input_refs=["spreadsheet_id", "range_name", "major_dimension"],
            output_ref="sheet_values",
            extra={
                "spreadsheet_id": spreadsheet_id,
                "range_name": range_name,
                "safe_error_code": error_code,
            },
        )
        data = {"spreadsheet_id": spreadsheet_id, "range_name": range_name, "major_dimension": major_dimension, "rows": [], "row_count": 0}
        return _failure_result(SHEETS_RANGE_VALUES_TYPE, error=error_code, evidence=evidence, data=data)


def _gmail_search(query: str, *, max_results: int, output_type: str, output_ref: str, tool_name: str) -> dict[str, Any]:
    query = str(query or "").strip() or "is:unread in:inbox"
    prereq = _google_runtime_prereq(tool_name, service="gmail", output_ref=output_ref, input_refs=["query", "max_results"])
    if prereq is not None:
        return prereq
    try:
        service = auth.build_google_service("gmail", "v1")
        results = service.users().messages().list(userId="me", q=query, maxResults=int(max_results)).execute()
        messages: list[dict[str, Any]] = []
        for message_ref in results.get("messages", []) if isinstance(results, dict) else []:
            message_id = str(message_ref.get("id", "")).strip()
            if not message_id:
                continue
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="metadata", metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )
            payload = msg.get("payload", {}) if isinstance(msg, dict) else {}
            headers = payload.get("headers", []) if isinstance(payload, dict) else []
            messages = [*messages, _message_metadata(msg, headers)]
        evidence = _build_evidence(
            tool_name,
            mode="live_read",
            operation="read",
            service="gmail",
            input_refs=["query", "max_results"],
            output_ref=output_ref,
            extra={"query": query, "record_count": len(messages)},
        )
        return _success_result(output_type, data=messages, evidence=evidence)
    except Exception as exc:
        error_code = _safe_google_error(exc, fallback="GOOGLE_LIVE_READ_FAILED")
        evidence = _build_evidence(
            tool_name,
            mode="live_read",
            operation="read",
            service="gmail",
            input_refs=["query", "max_results"],
            output_ref=output_ref,
            extra={"query": query, "safe_error_code": error_code},
        )
        return _failure_result(output_type, error=error_code, evidence=evidence, data=[])


def _google_runtime_prereq(tool: str, *, service: str, output_ref: str, input_refs: list[str]) -> dict[str, Any] | None:
    dependency_state = auth.google_dependency_state()
    if not dependency_state.get("ok"):
        evidence = _build_evidence(
            tool,
            mode="local_static_check",
            operation="read",
            service=service,
            input_refs=input_refs,
            output_ref=output_ref,
            extra={"safe_error_code": "MISSING_GOOGLE_DEPENDENCIES"},
        )
        return _failure_result(_output_type_for_tool(tool), error="MISSING_GOOGLE_DEPENDENCIES", evidence=evidence, data=_empty_data_for_tool(tool))

    auth_files = auth.google_auth_files()
    if not (auth_files.get("credentials_file_present") or auth_files.get("token_file_present")):
        evidence = _build_evidence(
            tool,
            mode="local_static_check",
            operation="read",
            service=service,
            input_refs=input_refs,
            output_ref=output_ref,
            extra={"safe_error_code": "GOOGLE_AUTH_NOT_CONFIGURED"},
        )
        return _failure_result(_output_type_for_tool(tool), error="GOOGLE_AUTH_NOT_CONFIGURED", evidence=evidence, data=_empty_data_for_tool(tool))
    return None


def _output_type_for_tool(tool: str) -> str:
    mapping = {
        "gmail/list_unread": GMAIL_MESSAGE_METADATA_LIST_TYPE,
        "gmail/search": GMAIL_MESSAGE_METADATA_LIST_TYPE,
        "gmail/read_metadata": GMAIL_MESSAGE_METADATA_TYPE,
        "calendar/search": CALENDAR_ENTRY_LIST_TYPE,
        "calendar/list_upcoming": CALENDAR_ENTRY_LIST_TYPE,
        "sheets/read_range": SHEETS_RANGE_VALUES_TYPE,
    }
    return mapping.get(tool, "")


def _empty_data_for_tool(tool: str) -> Any:
    if tool == "gmail/read_metadata":
        return {}
    if tool == "sheets/read_range":
        return {"spreadsheet_id": "", "range_name": "", "major_dimension": "ROWS", "rows": [], "row_count": 0}
    return []


def _build_evidence(
    tool: str,
    *,
    mode: str,
    operation: str,
    service: str,
    input_refs: list[str] | None = None,
    output_ref: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_tool_evidence(
        tool=tool,
        mode=mode,
        source=_SOURCE,
        operation=operation,
        input_refs=input_refs or [],
        output_ref=output_ref,
        extra={"service": service, **(extra or {})},
    )


def _success_result(result_type: str, *, data: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "type": result_type,
        "data": data,
        "evidence": evidence,
        "error": DEFAULT_TOOL_RESULT_ERROR,
    }


def _failure_result(result_type: str, *, error: str, evidence: dict[str, Any], data: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "type": result_type,
        "data": data,
        "evidence": evidence,
        "error": str(error or "GOOGLE_WORKSPACE_REQUEST_FAILED"),
    }


def _safe_google_error(exc: Exception, *, fallback: str) -> str:
    text = _safe_error_text(exc).lower()
    if any(term in text for term in ("credentials are not configured", "oauth", "token", "credential", "authorization")):
        return "GOOGLE_AUTH_NOT_CONFIGURED"
    if any(term in text for term in ("dependency", "module not found", "google client dependencies")):
        return "MISSING_GOOGLE_DEPENDENCIES"
    if any(term in text for term in ("not configured", "client secret", "client_secrets")):
        return "GOOGLE_AUTH_NOT_CONFIGURED"
    return fallback


def _safe_error_text(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return "GOOGLE_WORKSPACE_REQUEST_FAILED"
    return text.replace("\n", " ")[:500]


def _coerce_int(value: Any, *, default: int | None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


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
        auth.build_google_service("sheets", "v4")
        return
    raise RuntimeError(f"Unsupported service: {service_name}")
