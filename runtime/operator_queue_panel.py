"""Spec 137 — Operator UI queue panel data helper.

Provides a non-invasive data source for the operator UI queue panel.
Read-only; never triggers processing or side effects.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .event_queue_contract import (
    STATUS_PENDING,
    STATUS_CLAIMED,
    STATUS_PROCESSING,
    STATUS_COMPLETED,
    STATUS_FAILED_RETRYABLE,
    STATUS_DEAD_LETTER,
    STATUS_FAILED_PERMANENT,
    STATUS_CANCELLED,
)
from .event_queue import _list_durable_records, queue_health


_RECENT_COMPLETED_LIMIT = 20


def build_queue_panel(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    """Build the queue panel data dict for the operator UI.

    Returns counts, pending/processing/failed_retryable/dead_letter slices,
    and recent completed items. Never starts processing.
    """
    try:
        health = queue_health(runtime_data_dir)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "summary": {}, "pending": [], "processing": [], "failed_retryable": [], "dead_letter": [], "recent_completed": []}

    try:
        all_records = _list_durable_records(runtime_data_dir=runtime_data_dir, limit=10_000)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "summary": {}, "pending": [], "processing": [], "failed_retryable": [], "dead_letter": [], "recent_completed": []}

    pending = [_panel_record(r) for r in all_records if r.get("status") == STATUS_PENDING]
    processing = [_panel_record(r) for r in all_records if r.get("status") in (STATUS_CLAIMED, STATUS_PROCESSING)]
    failed_retryable = [_panel_record(r) for r in all_records if r.get("status") == STATUS_FAILED_RETRYABLE]
    dead_letter = [_panel_record(r) for r in all_records if r.get("status") == STATUS_DEAD_LETTER]

    completed = [r for r in all_records if r.get("status") == STATUS_COMPLETED]
    completed.sort(key=lambda r: str(r.get("completed_at") or r.get("updated_at") or ""), reverse=True)
    recent_completed = [_panel_record(r) for r in completed[:_RECENT_COMPLETED_LIMIT]]

    summary = {
        "total": len(all_records),
        "pending": len(pending),
        "processing": len(processing),
        "failed_retryable": len(failed_retryable),
        "dead_letter": len(dead_letter),
        "completed": len(completed),
        "failed_permanent": sum(1 for r in all_records if r.get("status") == STATUS_FAILED_PERMANENT),
        "cancelled": sum(1 for r in all_records if r.get("status") == STATUS_CANCELLED),
        "backend": health.get("backend", ""),
        "oldest_pending_created_at": health.get("oldest_pending_created_at", ""),
    }

    return {
        "ok": True,
        "summary": summary,
        "pending": pending,
        "processing": processing,
        "failed_retryable": failed_retryable,
        "dead_letter": dead_letter,
        "recent_completed": recent_completed,
    }


def _panel_record(record: dict[str, Any]) -> dict[str, Any]:
    """Slim down a full queue record for UI panel display."""
    return {
        "queue_id": record.get("queue_id", ""),
        "event_id": record.get("event_id", ""),
        "source": record.get("source", ""),
        "event_type": record.get("event_type", ""),
        "status": record.get("status", ""),
        "priority": record.get("priority", 100),
        "attempt_count": record.get("attempt_count", 0),
        "max_attempts": record.get("max_attempts", 3),
        "linked_frame_id": record.get("linked_frame_id", ""),
        "failure_category": record.get("failure_category", ""),
        "last_error": record.get("last_error", ""),
        "created_at": record.get("created_at", ""),
        "updated_at": record.get("updated_at", ""),
        "claimed_by": record.get("claimed_by", ""),
    }
