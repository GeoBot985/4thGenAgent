"""Spec 137 — Durable Event Queue canonical record shape, status constants, and dedupe helpers."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from .taskframe import utc_now

# ---------------------------------------------------------------------------
# Durable queue status constants
# ---------------------------------------------------------------------------

STATUS_PENDING = "PENDING"
STATUS_CLAIMED = "CLAIMED"
STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED_RETRYABLE = "FAILED_RETRYABLE"
STATUS_FAILED_PERMANENT = "FAILED_PERMANENT"
STATUS_DEAD_LETTER = "DEAD_LETTER"
STATUS_CANCELLED = "CANCELLED"

TERMINAL_STATUSES: frozenset[str] = frozenset({
    STATUS_COMPLETED,
    STATUS_FAILED_PERMANENT,
    STATUS_DEAD_LETTER,
    STATUS_CANCELLED,
})

ACTIVE_STATUSES: frozenset[str] = frozenset({
    STATUS_PENDING,
    STATUS_CLAIMED,
    STATUS_PROCESSING,
    STATUS_FAILED_RETRYABLE,
})

# ---------------------------------------------------------------------------
# Failure category constants
# ---------------------------------------------------------------------------

FAILURE_ROUTE_NOT_FOUND = "route_not_found"
FAILURE_MANIFEST_NOT_FOUND = "manifest_not_found"
FAILURE_INPUT_MAPPING_FAILED = "input_mapping_failed"
FAILURE_TRANSIENT_TOOL_FAILURE = "transient_tool_failure"
FAILURE_LLM_TRANSIENT_FAILURE = "llm_transient_failure"
FAILURE_VALIDATION_FAILED = "validation_failed"
FAILURE_RUNTIME_EXCEPTION = "runtime_exception"
FAILURE_POLICY_BLOCKED = "policy_blocked"

RETRYABLE_FAILURE_CATEGORIES: frozenset[str] = frozenset({
    FAILURE_TRANSIENT_TOOL_FAILURE,
    FAILURE_LLM_TRANSIENT_FAILURE,
    FAILURE_RUNTIME_EXCEPTION,
})

NON_RETRYABLE_FAILURE_CATEGORIES: frozenset[str] = frozenset({
    FAILURE_ROUTE_NOT_FOUND,
    FAILURE_MANIFEST_NOT_FOUND,
    FAILURE_INPUT_MAPPING_FAILED,
    FAILURE_VALIDATION_FAILED,
    FAILURE_POLICY_BLOCKED,
})

# ---------------------------------------------------------------------------
# Retry policy defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 0

RETRY_POLICY: dict[str, Any] = {
    "max_attempts": DEFAULT_MAX_ATTEMPTS,
    "retry_delay_seconds": DEFAULT_RETRY_DELAY_SECONDS,
    "retryable_categories": sorted(RETRYABLE_FAILURE_CATEGORIES),
}

# ---------------------------------------------------------------------------
# Status classification helpers
# ---------------------------------------------------------------------------


def is_terminal_status(status: str) -> bool:
    return status in TERMINAL_STATUSES


def is_active_status(status: str) -> bool:
    return status in ACTIVE_STATUSES


def is_retryable_failure_category(category: str) -> bool:
    return category in RETRYABLE_FAILURE_CATEGORIES


def is_permanent_failure_category(category: str) -> bool:
    return category in NON_RETRYABLE_FAILURE_CATEGORIES


# ---------------------------------------------------------------------------
# Failure classification from runtime status strings
# ---------------------------------------------------------------------------

_STATUS_TO_FAILURE_CATEGORY: dict[str, str] = {
    "NO_ROUTE": FAILURE_ROUTE_NOT_FOUND,
    "ROUTE_NOT_FOUND": FAILURE_ROUTE_NOT_FOUND,
    "MANIFEST_NOT_FOUND": FAILURE_MANIFEST_NOT_FOUND,
    "ROUTE_MAPPING_FAILED": FAILURE_INPUT_MAPPING_FAILED,
    "FAILED_VALIDATION": FAILURE_VALIDATION_FAILED,
    "POLICY_BLOCKED": FAILURE_POLICY_BLOCKED,
    "LIVE_EFFECT_BLOCKED": FAILURE_POLICY_BLOCKED,
    "INVALID_EVENT": FAILURE_INPUT_MAPPING_FAILED,
    "SOURCE_CONTRACT_VIOLATION": FAILURE_INPUT_MAPPING_FAILED,
    "LLM_UNAVAILABLE": FAILURE_LLM_TRANSIENT_FAILURE,
    "FAILED_EXECUTION": FAILURE_RUNTIME_EXCEPTION,
    "TASKFRAME_CREATION_FAILED": FAILURE_RUNTIME_EXCEPTION,
    "FAILED": FAILURE_RUNTIME_EXCEPTION,
    "FAILED_COMPLETION": FAILURE_RUNTIME_EXCEPTION,
}


def classify_failure_from_status(status_str: str) -> str:
    """Derive a failure category from a runtime status string."""
    return _STATUS_TO_FAILURE_CATEGORY.get(str(status_str).upper(), FAILURE_RUNTIME_EXCEPTION)


# ---------------------------------------------------------------------------
# Dedupe key builder
# ---------------------------------------------------------------------------


def build_dedupe_key(event: dict[str, Any]) -> str:
    """Build a deterministic dedupe key from source + event_type + stable payload identity."""
    source = str(event.get("source", "") or "")
    event_type = str(event.get("event_type", "") or "")
    payload: dict[str, Any] = dict(event.get("payload") or {})

    if source in ("manual", "command", "cli"):
        identity = str(event.get("event_id", "") or "")
    elif source in ("gmail", "email"):
        identity = str(
            payload.get("message_id")
            or payload.get("gmail_message_id")
            or event.get("event_id", "")
            or ""
        )
    elif source in ("call_centre", "call_center", "telephony"):
        identity = str(
            payload.get("message_id")
            or payload.get("call_id")
            or event.get("event_id", "")
            or ""
        )
    elif source == "schedule":
        schedule_id = str(payload.get("schedule_id", "") or "")
        scheduled_time = str(payload.get("scheduled_time", "") or "")
        identity = f"{schedule_id}:{scheduled_time}"
    elif source in ("file", "file_watch", "filesystem"):
        file_path = str(payload.get("file_path", "") or "")
        content_hash = str(payload.get("content_hash", "") or "")
        identity = f"{file_path}:{content_hash}"
    elif source in ("database", "db", "postgres", "mysql", "sqlite"):
        source_table = str(payload.get("source_table", "") or "")
        source_key = str(payload.get("source_key", "") or payload.get("row_id", "") or "")
        version = str(payload.get("version", "") or payload.get("timestamp", "") or "")
        identity = f"{source_table}:{source_key}:{version}"
    else:
        identity = str(event.get("event_id", "") or "")

    key_data = f"{source}:{event_type}:{identity}"
    return hashlib.sha256(key_data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Queue record builder
# ---------------------------------------------------------------------------


def build_durable_queue_record(
    event: dict[str, Any],
    *,
    priority: int = 100,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    available_at: str | None = None,
) -> dict[str, Any]:
    """Build a canonical durable queue record from an event dict."""
    now = utc_now()
    queue_id = str(uuid.uuid4())
    event_id = str(event.get("event_id", "") or "")
    dedupe_key = build_dedupe_key(event)

    return {
        "queue_id": queue_id,
        "event_id": event_id,
        "source": str(event.get("source", "") or ""),
        "event_type": str(event.get("event_type", "") or ""),
        "status": STATUS_PENDING,
        "priority": int(priority),
        "attempt_count": 0,
        "max_attempts": int(max_attempts),
        "available_at": available_at or now,
        "claimed_at": "",
        "claimed_by": "",
        "completed_at": "",
        "linked_frame_id": "",
        "dedupe_key": dedupe_key,
        "payload_json": dict(event.get("payload") or {}),
        "last_error": "",
        "failure_category": "",
        "created_at": now,
        "updated_at": now,
    }


def update_durable_queue_record(existing: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Return a new record merging existing fields with overrides, always bumping updated_at."""
    updated = dict(existing)
    updated.update(overrides)
    updated["updated_at"] = utc_now()
    return updated
