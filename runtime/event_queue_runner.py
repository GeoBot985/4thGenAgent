"""Spec 137 — Durable Event Queue Runner.

Processes queued events into TaskFrames using the existing intake pipeline.
Always runs in dry-run mode; live side effects are never executed here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .event_queue_contract import (
    FAILURE_RUNTIME_EXCEPTION,
    classify_failure_from_status,
)
from .taskframe import utc_now


def _classify_event_failure(result: dict[str, Any]) -> str:
    """Derive failure category from an intake_and_run_event result."""
    status = str(result.get("status", "") or "")
    errors = list(result.get("errors") or [])
    error_text = " ".join(str(e) for e in errors).upper()

    if "POLICY_BLOCKED" in error_text or "LIVE_EFFECT" in error_text:
        from .event_queue_contract import FAILURE_POLICY_BLOCKED
        return FAILURE_POLICY_BLOCKED
    if "LLM" in error_text and ("UNAVAILABLE" in error_text or "TIMEOUT" in error_text):
        from .event_queue_contract import FAILURE_LLM_TRANSIENT_FAILURE
        return FAILURE_LLM_TRANSIENT_FAILURE
    if "TIMEOUT" in error_text or "TRANSIENT" in error_text:
        from .event_queue_contract import FAILURE_TRANSIENT_TOOL_FAILURE
        return FAILURE_TRANSIENT_TOOL_FAILURE

    return classify_failure_from_status(status)


def _write_queue_audit_event(
    queue_id: str,
    action: str,
    detail: dict[str, Any],
    runtime_data_dir: str | Path,
) -> None:
    """Append a lightweight audit entry for a queue lifecycle event."""
    from .event_store import append_event
    from .events import create_event

    payload = {"queue_id": queue_id, "action": action, **detail}
    event = {
        "event_id": f"qaudit_{queue_id}_{action}_{utc_now()}",
        "source": "queue_runner",
        "event_type": f"queue.{action}",
        "payload": payload,
        "received_at": utc_now(),
    }
    try:
        append_event(event, runtime_data_dir)
    except Exception:
        pass


def process_next_queued_event(
    runtime_data_dir: str | Path = "runtime_data",
    worker_id: str = "local",
) -> dict[str, Any]:
    """Claim and process one PENDING queue item into a TaskFrame.

    Processing always uses dry-run mode; live side effects are blocked.
    Returns a result dict with ok, queue_id, status, and optional frame_id/error.
    """
    from .event_queue import (
        claim_next_event,
        mark_event_completed,
        mark_event_failed,
        mark_event_processing,
    )
    from .event_store import intake_and_run_event

    claimed = claim_next_event(worker_id, runtime_data_dir)
    if not claimed.get("ok"):
        return claimed

    queue_id = str(claimed["queue_id"])

    processing = mark_event_processing(queue_id, runtime_data_dir)
    if not processing.get("ok"):
        return {"ok": False, "queue_id": queue_id, "error": processing.get("error", "mark_processing failed")}

    # Build a synthetic event so the intake pipeline does not see a duplicate event_id
    event_data: dict[str, Any] = {
        "event_id": f"dq_{queue_id}",
        "source": str(claimed.get("source", "") or ""),
        "event_type": str(claimed.get("event_type", "") or ""),
        "payload": dict(claimed.get("payload_json") or {}),
        "received_at": utc_now(),
        "metadata": {
            "queue_id": queue_id,
            "original_event_id": str(claimed.get("event_id", "") or ""),
        },
    }

    try:
        result = intake_and_run_event(event_data, runtime_data_dir=runtime_data_dir)
    except Exception as exc:
        error = {"message": str(exc), "category": FAILURE_RUNTIME_EXCEPTION}
        mark_event_failed(queue_id, error, runtime_data_dir)
        _write_queue_audit_event(queue_id, "failed_exception", {"error": str(exc)}, runtime_data_dir)
        return {"ok": False, "queue_id": queue_id, "status": "FAILED", "error": error}

    if result.get("ok") or result.get("status") in ("FRAME_CREATED", "COMPLETED", "DUPLICATE_EVENT"):
        frame_id = str(result.get("frame_id", "") or "")
        mark_event_completed(queue_id, frame_id, runtime_data_dir)
        _write_queue_audit_event(queue_id, "completed", {"frame_id": frame_id}, runtime_data_dir)
        return {
            "ok": True,
            "queue_id": queue_id,
            "frame_id": frame_id,
            "status": "COMPLETED",
            "intake_status": result.get("status"),
        }

    errors = list(result.get("errors") or [])
    failure_category = _classify_event_failure(result)
    error = {
        "message": str(errors[0]) if errors else str(result.get("status", "FAILED")),
        "category": failure_category,
    }
    failed = mark_event_failed(queue_id, error, runtime_data_dir)
    _write_queue_audit_event(queue_id, "failed", error, runtime_data_dir)
    return {
        "ok": False,
        "queue_id": queue_id,
        "status": failed.get("status", "FAILED"),
        "failure_category": failure_category,
        "error": error,
        "intake_status": result.get("status"),
    }


def process_queued_events(
    limit: int = 10,
    runtime_data_dir: str | Path = "runtime_data",
    worker_id: str = "local",
) -> dict[str, Any]:
    """Process up to `limit` PENDING queue items sequentially.

    Stops early when no more PENDING items are available.
    """
    results: list[dict[str, Any]] = []
    for _ in range(int(limit)):
        result = process_next_queued_event(runtime_data_dir=runtime_data_dir, worker_id=worker_id)
        results.append(result)
        if result.get("no_pending_event"):
            break

    completed = sum(1 for r in results if r.get("status") == "COMPLETED" or r.get("ok"))
    failed = sum(1 for r in results if not r.get("ok") and not r.get("no_pending_event"))
    no_work = bool(results and results[-1].get("no_pending_event"))

    return {
        "ok": True,
        "processed": len(results),
        "completed": completed,
        "failed": failed,
        "no_more_pending": no_work,
        "results": results,
    }
