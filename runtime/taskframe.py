from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import RuntimeSpecError
from .models import (
    AuditEvent,
    Manifest,
    StepRuntime,
    TaskFrame,
    ToolResult,
)
from .tool_result_contract import build_tool_evidence, normalize_evidence
from .retry_policy import get_step_max_attempts, normalize_retry_policy
from .timing import utc_now as timing_utc_now


TASKFRAME_STATES = {
    "CREATED",
    "VALIDATING",
    "READY",
    "RUNNING",
    "WAITING_FOR_INPUT",
    "WAITING_FOR_EXECUTE",
    "EXECUTING_PENDING",
    "VERIFYING",
    "COMPLETED",
    "COMPLETED_NO_DATA",
    "FAILED_VALIDATION",
    "FAILED_EXECUTION",
    "FAILED_COMPLETION",
    "CANCELLED",
    "EXPIRED",
}


VALID_TRANSITIONS = {
    "CREATED": {"VALIDATING", "CANCELLED"},
    "VALIDATING": {"READY", "FAILED_VALIDATION"},
    "READY": {"RUNNING", "CANCELLED"},
    "RUNNING": {
        "WAITING_FOR_INPUT",
        "WAITING_FOR_EXECUTE",
        "VERIFYING",
        "FAILED_EXECUTION",
        "CANCELLED",
    },
    "WAITING_FOR_INPUT": {"RUNNING", "CANCELLED"},
    "WAITING_FOR_EXECUTE": {"EXECUTING_PENDING", "CANCELLED", "FAILED_COMPLETION"},
    "EXECUTING_PENDING": {"VERIFYING", "FAILED_EXECUTION"},
    "VERIFYING": {
        "COMPLETED",
        "COMPLETED_NO_DATA",
        "FAILED_COMPLETION",
    },
    "FAILED_VALIDATION": set(),
    "FAILED_EXECUTION": set(),
    "FAILED_COMPLETION": set(),
    "COMPLETED": set(),
    "COMPLETED_NO_DATA": set(),
    "CANCELLED": set(),
    "EXPIRED": set(),
}


PENDING_ACTION_TRANSITIONS = {
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "FAILED"},
    "APPROVED": {"EXECUTING", "FAILED"},
    "REJECTED": set(),
    "EXECUTING": {"EXECUTED", "FAILED"},
    "EXECUTED": set(),
    "FAILED": set(),
}


STEP_STATUSES = {
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "STAGED",
    "FAILED",
    "SKIPPED",
}


class TaskFrameStateError(RuntimeSpecError):
    pass


class PendingActionStateError(RuntimeSpecError):
    pass


def utc_now() -> str:
    return timing_utc_now()


def new_frame_id() -> str:
    return f"frame_{uuid4().hex}"


def create_taskframe(
    manifest: Manifest,
    trigger: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    raw_input: str = "",
    metadata: dict[str, Any] | None = None,
) -> TaskFrame:
    timestamp = utc_now()
    steps = [
        StepRuntime(
            step_id=step.id,
            command=step.command,
            kind=step.parsed_command.kind,
            namespace=step.parsed_command.namespace,
            action=step.parsed_command.action,
            output_alias=step.parsed_command.output_alias,
            when=step.when,
            retry=normalize_retry_policy(step.retry),
            timeout_seconds=step.timeout_seconds,
            max_attempts=get_step_max_attempts(step.retry),
        )
        for step in manifest.steps
    ]
    frame = TaskFrame(
        frame_id=new_frame_id(),
        manifest_id=manifest.manifest_id,
        state="CREATED",
        trigger=dict(trigger if trigger is not None else manifest.trigger),
        raw_input=raw_input,
        inputs=dict(inputs or {}),
        steps=steps,
        current_step_id=steps[0].step_id if steps else None,
        attempts=[],
        outputs={},
        evidence=[],
        pending_actions=[],
        executed_actions=[],
        tool_calls=[],
        llm_calls=[],
        validations=[],
        errors=[],
        completion_gate_result=None,
        final_response="",
        audit=[],
        created_at=timestamp,
        updated_at=timestamp,
        metadata=dict(metadata or {}),
        schema_version=1,
        runtime_version=1,
    )
    add_audit_event(
        frame,
        "TASKFRAME_CREATED",
        "TaskFrame created from manifest.",
        {"manifest_id": manifest.manifest_id, "metadata": json_safe(frame.metadata)},
    )
    return frame


