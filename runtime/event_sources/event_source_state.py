"""Spec 139 — Event source state and history persistence.

Stores source configs, per-source state, and polling history.
Delegates to the active persistence backend (filesystem or SQLite).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from runtime.taskframe import json_safe, utc_now


# ---------------------------------------------------------------------------
# History record builder
# ---------------------------------------------------------------------------

def build_history_record(
    source_id: str,
    *,
    ok: bool,
    adapter: str = "",
    mode: str = "",
    raw_count: int = 0,
    event_count: int = 0,
    duplicate_count: int = 0,
    enqueued_count: int = 0,
    error: str = "",
    error_category: str = "",
    cursor_update: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    return {
        "history_id": str(uuid.uuid4()),
        "source_id": str(source_id),
        "ok": bool(ok),
        "adapter": str(adapter),
        "mode": str(mode),
        "raw_count": int(raw_count),
        "event_count": int(event_count),
        "duplicate_count": int(duplicate_count),
        "enqueued_count": int(enqueued_count),
        "error": str(error),
        "error_category": str(error_category),
        "cursor_update": dict(cursor_update or {}),
        "evidence": dict(evidence or {}),
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# Backend accessors
# ---------------------------------------------------------------------------

def _get_backend(runtime_data_dir: Path | str):
    from runtime.persistence_backends.backend_factory import get_persistence_backend
    return get_persistence_backend(runtime_data_dir)


# ---------------------------------------------------------------------------
# Source config CRUD
# ---------------------------------------------------------------------------

def save_event_source(
    config: dict[str, Any],
    runtime_data_dir: Path | str = "runtime_data",
) -> None:
    updated = dict(config)
    updated["updated_at"] = utc_now()
    _get_backend(runtime_data_dir).save_event_source(updated)


def get_event_source(
    source_id: str,
    runtime_data_dir: Path | str = "runtime_data",
) -> dict[str, Any] | None:
    return _get_backend(runtime_data_dir).get_event_source(source_id)


def list_event_sources(
    runtime_data_dir: Path | str = "runtime_data",
    *,
    enabled_only: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if enabled_only:
        filters["enabled"] = True
    return _get_backend(runtime_data_dir).list_event_sources(limit=limit, **filters)


def create_event_source(
    config: dict[str, Any],
    runtime_data_dir: Path | str = "runtime_data",
) -> dict[str, Any]:
    from .event_source_contract import validate_event_source_config

    ok, errors = validate_event_source_config(config)
    if not ok:
        return {"ok": False, "error": "; ".join(errors)}

    source_id = config["source_id"]
    existing = get_event_source(source_id, runtime_data_dir)
    if existing:
        return {"ok": False, "error": f"Source {source_id!r} already exists."}

    save_event_source(config, runtime_data_dir)
    return {"ok": True, "source_id": source_id, "record": config}


def enable_event_source(
    source_id: str,
    runtime_data_dir: Path | str = "runtime_data",
) -> dict[str, Any]:
    record = get_event_source(source_id, runtime_data_dir)
    if not record:
        return {"ok": False, "error": f"Source {source_id!r} not found."}
    record["enabled"] = True
    record["updated_at"] = utc_now()
    save_event_source(record, runtime_data_dir)
    return {"ok": True, "source_id": source_id}


def disable_event_source(
    source_id: str,
    runtime_data_dir: Path | str = "runtime_data",
) -> dict[str, Any]:
    record = get_event_source(source_id, runtime_data_dir)
    if not record:
        return {"ok": False, "error": f"Source {source_id!r} not found."}
    record["enabled"] = False
    record["updated_at"] = utc_now()
    save_event_source(record, runtime_data_dir)
    return {"ok": True, "source_id": source_id}


# ---------------------------------------------------------------------------
# Source state CRUD
# ---------------------------------------------------------------------------

def get_event_source_state(
    source_id: str,
    runtime_data_dir: Path | str = "runtime_data",
) -> dict[str, Any]:
    state = _get_backend(runtime_data_dir).get_event_source_state(source_id)
    if state:
        return state
    return _default_state(source_id)


def save_event_source_state(
    state: dict[str, Any],
    runtime_data_dir: Path | str = "runtime_data",
) -> None:
    updated = dict(state)
    updated["updated_at"] = utc_now()
    _get_backend(runtime_data_dir).save_event_source_state(updated)


def _default_state(source_id: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "source_id": str(source_id),
        "last_poll_started_at": "",
        "last_poll_completed_at": "",
        "last_success_at": "",
        "last_error": "",
        "last_error_category": "",
        "poll_count": 0,
        "event_count": 0,
        "duplicate_count": 0,
        "cursor": {
            "watermark": "",
            "seen_ids": [],
        },
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# Polling history
# ---------------------------------------------------------------------------

def append_event_source_history(
    record: dict[str, Any],
    runtime_data_dir: Path | str = "runtime_data",
) -> None:
    _get_backend(runtime_data_dir).append_event_source_history(record)


def list_event_source_history(
    runtime_data_dir: Path | str = "runtime_data",
    *,
    source_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if source_id:
        filters["source_id"] = source_id
    return _get_backend(runtime_data_dir).list_event_source_history(limit=limit, **filters)


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def update_cursor(
    source_id: str,
    cursor_update: dict[str, Any],
    runtime_data_dir: Path | str = "runtime_data",
) -> None:
    state = get_event_source_state(source_id, runtime_data_dir)
    cursor = dict(state.get("cursor") or {})
    if "watermark" in cursor_update:
        cursor["watermark"] = str(cursor_update["watermark"])
    if "seen_ids" in cursor_update:
        existing = list(cursor.get("seen_ids") or [])
        new_ids = list(cursor_update["seen_ids"])
        merged = list(dict.fromkeys(existing + new_ids))
        cursor["seen_ids"] = merged[-500:]
    state["cursor"] = cursor
    save_event_source_state(state, runtime_data_dir)
