from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import TaskFrameReloadError
from .manifest_loader import load_manifest_by_id
from .models import AuditEvent, Manifest, StepRuntime, TaskFrame
from .persistence import DEFAULT_RUNTIME_DATA_DIR, load_taskframe_dict
from .command_parser import parse_command


def step_runtime_from_dict(data: dict[str, Any]) -> StepRuntime:
    if not isinstance(data, dict):
        raise TaskFrameReloadError("Step runtime data must be an object.")
    command = data.get("command")
    step_id = data.get("step_id") or data.get("id")
    if not isinstance(step_id, str) or not step_id.strip():
        raise TaskFrameReloadError("Step runtime step_id must be a non-empty string.")
    kind = _string_or_default(data.get("kind"), "")
    namespace = _string_or_default(data.get("namespace"), None)
    action = _string_or_default(data.get("action"), "")
    output_alias = _string_or_default(data.get("output_alias"), None)
    if isinstance(command, str) and command.strip():
        try:
            parsed = parse_command(command)
            if not kind:
                kind = parsed.kind
            if namespace is None:
                namespace = parsed.namespace
            if not action:
                action = parsed.action
            if output_alias is None:
                output_alias = parsed.output_alias
        except Exception:
            parsed = None
    else:
        parsed = None
    if not kind:
        kind = "command"
    return StepRuntime(
        step_id=step_id,
        command=str(command or ""),
        kind=kind,
        namespace=namespace,
        action=action,
        output_alias=output_alias,
        when=data.get("when"),
        retry=data.get("retry"),
        timeout_seconds=data.get("timeout_seconds"),
        status=_string_or_default(data.get("status"), "PENDING"),
        attempts=int(data.get("attempts", 0) or 0),
        max_attempts=int(data.get("max_attempts", 1) or 1),
        started_at=_string_or_default(data.get("started_at"), ""),
        ended_at=_string_or_default(data.get("ended_at"), ""),
        duration_ms=float(data.get("duration_ms", 0.0) or 0.0),
        last_error=_string_or_default(data.get("last_error"), ""),
        result_ref=data.get("result_ref"),
        error=_string_or_default(data.get("error"), ""),
    )


def audit_event_from_dict(data: dict[str, Any]) -> AuditEvent:
    if not isinstance(data, dict):
        raise TaskFrameReloadError("Audit event data must be an object.")
    timestamp = data.get("timestamp")
    event_type = data.get("event_type")
    message = data.get("message")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise TaskFrameReloadError("Audit event timestamp must be a non-empty string.")
    if not isinstance(event_type, str) or not event_type.strip():
        raise TaskFrameReloadError("Audit event event_type must be a non-empty string.")
    if not isinstance(message, str):
        raise TaskFrameReloadError("Audit event message must be a string.")
    audit_data = data.get("data", {})
    if not isinstance(audit_data, dict):
        audit_data = {}
    return AuditEvent(timestamp=timestamp, event_type=event_type, message=message, data=audit_data)


def taskframe_from_dict(data: dict[str, Any]) -> TaskFrame:
    if not isinstance(data, dict):
        raise TaskFrameReloadError("TaskFrame data must be an object.")

    frame_id = data.get("frame_id")
    manifest_id = data.get("manifest_id")
    state = data.get("state")
    steps_raw = data.get("steps")
    created_at = data.get("created_at")
    updated_at = data.get("updated_at")
    schema_version = int(data.get("schema_version", 1) or 1)
    runtime_version = int(data.get("runtime_version", 1) or 1)

    if not isinstance(frame_id, str) or not frame_id.strip():
        raise TaskFrameReloadError("TaskFrame frame_id is required.")
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise TaskFrameReloadError("TaskFrame manifest_id is required.")
    if not isinstance(state, str) or not state.strip():
        raise TaskFrameReloadError("TaskFrame state is required.")
    if not isinstance(steps_raw, list):
        raise TaskFrameReloadError("TaskFrame steps are required.")
    if not isinstance(created_at, str) or not created_at.strip():
        raise TaskFrameReloadError("TaskFrame created_at is required.")
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise TaskFrameReloadError("TaskFrame updated_at is required.")

    steps = [step_runtime_from_dict(item) for item in steps_raw]
    audit_raw = data.get("audit", [])
    if not isinstance(audit_raw, list):
        audit_raw = []
    audit = [audit_event_from_dict(item) for item in audit_raw]

    frame = TaskFrame(
        frame_id=frame_id,
        manifest_id=manifest_id,
        state=state,
        trigger=dict(data.get("trigger", {})) if isinstance(data.get("trigger", {}), dict) else {},
        raw_input=str(data.get("raw_input", "")),
        inputs=dict(data.get("inputs", {})) if isinstance(data.get("inputs", {}), dict) else {},
        steps=steps,
        current_step_id=data.get("current_step_id"),
        outputs=dict(data.get("outputs", {})) if isinstance(data.get("outputs", {}), dict) else {},
        evidence=list(data.get("evidence", [])) if isinstance(data.get("evidence", []), list) else [],
        pending_actions=list(data.get("pending_actions", [])) if isinstance(data.get("pending_actions", []), list) else [],
        executed_actions=list(data.get("executed_actions", [])) if isinstance(data.get("executed_actions", []), list) else [],
        tool_calls=list(data.get("tool_calls", [])) if isinstance(data.get("tool_calls", []), list) else [],
        llm_calls=list(data.get("llm_calls", [])) if isinstance(data.get("llm_calls", []), list) else [],
        validations=list(data.get("validations", [])) if isinstance(data.get("validations", []), list) else [],
        errors=list(data.get("errors", [])) if isinstance(data.get("errors", []), list) else [],
        completion_gate_result=data.get("completion_gate_result"),
        final_response=str(data.get("final_response", "")),
        audit=audit,
        created_at=created_at,
        updated_at=updated_at,
        metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
        attempts=list(data.get("attempts", [])) if isinstance(data.get("attempts", []), list) else [],
        schema_version=schema_version,
        runtime_version=runtime_version,
    )
    if frame.current_step_id is None and frame.steps:
        frame.current_step_id = frame.steps[0].step_id
    return frame


def load_taskframe(
    frame_id: str,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> TaskFrame:
    try:
        data = load_taskframe_dict(frame_id, runtime_data_dir)
    except Exception as exc:
        raise TaskFrameReloadError(f"TaskFrame artifact not found: {frame_id}") from exc
    return taskframe_from_dict(data)


def load_manifest_for_frame(
    frame: TaskFrame,
    manifest_dir: str | Path = "manifests",
) -> Manifest:
    if not isinstance(frame.manifest_id, str) or not frame.manifest_id.strip():
        raise TaskFrameReloadError("TaskFrame manifest_id is required.")
    return load_manifest_by_id(frame.manifest_id, manifest_dir)


def _string_or_default(value: Any, default: str | None) -> str | None:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)
