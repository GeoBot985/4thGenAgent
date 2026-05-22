"""Spec 139 — Event source config contract: canonical shape, builders, validation."""
from __future__ import annotations

import uuid
from typing import Any

from runtime.taskframe import utc_now

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADAPTER_FIXTURE_JSON = "fixture_json"
ADAPTER_GMAIL_READONLY = "gmail_readonly"
KNOWN_ADAPTERS = (ADAPTER_FIXTURE_JSON, ADAPTER_GMAIL_READONLY)

MODE_FIXTURE = "fixture"
MODE_LIVE_READ = "live_read"
KNOWN_MODES = (MODE_FIXTURE, MODE_LIVE_READ)

CURSOR_TYPE_WATERMARK = "watermark"
CURSOR_TYPE_SEEN_IDS = "seen_ids"
KNOWN_CURSOR_TYPES = (CURSOR_TYPE_WATERMARK, CURSOR_TYPE_SEEN_IDS)

# Structured failure categories for event source operations
FAILURE_SOURCE_NOT_FOUND = "source_not_found"
FAILURE_SOURCE_DISABLED = "source_disabled"
FAILURE_ADAPTER_NOT_FOUND = "adapter_not_found"
FAILURE_CREDENTIALS_MISSING = "credentials_missing"
FAILURE_AUTH_FAILED = "auth_failed"
FAILURE_EXTERNAL_DEPENDENCY_UNAVAILABLE = "external_dependency_unavailable"
FAILURE_POLL_TIMEOUT = "poll_timeout"
FAILURE_NORMALIZATION_FAILED = "normalization_failed"
FAILURE_DEDUPE_FAILED = "dedupe_failed"
FAILURE_QUEUE_ENQUEUE_FAILED = "queue_enqueue_failed"
FAILURE_PERSISTENCE_ERROR = "persistence_error"
FAILURE_MALFORMED_FIXTURE = "malformed_fixture"
FAILURE_UNSUPPORTED_MODE = "unsupported_mode"


def new_source_id() -> str:
    return f"src_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def build_event_source_config(
    source_id: str,
    name: str,
    adapter: str,
    mode: str,
    event_source: str,
    event_type: str,
    *,
    enabled: bool = False,
    route_hint: str = "",
    poll: dict[str, Any] | None = None,
    dedupe: dict[str, Any] | None = None,
    cursor: dict[str, Any] | None = None,
    auth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    return {
        "source_id": str(source_id),
        "name": str(name),
        "enabled": bool(enabled),
        "adapter": str(adapter),
        "mode": str(mode),
        "event_source": str(event_source),
        "event_type": str(event_type),
        "route_hint": str(route_hint),
        "poll": dict(poll or {}),
        "dedupe": dict(dedupe or {}),
        "cursor": dict(cursor or {}),
        "auth": dict(auth or {}),
        "created_at": now,
        "updated_at": now,
    }


def build_fixture_source_config(
    source_id: str,
    name: str,
    event_source: str,
    event_type: str,
    fixture_path: str,
    *,
    enabled: bool = True,
    max_events_per_poll: int = 10,
    dedupe_key_template: str = "fixture:{message_id}",
) -> dict[str, Any]:
    return build_event_source_config(
        source_id=source_id,
        name=name,
        adapter=ADAPTER_FIXTURE_JSON,
        mode=MODE_FIXTURE,
        event_source=event_source,
        event_type=event_type,
        enabled=enabled,
        poll={"fixture_path": fixture_path, "max_events_per_poll": max_events_per_poll},
        dedupe={"key_template": dedupe_key_template},
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_event_source_config(config: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(config, dict):
        return False, ["config must be a dict."]

    source_id = config.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        errors.append("source_id must be a non-empty string.")

    name = config.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name must be a non-empty string.")

    adapter = config.get("adapter")
    if not isinstance(adapter, str) or not adapter.strip():
        errors.append("adapter must be a non-empty string.")

    mode = config.get("mode")
    if mode not in KNOWN_MODES:
        errors.append(f"mode must be one of {KNOWN_MODES}; got {mode!r}.")

    event_source = config.get("event_source")
    if not isinstance(event_source, str) or not event_source.strip():
        errors.append("event_source must be a non-empty string.")

    event_type = config.get("event_type")
    if not isinstance(event_type, str) or not event_type.strip():
        errors.append("event_type must be a non-empty string.")

    poll = config.get("poll")
    if poll is not None and not isinstance(poll, dict):
        errors.append("poll must be a dict if provided.")

    dedupe = config.get("dedupe")
    if dedupe is not None and not isinstance(dedupe, dict):
        errors.append("dedupe must be a dict if provided.")

    return len(errors) == 0, errors
