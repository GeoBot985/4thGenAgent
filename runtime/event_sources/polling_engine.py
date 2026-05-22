"""Spec 139 — Event source polling engine.

Orchestrates: load config → load state → adapter health → adapter poll →
normalize → dedupe/enqueue → persist cursor/state → write history.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.taskframe import utc_now


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

def _get_adapter(adapter_id: str) -> Any:
    from .event_source_contract import ADAPTER_FIXTURE_JSON, ADAPTER_GMAIL_READONLY, FAILURE_ADAPTER_NOT_FOUND

    if adapter_id == ADAPTER_FIXTURE_JSON:
        from .adapters.fixture_json import FixtureJsonAdapter
        return FixtureJsonAdapter()
    if adapter_id == ADAPTER_GMAIL_READONLY:
        from .adapters.gmail_readonly import GmailReadonlyAdapter
        return GmailReadonlyAdapter()
    raise ValueError(f"Unknown adapter: {adapter_id!r}")


# ---------------------------------------------------------------------------
# Primary public API
# ---------------------------------------------------------------------------

def poll_event_source(
    source_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Poll a single event source by ID. Returns a structured result dict."""
    from .event_source_contract import (
        FAILURE_SOURCE_NOT_FOUND,
        FAILURE_SOURCE_DISABLED,
        FAILURE_ADAPTER_NOT_FOUND,
    )
    from .event_source_state import (
        get_event_source,
        get_event_source_state,
        save_event_source_state,
        append_event_source_history,
        build_history_record,
        update_cursor,
    )

    config = get_event_source(source_id, runtime_data_dir)
    if config is None:
        hist = build_history_record(
            source_id, ok=False,
            error=f"Source not found: {source_id!r}",
            error_category=FAILURE_SOURCE_NOT_FOUND,
        )
        append_event_source_history(hist, runtime_data_dir)
        return {"ok": False, "source_id": source_id, "error": hist["error"], "error_category": FAILURE_SOURCE_NOT_FOUND}

    if not config.get("enabled"):
        hist = build_history_record(
            source_id, ok=False,
            adapter=str(config.get("adapter") or ""),
            mode=str(config.get("mode") or ""),
            error=f"Source {source_id!r} is disabled.",
            error_category=FAILURE_SOURCE_DISABLED,
        )
        append_event_source_history(hist, runtime_data_dir)
        return {"ok": False, "source_id": source_id, "error": hist["error"], "error_category": FAILURE_SOURCE_DISABLED}

    adapter_id = str(config.get("adapter") or "")
    try:
        adapter = _get_adapter(adapter_id)
    except ValueError as exc:
        hist = build_history_record(
            source_id, ok=False,
            adapter=adapter_id,
            mode=str(config.get("mode") or ""),
            error=str(exc),
            error_category=FAILURE_ADAPTER_NOT_FOUND,
        )
        append_event_source_history(hist, runtime_data_dir)
        return {"ok": False, "source_id": source_id, "error": str(exc), "error_category": FAILURE_ADAPTER_NOT_FOUND}

    state = get_event_source_state(source_id, runtime_data_dir)

    # Mark poll started
    state["last_poll_started_at"] = utc_now()
    save_event_source_state(state, runtime_data_dir)

    try:
        poll_result = adapter.poll(config, state, str(runtime_data_dir))
    except Exception as exc:
        error_msg = f"Adapter poll raised exception: {exc}"
        state["last_error"] = error_msg
        state["last_error_category"] = "normalization_failed"
        save_event_source_state(state, runtime_data_dir)
        hist = build_history_record(
            source_id, ok=False,
            adapter=adapter_id, mode=str(config.get("mode") or ""),
            error=error_msg, error_category="normalization_failed",
        )
        append_event_source_history(hist, runtime_data_dir)
        return {"ok": False, "source_id": source_id, "error": error_msg}

    if not poll_result.get("ok"):
        state["last_error"] = str(poll_result.get("error") or "")
        state["last_error_category"] = str(poll_result.get("error_category") or "")
        state["last_poll_completed_at"] = utc_now()
        state["poll_count"] = int(state.get("poll_count") or 0) + 1
        save_event_source_state(state, runtime_data_dir)
        hist = build_history_record(
            source_id, ok=False,
            adapter=adapter_id, mode=str(config.get("mode") or ""),
            error=str(poll_result.get("error") or ""),
            error_category=str(poll_result.get("error_category") or ""),
        )
        append_event_source_history(hist, runtime_data_dir)
        return {**poll_result, "source_id": source_id}

    # Enqueue events via durable queue
    events = list(poll_result.get("events") or [])
    enqueue_result = enqueue_polled_events(source_id, events, runtime_data_dir)

    enqueued_count = int(enqueue_result.get("enqueued_count") or 0)
    duplicate_count = int(enqueue_result.get("duplicate_count") or 0)

    # Persist cursor then reload state so final save includes the updated cursor
    cursor_update = dict(poll_result.get("cursor_update") or {})
    if cursor_update:
        update_cursor(source_id, cursor_update, runtime_data_dir)
    state = get_event_source_state(source_id, runtime_data_dir)

    # Update state
    now = utc_now()
    state["last_poll_completed_at"] = now
    state["last_success_at"] = now
    state["last_error"] = ""
    state["last_error_category"] = ""
    state["poll_count"] = int(state.get("poll_count") or 0) + 1
    state["event_count"] = int(state.get("event_count") or 0) + enqueued_count
    state["duplicate_count"] = int(state.get("duplicate_count") or 0) + duplicate_count
    save_event_source_state(state, runtime_data_dir)

    # Write history (redact message body in history evidence)
    hist = build_history_record(
        source_id, ok=True,
        adapter=adapter_id, mode=str(config.get("mode") or ""),
        raw_count=int(poll_result.get("raw_count") or 0),
        event_count=len(events),
        duplicate_count=duplicate_count,
        enqueued_count=enqueued_count,
        cursor_update=cursor_update,
        evidence=_redact_history_evidence(poll_result.get("evidence") or {}),
    )
    append_event_source_history(hist, runtime_data_dir)

    return {
        "ok": True,
        "source_id": source_id,
        "adapter": adapter_id,
        "mode": str(config.get("mode") or ""),
        "raw_count": int(poll_result.get("raw_count") or 0),
        "event_count": len(events),
        "enqueued_count": enqueued_count,
        "duplicate_count": duplicate_count,
        "warnings": list(poll_result.get("warnings") or []),
        "enqueue_warnings": list(enqueue_result.get("warnings") or []),
    }


