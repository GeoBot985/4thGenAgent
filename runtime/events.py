from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from .errors import EventValidationError
from .taskframe import utc_now


@dataclass
class RuntimeEvent:
    event_id: str
    event_type: str
    source: str
    payload: dict[str, Any]
    received_at: str
    status: str = "RECEIVED"
    linked_frame_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


Event = RuntimeEvent


def new_event_id() -> str:
    return f"evt_{uuid4().hex}"


def create_event(
    event_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeEvent:
    if not isinstance(event_type, str) or not event_type.strip():
        raise EventValidationError("event_type must be a non-empty string.")
    if not isinstance(source, str) or not source.strip():
        raise EventValidationError("source must be a non-empty string.")
    if payload is None:
        payload = {}
    if metadata is None:
        metadata = {}
    if not isinstance(payload, dict):
        raise EventValidationError("payload must be a dict.")
    if not isinstance(metadata, dict):
        raise EventValidationError("metadata must be a dict.")

    return RuntimeEvent(
        event_id=new_event_id(),
        event_type=event_type,
        source=source,
        payload=dict(payload),
        received_at=utc_now(),
        status="RECEIVED",
        linked_frame_id=None,
        metadata=dict(metadata),
    )


def validate_event(event: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(event, dict):
        return False, ["event must be a dict."]

    event_id = event.get("event_id")
    source = event.get("source")
    event_type = event.get("event_type")
    payload = event.get("payload")
    received_at = event.get("received_at")

    if not isinstance(event_id, str) or not event_id.strip():
        errors.append("event_id")
    if not isinstance(source, str) or not source.strip():
        errors.append("source")
    if not isinstance(event_type, str) or not event_type.strip():
        errors.append("event_type")
    if not isinstance(payload, dict):
        errors.append("payload")
    if not isinstance(received_at, str) or not received_at.strip():
        errors.append("received_at")

    return len(errors) == 0, errors


def event_to_dict(event: RuntimeEvent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, RuntimeEvent):
        return asdict(event)
    return dict(event)


def intake_and_run_event(event_data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    from .event_store import intake_and_run_event as _intake_and_run_event

    return _intake_and_run_event(event_data, **kwargs)
