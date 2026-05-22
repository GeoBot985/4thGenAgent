"""Spec 139 — Operator event sources panel: read-only summary helper."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_event_sources_panel(
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    """Return a read-only summary of the event source subsystem state.

    Never triggers processing. Returns panel-ready shape with sources,
    recent history, and recent enqueued events.
    """
    from runtime.event_sources.event_source_state import (
        list_event_sources,
        list_event_source_history,
        get_event_source_state,
    )

    try:
        sources = list_event_sources(runtime_data_dir)
        enabled_count = sum(1 for s in sources if s.get("enabled"))
        needs_auth_count = 0

        source_summaries: list[dict[str, Any]] = []
        for src in sources:
            source_id = str(src.get("source_id") or "")
            state = get_event_source_state(source_id, runtime_data_dir)
            health_status = _source_health_status(src, state)
            if health_status == "needs_auth":
                needs_auth_count += 1
            source_summaries.append({
                "source_id": source_id,
                "name": src.get("name", ""),
                "adapter": src.get("adapter", ""),
                "mode": src.get("mode", ""),
                "enabled": bool(src.get("enabled")),
                "event_source": src.get("event_source", ""),
                "event_type": src.get("event_type", ""),
                "health_status": health_status,
                "last_poll_completed_at": state.get("last_poll_completed_at", ""),
                "last_success_at": state.get("last_success_at", ""),
                "last_error": state.get("last_error", ""),
                "poll_count": state.get("poll_count", 0),
                "event_count": state.get("event_count", 0),
                "duplicate_count": state.get("duplicate_count", 0),
            })

        recent_history = list_event_source_history(runtime_data_dir, limit=20)

        last_poll_at = ""
        if recent_history:
            last_poll_at = str(recent_history[0].get("created_at") or "")

        recent_enqueued_events = _load_recent_enqueued(runtime_data_dir, limit=10)

        warnings: list[str] = []
        if needs_auth_count > 0:
            warnings.append(f"{needs_auth_count} source(s) need authentication credentials.")

        return {
            "ok": True,
            "summary": {
                "source_count": len(sources),
                "enabled_count": enabled_count,
                "needs_auth_count": needs_auth_count,
                "last_poll_at": last_poll_at,
            },
            "sources": source_summaries,
            "recent_history": [_slim_history(h) for h in recent_history],
            "recent_enqueued_events": recent_enqueued_events,
            "warnings": warnings,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "summary": {"source_count": 0, "enabled_count": 0, "needs_auth_count": 0, "last_poll_at": ""},
            "sources": [],
            "recent_history": [],
            "recent_enqueued_events": [],
            "warnings": [],
        }


def _source_health_status(config: dict[str, Any], state: dict[str, Any]) -> str:
    if not config.get("enabled"):
        return "disabled"
    adapter = str(config.get("adapter") or "")
    auth = dict(config.get("auth") or {})
    if adapter == "gmail_readonly" and auth.get("requires_credentials"):
        token_path = str(auth.get("token_path") or "")
        import pathlib
        if token_path and not pathlib.Path(token_path).expanduser().is_file():
            return "needs_auth"
    last_error = str(state.get("last_error") or "")
    if last_error:
        return "error"
    if state.get("last_success_at"):
        return "ok"
    return "ready"


def _slim_history(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "history_id": record.get("history_id", ""),
        "source_id": record.get("source_id", ""),
        "ok": record.get("ok", False),
        "adapter": record.get("adapter", ""),
        "raw_count": record.get("raw_count", 0),
        "event_count": record.get("event_count", 0),
        "duplicate_count": record.get("duplicate_count", 0),
        "enqueued_count": record.get("enqueued_count", 0),
        "error": record.get("error", ""),
        "error_category": record.get("error_category", ""),
        "created_at": record.get("created_at", ""),
    }


def _load_recent_enqueued(
    runtime_data_dir: str | Path,
    limit: int = 10,
) -> list[dict[str, Any]]:
    try:
        from runtime.event_queue import _list_durable_records
        from runtime.event_queue_contract import STATUS_PENDING

        records = _list_durable_records(runtime_data_dir=runtime_data_dir, limit=500)
        event_source_records = [
            r for r in records
            if str(r.get("source") or "").startswith("fixture")
            or str(r.get("source") or "") in ("gmail", "gmail_customer_support")
            or str(r.get("source") or "").startswith("src_")
        ]
        event_source_records.sort(
            key=lambda r: str(r.get("created_at") or ""),
            reverse=True,
        )
        return [
            {
                "queue_id": r.get("queue_id", ""),
                "event_id": r.get("event_id", ""),
                "source": r.get("source", ""),
                "event_type": r.get("event_type", ""),
                "status": r.get("status", ""),
                "created_at": r.get("created_at", ""),
            }
            for r in event_source_records[:limit]
        ]
    except Exception:
        return []