def poll_enabled_event_sources(
    runtime_data_dir: str | Path = "runtime_data",
    limit: int = 10,
) -> dict[str, Any]:
    """Poll all enabled event sources in a bounded pass."""
    from .event_source_state import list_event_sources

    sources = list_event_sources(runtime_data_dir, enabled_only=True, limit=limit)
    results: list[dict[str, Any]] = []
    total_enqueued = 0
    total_duplicates = 0
    failed_sources: list[str] = []

    for src in sources:
        source_id = str(src.get("source_id") or "")
        try:
            result = poll_event_source(source_id, runtime_data_dir)
        except Exception as exc:
            result = {"ok": False, "source_id": source_id, "error": str(exc)}
        results.append(result)
        if result.get("ok"):
            total_enqueued += int(result.get("enqueued_count") or 0)
            total_duplicates += int(result.get("duplicate_count") or 0)
        else:
            failed_sources.append(source_id)

    return {
        "ok": len(failed_sources) == 0,
        "sources_polled": len(sources),
        "total_enqueued": total_enqueued,
        "total_duplicates": total_duplicates,
        "failed_sources": failed_sources,
        "results": results,
    }


def normalize_polled_events(poll_result: dict[str, Any]) -> dict[str, Any]:
    """Return the events list from a poll result, normalized and validated."""
    events = list(poll_result.get("events") or [])
    valid: list[dict[str, Any]] = []
    warnings: list[str] = []
    for evt in events:
        if not isinstance(evt, dict):
            warnings.append(f"Skipping non-dict event: {evt!r}")
            continue
        if not evt.get("event_id") or not evt.get("source") or not evt.get("event_type"):
            warnings.append(f"Skipping event missing required fields: {list(evt.keys())}")
            continue
        valid.append(evt)
    return {"events": valid, "count": len(valid), "warnings": warnings}


def enqueue_polled_events(
    source_id: str,
    events: list[dict[str, Any]],
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Enqueue a list of normalized events into the durable queue.

    Deduplication is handled by the durable queue's dedupe_key mechanism.
    """
    from runtime.event_queue import enqueue_event

    enqueued_count = 0
    duplicate_count = 0
    warnings: list[str] = []

    for evt in events:
        try:
            result = enqueue_event(evt, runtime_data_dir)
            if result.get("ok"):
                enqueued_count += 1
            elif result.get("duplicate"):
                duplicate_count += 1
            else:
                warnings.append(f"Enqueue failed for event {evt.get('event_id')}: {result}")
        except Exception as exc:
            warnings.append(f"Enqueue raised exception for {evt.get('event_id')}: {exc}")

    return {
        "ok": True,
        "enqueued_count": enqueued_count,
        "duplicate_count": duplicate_count,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# History evidence redaction
# ---------------------------------------------------------------------------

def _redact_history_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(evidence)
    messages = redacted.get("messages")
    if isinstance(messages, list):
        safe_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                safe_msg = {k: v for k, v in msg.items() if k not in ("body", "message", "snippet")}
                safe_messages.append(safe_msg)
        redacted["messages"] = safe_messages
    return redacted
