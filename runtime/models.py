from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedCommand:
    raw: str
    kind: str
    namespace: str | None
    action: str
    output_alias: str | None
    payload: str
    args: dict[str, str]


@dataclass(frozen=True)
class ManifestStep:
    id: str
    command: str
    parsed_command: ParsedCommand
    when: dict[str, Any] | None = None
    retry: dict[str, Any] | None = None
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Manifest:
    manifest_id: str
    name: str
    version: int
    trigger: dict
    inputs: list
    steps: list[ManifestStep]
    validations: list
    completion: dict
    raw: dict
    live_execution: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRuntime:
    step_id: str
    command: str
    kind: str
    namespace: str | None
    action: str
    output_alias: str | None
    when: dict[str, Any] | None = None
    retry: dict[str, Any] | None = None
    timeout_seconds: float | None = None
    status: str = "PENDING"
    attempts: int = 0
    max_attempts: int = 1
    started_at: str = ""
    ended_at: str = ""
    duration_ms: float = 0.0
    last_error: str = ""
    result_ref: str | None = None
    error: str = ""


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    event_type: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    type: str
    data: Any = None
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    raw: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    validation_id: str
    validation_type: str
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryItem:
    key: str
    value: Any
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryResult:
    ok: bool
    action: str
    key: str = ""
    value: Any = None
    items: list[dict[str, Any]] = field(default_factory=list)
    found: bool = False
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResult:
    ok: bool
    action: str
    output: Any = None
    raw_text: str = ""
    parsed_json: dict[str, Any] | list[Any] | None = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InspectionResult:
    ok: bool
    action: str
    frame_id: str = ""
    data: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CleanupCandidate:
    candidate_id: str
    candidate_type: str
    path: str
    frame_id: str = ""
    reason: str = ""
    protected: bool = False
    protection_reason: str = ""
    size_bytes: int = 0
    age_days: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CleanupResult:
    ok: bool
    cleanup_id: str
    dry_run: bool
    policy: dict[str, Any]
    candidates: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[dict[str, Any]] = field(default_factory=list)
    protected: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    report_path: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MaintenanceResult:
    ok: bool
    action: str
    data: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalCommandResult:
    ok: bool
    action: str
    frame_id: str = ""
    action_id: str = ""
    data: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def validation_ok(
    validation_id: str,
    validation_type: str,
    message: str = "",
    data: dict[str, Any] | None = None,
) -> ValidationResult:
    return ValidationResult(
        validation_id=validation_id,
        validation_type=validation_type,
        ok=True,
        message=message,
        data=dict(data or {}),
    )


def validation_fail(
    validation_id: str,
    validation_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> ValidationResult:
    return ValidationResult(
        validation_id=validation_id,
        validation_type=validation_type,
        ok=False,
        message=message,
        data=dict(data or {}),
    )


def llm_result_ok(
    action: str,
    output: Any,
    raw_text: str = "",
    parsed_json: dict[str, Any] | list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMResult:
    return LLMResult(
        ok=True,
        action=action,
        output=output,
        raw_text=raw_text,
        parsed_json=parsed_json,
        error="",
        metadata=dict(metadata or {}),
    )


def llm_result_error(
    action: str,
    error: str,
    raw_text: str = "",
    metadata: dict[str, Any] | None = None,
) -> LLMResult:
    return LLMResult(
        ok=False,
        action=action,
        output=None,
        raw_text=raw_text,
        parsed_json=None,
        error=error,
        metadata=dict(metadata or {}),
    )


def inspection_ok(
    action: str,
    data: Any,
    frame_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> InspectionResult:
    return InspectionResult(
        ok=True,
        action=action,
        frame_id=frame_id,
        data=data,
        error="",
        metadata=dict(metadata or {}),
    )


def inspection_error(
    action: str,
    error: str,
    frame_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> InspectionResult:
    return InspectionResult(
        ok=False,
        action=action,
        frame_id=frame_id,
        data=None,
        error=error,
        metadata=dict(metadata or {}),
    )


def maintenance_ok(
    action: str,
    data: Any,
    metadata: dict[str, Any] | None = None,
) -> MaintenanceResult:
    return MaintenanceResult(ok=True, action=action, data=data, error="", metadata=dict(metadata or {}))


def maintenance_error(
    action: str,
    error: str,
    metadata: dict[str, Any] | None = None,
) -> MaintenanceResult:
    return MaintenanceResult(ok=False, action=action, data=None, error=error, metadata=dict(metadata or {}))


def approval_command_ok(
    action: str,
    data: Any,
    frame_id: str = "",
    action_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> ApprovalCommandResult:
    return ApprovalCommandResult(
        ok=True,
        action=action,
        frame_id=frame_id,
        action_id=action_id,
        data=data,
        error="",
        metadata=dict(metadata or {}),
    )


def approval_command_error(
    action: str,
    error: str,
    frame_id: str = "",
    action_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> ApprovalCommandResult:
    return ApprovalCommandResult(
        ok=False,
        action=action,
        frame_id=frame_id,
        action_id=action_id,
        data=None,
        error=error,
        metadata=dict(metadata or {}),
    )


@dataclass
class TaskFrame:
    frame_id: str
    manifest_id: str
    state: str

    trigger: dict[str, Any]
    raw_input: str
    inputs: dict[str, Any]

    steps: list[StepRuntime]
    current_step_id: str | None

    outputs: dict[str, Any]
    evidence: list[dict[str, Any]]

    pending_actions: list[dict[str, Any]]
    executed_actions: list[dict[str, Any]]

    tool_calls: list[dict[str, Any]]
    llm_calls: list[dict[str, Any]]

    validations: list[dict[str, Any]]
    errors: list[dict[str, Any]]

    completion_gate_result: dict[str, Any] | None
    final_response: str

    audit: list[AuditEvent]

    created_at: str
    updated_at: str
    attempts: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = 1
    runtime_version: int = 1


PENDING_ACTION_STATUSES = {
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "EXECUTING",
    "EXECUTED",
    "FAILED",
}
