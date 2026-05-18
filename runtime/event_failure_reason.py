"""Spec 108 — Event failure reason derivation.

Maps event record state and optional linked TaskFrame state
to a structured failure reason for operator inspection.
"""
from __future__ import annotations

from typing import Any, Literal

FailureSource = Literal["event_route", "runtime", "taskframe", "completion_gate", "unknown"]

# ---------------------------------------------------------------------------
# Failure codes
# ---------------------------------------------------------------------------

FC_ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
FC_MANIFEST_NOT_FOUND = "MANIFEST_NOT_FOUND"
FC_EVENT_VALIDATION_FAILED = "EVENT_VALIDATION_FAILED"
FC_TASKFRAME_CREATION_FAILED = "TASKFRAME_CREATION_FAILED"
FC_RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
FC_FRAME_FAILED_VALIDATION = "FRAME_FAILED_VALIDATION"
FC_FRAME_FAILED_EXECUTION = "FRAME_FAILED_EXECUTION"
FC_FRAME_FAILED_COMPLETION = "FRAME_FAILED_COMPLETION"
FC_UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

# Map queue/legacy event statuses → failure codes
_STATUS_TO_CODE: dict[str, tuple[str, str, FailureSource]] = {
    # (code, human reason, source)
    "INVALID_EVENT": (FC_EVENT_VALIDATION_FAILED, "Event record is missing required fields.", "event_route"),
    "NO_ROUTE": (FC_ROUTE_NOT_FOUND, "No event route matched this source and event type.", "event_route"),
    "ROUTE_NOT_FOUND": (FC_ROUTE_NOT_FOUND, "No event route matched this source and event type.", "event_route"),
    "ROUTE_MAPPING_FAILED": (FC_RUNTIME_EXCEPTION, "Event fields could not be mapped to manifest inputs.", "event_route"),
    "MANIFEST_NOT_FOUND": (FC_MANIFEST_NOT_FOUND, "The target manifest could not be found.", "event_route"),
    "FAILED": (FC_RUNTIME_EXCEPTION, "Runtime exception during event processing.", "runtime"),
    "FAILED_EXECUTION": (FC_FRAME_FAILED_EXECUTION, "TaskFrame execution failed.", "taskframe"),
    "FAILED_VALIDATION": (FC_FRAME_FAILED_VALIDATION, "TaskFrame validation failed.", "taskframe"),
    "FAILED_COMPLETION": (FC_FRAME_FAILED_COMPLETION, "TaskFrame completion gate failed.", "completion_gate"),
    "REPLAY_FAILED": (FC_RUNTIME_EXCEPTION, "Replay attempt failed.", "runtime"),
}

# Map TaskFrame terminal states → failure codes
_FRAME_STATE_TO_CODE: dict[str, tuple[str, str, FailureSource]] = {
    "FAILED_VALIDATION": (FC_FRAME_FAILED_VALIDATION, "Validation step failed.", "taskframe"),
    "FAILED_EXECUTION": (FC_FRAME_FAILED_EXECUTION, "Execution step failed.", "taskframe"),
    "FAILED_COMPLETION": (FC_FRAME_FAILED_COMPLETION, "Completion gate was not satisfied.", "completion_gate"),
    "CANCELLED": (FC_RUNTIME_EXCEPTION, "TaskFrame was cancelled.", "taskframe"),
    "EXPIRED": (FC_RUNTIME_EXCEPTION, "TaskFrame execution timed out.", "taskframe"),
}


def derive_event_failure_reason(
    event_record: dict[str, Any],
    frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive structured failure reason for an event record.

    Returns:
        {
            "failure_code": str,
            "failure_reason": str,
            "source": FailureSource,
        }
    """
    status = str(event_record.get("status", "") or "")
    errors = list(event_record.get("errors") or [])

    # Try frame state first (most specific)
    if frame is not None:
        frame_state = str(frame.get("state", "") or "")
        if frame_state in _FRAME_STATE_TO_CODE:
            code, reason, source = _FRAME_STATE_TO_CODE[frame_state]
            # Enrich with first frame error message if available
            frame_errors = [e.get("message", "") for e in (frame.get("errors") or []) if isinstance(e, dict)]
            if frame_errors:
                reason = f"{reason} {frame_errors[0]}".strip()
            return {"failure_code": code, "failure_reason": reason, "source": source}

        # Frame completion gate result
        cgr = frame.get("completion_gate_result") or {}
        cgr_outcome = str(cgr.get("outcome", "") or "")
        if cgr_outcome == "VALIDATION_FAILED":
            return {
                "failure_code": FC_FRAME_FAILED_VALIDATION,
                "failure_reason": cgr.get("message", "Validation failed."),
                "source": "taskframe",
            }
        if cgr_outcome in {"COMPLETION_REQUIREMENT_FAILED", "PENDING_ACTION_REJECTED"}:
            return {
                "failure_code": FC_FRAME_FAILED_COMPLETION,
                "failure_reason": cgr.get("message", "Completion gate failed."),
                "source": "completion_gate",
            }
        if cgr_outcome == "EXECUTION_FAILED":
            return {
                "failure_code": FC_FRAME_FAILED_EXECUTION,
                "failure_reason": cgr.get("message", "Execution failed."),
                "source": "taskframe",
            }

    # Try event status mapping
    if status in _STATUS_TO_CODE:
        code, reason, source = _STATUS_TO_CODE[status]
        # Enrich with first error message if available
        if errors:
            reason = f"{reason} {errors[0]}".strip()
        return {"failure_code": code, "failure_reason": reason, "source": source}

    # No failure (success or unknown)
    if not status.startswith("FAILED") and status not in {
        "INVALID_EVENT", "NO_ROUTE", "ROUTE_NOT_FOUND", "ROUTE_MAPPING_FAILED",
        "MANIFEST_NOT_FOUND", "REPLAY_FAILED",
    }:
        return {"failure_code": "", "failure_reason": "", "source": "unknown"}

    return {
        "failure_code": FC_UNKNOWN_FAILURE,
        "failure_reason": errors[0] if errors else "Unknown failure.",
        "source": "unknown",
    }