def add_audit_event(
    frame: TaskFrame,
    event_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    timestamp = utc_now()
    frame.audit.append(
        AuditEvent(
            timestamp=timestamp,
            event_type=event_type,
            message=message,
            data=dict(data or {}),
        )
    )
    frame.updated_at = timestamp


def transition_state(frame: TaskFrame, new_state: str) -> None:
    if new_state not in TASKFRAME_STATES:
        raise TaskFrameStateError(f"Unknown TaskFrame state: {new_state}")

    current_state = frame.state
    if current_state not in VALID_TRANSITIONS:
        raise TaskFrameStateError(f"Unknown current TaskFrame state: {current_state}")

    if new_state not in VALID_TRANSITIONS[current_state]:
        raise TaskFrameStateError(f"Invalid TaskFrame transition: {current_state} -> {new_state}")

    frame.state = new_state
    add_audit_event(
        frame,
        "STATE_CHANGED",
        f"{current_state} -> {new_state}",
        {"from": current_state, "to": new_state},
    )


def record_error(
    frame: TaskFrame,
    error_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    error_record = {
        "type": error_type,
        "message": message,
        "data": dict(data or {}),
        "timestamp": utc_now(),
    }
    frame.errors.append(error_record)
    add_audit_event(frame, "ERROR_RECORDED", message, error_record)


def set_output(
    frame: TaskFrame,
    output_alias: str,
    value: Any,
) -> None:
    frame.outputs[output_alias] = value
    frame.updated_at = utc_now()


def to_dict(frame: TaskFrame) -> dict[str, Any]:
    return json_safe({
        "frame_id": frame.frame_id,
        "manifest_id": frame.manifest_id,
        "state": frame.state,
        "schema_version": int(getattr(frame, "schema_version", 1) or 1),
        "runtime_version": int(getattr(frame, "runtime_version", 1) or 1),
        "trigger": dict(frame.trigger),
        "raw_input": frame.raw_input,
        "inputs": dict(frame.inputs),
        "steps": [asdict(step) for step in frame.steps],
        "current_step_id": frame.current_step_id,
        "attempts": [dict(item) for item in frame.attempts],
        "outputs": dict(frame.outputs),
        "evidence": [dict(item) for item in frame.evidence],
        "pending_actions": [dict(item) for item in frame.pending_actions],
        "executed_actions": [dict(item) for item in frame.executed_actions],
        "tool_calls": [dict(item) for item in frame.tool_calls],
        "llm_calls": [dict(item) for item in frame.llm_calls],
        "validations": [dict(item) for item in frame.validations],
        "errors": [dict(item) for item in frame.errors],
        "completion_gate_result": dict(frame.completion_gate_result) if frame.completion_gate_result is not None else None,
        "final_response": frame.final_response,
        "audit": [asdict(event) for event in frame.audit],
        "created_at": frame.created_at,
        "updated_at": frame.updated_at,
        "metadata": json_safe(frame.metadata),
    })


def build_taskframe_summary(frame: TaskFrame) -> dict[str, Any]:
    completed_steps = sum(1 for step in frame.steps if step.status == "COMPLETED")
    failed_steps = sum(1 for step in frame.steps if step.status == "FAILED")
    skipped_steps = sum(1 for step in frame.steps if step.status == "SKIPPED")
    completion_status = ""
    if isinstance(frame.completion_gate_result, dict):
        completion_status = str(frame.completion_gate_result.get("status", ""))
    return json_safe(
        {
            "frame_id": frame.frame_id,
            "manifest_id": frame.manifest_id,
            "state": frame.state,
            "created_at": frame.created_at,
            "updated_at": frame.updated_at,
            "current_step_id": frame.current_step_id,
            "step_count": len(frame.steps),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "skipped_steps": skipped_steps,
            "pending_action_count": len(frame.pending_actions),
            "executed_action_count": len(frame.executed_actions),
            "error_count": len(frame.errors),
            "validation_count": len(frame.validations),
            "validation_failed_count": sum(1 for item in frame.validations if isinstance(item, dict) and item.get("ok") is False),
            "output_keys": sorted(frame.outputs.keys()),
            "completion_status": completion_status,
            "metadata": json_safe(frame.metadata),
        }
    )


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Exception):
        return str(value)
    if hasattr(value, "__dict__"):
        return json_safe(asdict(value)) if is_dataclass(value) else str(value)
    return str(value)


def tool_result_ok(
    result_type: str,
    data: Any = None,
    evidence: object | None = None,
    raw: Any = None,
    metadata: dict[str, Any] | None = None,
) -> ToolResult:
    metadata_dict = dict(metadata or {})
    fallback = _default_tool_evidence(result_type, metadata_dict)
    return ToolResult(
        ok=True,
        type=result_type,
        data=data,
        evidence=normalize_evidence(evidence, fallback=fallback),
        error="",
        raw=raw,
        metadata=metadata_dict,
    )


def tool_result_error(
    result_type: str,
    error: str,
    raw: Any = None,
    metadata: dict[str, Any] | None = None,
) -> ToolResult:
    metadata_dict = dict(metadata or {})
    fallback = _default_tool_evidence(result_type, metadata_dict)
    return ToolResult(
        ok=False,
        type=result_type,
        data=None,
        evidence=normalize_evidence(None, fallback=fallback),
        error=error,
        raw=raw,
        metadata=metadata_dict,
    )


def _default_tool_evidence(result_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    extra = {
        key: value
        for key, value in metadata.items()
        if key not in {"tool", "mode", "source", "operation", "input_refs", "output_ref"}
    }
    return build_tool_evidence(
        tool=str(metadata.get("tool", result_type) or result_type),
        mode=str(metadata.get("mode", "local_static_check") or "local_static_check"),
        source=str(metadata.get("source", "builtin") or "builtin"),
        operation=str(metadata.get("operation", "validation") or "validation"),
        input_refs=list(metadata.get("input_refs", [])) if isinstance(metadata.get("input_refs", []), list) else [],
        output_ref=str(metadata.get("output_ref", result_type) or result_type),
        extra=extra,
    )
