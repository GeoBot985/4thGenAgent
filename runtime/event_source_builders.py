from __future__ import annotations

from typing import Any

from .events import create_event


def build_operator_event(
    event_type: str,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ev = create_event(event_type=event_type, source="operator_ui", payload=payload or {}, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_schedule_event(
    event_type: str,
    schedule_id: str = "",
    cron_expression: str = "",
    triggered_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if schedule_id:
        payload["schedule_id"] = schedule_id
    if cron_expression:
        payload["cron_expression"] = cron_expression
    if triggered_at:
        payload["triggered_at"] = triggered_at
    ev = create_event(event_type=event_type, source="schedule", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_customer_inbox_event(
    event_type: str,
    message_id: str,
    message: str,
    channel: str,
    customer_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message_id": message_id,
        "message": message,
        "channel": channel,
    }
    if customer_id:
        payload["customer_id"] = customer_id
    ev = create_event(event_type=event_type, source="customer_inbox", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_gmail_event(
    event_type: str,
    message_id: str,
    from_address: str,
    subject: str,
    body: str = "",
    to: str = "",
    cc: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message_id": message_id,
        "from": from_address,
        "subject": subject,
    }
    if body:
        payload["body"] = body
    if to:
        payload["to"] = to
    if cc:
        payload["cc"] = cc
    ev = create_event(event_type=event_type, source="gmail", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_calendar_event(
    event_type: str,
    event_id: str,
    title: str,
    start: str,
    end: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": event_id,
        "title": title,
        "start": start,
    }
    if end:
        payload["end"] = end
    if location:
        payload["location"] = location
    if attendees:
        payload["attendees"] = list(attendees)
    ev = create_event(event_type=event_type, source="calendar", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_sheet_event(
    event_type: str,
    spreadsheet_id: str,
    range: str,
    values: list[list[Any]] | None = None,
    sheet_name: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "spreadsheet_id": spreadsheet_id,
        "range": range,
    }
    if values is not None:
        payload["values"] = values
    if sheet_name:
        payload["sheet_name"] = sheet_name
    ev = create_event(event_type=event_type, source="sheet", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_rpa_event(
    event_type: str,
    task_id: str,
    task_type: str,
    url: str = "",
    selector: str = "",
    value: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": task_id,
        "task_type": task_type,
    }
    if url:
        payload["url"] = url
    if selector:
        payload["selector"] = selector
    if value:
        payload["value"] = value
    ev = create_event(event_type=event_type, source="rpa", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }


def build_system_event(
    event_type: str,
    component: str,
    event_name: str,
    severity: str = "",
    details: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "component": component,
        "event_name": event_name,
    }
    if severity:
        payload["severity"] = severity
    if details:
        payload["details"] = details
    ev = create_event(event_type=event_type, source="system", payload=payload, metadata=metadata or {})
    return {
        "event_id": ev.event_id,
        "source": ev.source,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "received_at": ev.received_at,
        "metadata": ev.metadata,
    }
