from __future__ import annotations

from typing import Any

from .errors import CompletionGateError
from .models import Manifest, TaskFrame
from .taskframe import add_audit_event, transition_state

# ---------------------------------------------------------------------------
# Canonical outcome values (Spec 107)
# ---------------------------------------------------------------------------

OUTCOME_SUCCESS_WITH_DATA = "SUCCESS_WITH_DATA"
OUTCOME_SUCCESS_NO_DATA = "SUCCESS_NO_DATA"
OUTCOME_VALIDATION_FAILED = "VALIDATION_FAILED"
OUTCOME_COMPLETION_REQUIREMENT_FAILED = "COMPLETION_REQUIREMENT_FAILED"
OUTCOME_PENDING_APPROVAL = "PENDING_APPROVAL"
OUTCOME_PENDING_ACTION_REJECTED = "PENDING_ACTION_REJECTED"
OUTCOME_DRY_RUN_EXECUTED = "DRY_RUN_EXECUTED"
OUTCOME_LIVE_EXECUTION_BLOCKED = "LIVE_EXECUTION_BLOCKED"
OUTCOME_EXECUTION_FAILED = "EXECUTION_FAILED"


def evaluate_completion(
    frame: TaskFrame,
    manifest: Manifest,
) -> dict[str, Any]:
    """Evaluate whether a TaskFrame meets its completion contract.

    Returns a canonical completion result dict.  Every code path returns
    the same set of keys — callers may rely on all keys being present.
    """
    validation_results = [item for item in frame.validations if isinstance(item, dict)]
    passed_count = sum(1 for item in validation_results if item.get("ok") is True)
    failed_count = sum(1 for item in validation_results if item.get("ok") is False)

    failed_steps = [step.step_id for step in frame.steps if step.status == "FAILED"]
    runtime_errors = [error for error in frame.errors if _is_active_runtime_error(frame, error)]

    completion_spec = manifest.completion or {}
    success_outputs = list(completion_spec.get("success_outputs", []))
    required_outputs = list(completion_spec.get("required_outputs", []))
    if required_outputs:
        for output_alias in required_outputs:
            if output_alias not in success_outputs:
                success_outputs.append(output_alias)
    acceptable_empty_outputs = set(completion_spec.get("acceptable_empty_outputs", []))
    success_pending_actions = list(completion_spec.get("success_pending_actions", []))
    required_pending_actions = list(completion_spec.get("required_pending_actions", []))
    for alias in required_pending_actions:
        if alias not in success_pending_actions:
            success_pending_actions.append(alias)
    success_executed_actions = list(completion_spec.get("success_executed_actions", []))
    allow_pending_approval = bool(completion_spec.get("allow_pending_approval", False))
    required_state = str(completion_spec.get("required_state", "") or "")

    pending_action_summary = _build_pending_action_summary(frame)
    evidence_refs = [e.get("evidence_id", "") for e in frame.evidence if isinstance(e, dict) and e.get("evidence_id")]
    error_refs = [e.get("error_id", "") for e in frame.errors if isinstance(e, dict) and e.get("error_id")]

    # 1. Validation failures
    if failed_count > 0 and not runtime_errors and not failed_steps:
        return _evaluate_failed_validation(
            passed_count, failed_count, failed_steps, runtime_errors,
            success_outputs, success_pending_actions, success_executed_actions,
            pending_action_summary, evidence_refs, error_refs,
        )

    # 2. Runtime errors or failed steps (execution failures)
    if failed_count > 0 or runtime_errors or failed_steps:
        live_blocked = any(
            isinstance(e, dict) and e.get("type") in {"live_execution_blocked", "LiveExecutionBlocked"}
            for e in frame.errors
        )
        return _evaluate_failed_or_rejected_actions(
            passed_count, failed_count, [], [], failed_steps, runtime_errors,
            success_outputs, success_pending_actions, success_executed_actions,
            pending_action_summary, evidence_refs, error_refs,
            live_blocked=live_blocked,
        )

    # 3. Pending actions in flight
    pending_actions = [
        item for item in frame.pending_actions
        if item.get("status") in {"PENDING_APPROVAL", "APPROVED", "EXECUTING"}
    ]
    pending_action_statuses = {item.get("status") for item in pending_actions}

    if pending_actions:
        return _evaluate_pending_approval(
            passed_count, failed_count, pending_actions, pending_action_statuses,
            allow_pending_approval, success_pending_actions, required_state,
            failed_steps, runtime_errors,
            success_outputs, success_executed_actions,
            pending_action_summary, evidence_refs, error_refs,
        )

    # 4. Check for rejected pending actions
    rejected_actions = [
        item for item in frame.pending_actions
        if item.get("status") == "REJECTED"
    ]
    if rejected_actions and not success_executed_actions:
        return _evaluate_failed_or_rejected_actions(
            passed_count, failed_count, [], [], failed_steps, runtime_errors,
            success_outputs, success_pending_actions, success_executed_actions,
            pending_action_summary, evidence_refs, error_refs,
            rejected=True,
        )

    # 5. Required pending/executed action aliases
    missing_pending_actions: list[str] = []
    for alias in success_pending_actions:
        if not any(item.get("output_alias") == alias for item in frame.pending_actions):
            missing_pending_actions.append(alias)

    executed_aliases = {
        item.get("output_alias")
        for item in frame.executed_actions
        if item.get("status") == "EXECUTED"
    }
    missing_executed_actions: list[str] = []
    for alias in success_executed_actions:
        if alias not in executed_aliases:
            missing_executed_actions.append(alias)

    if missing_pending_actions or missing_executed_actions:
        return _failed_result(
            passed_count, failed_count,
            [], missing_pending_actions, failed_steps, runtime_errors,
            missing_executed_actions=missing_executed_actions,
            outcome=OUTCOME_COMPLETION_REQUIREMENT_FAILED,
            reason_code="MISSING_PENDING_OR_EXECUTED_ACTIONS",
            required_outputs=success_outputs,
            required_pending_actions=success_pending_actions,
            required_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
        )

    # 6. Determine if this was a dry-run executed flow
    dry_run_executed = bool(success_executed_actions) and all(
        any(
            item.get("output_alias") == alias and item.get("status") == "EXECUTED"
            for item in frame.executed_actions
        )
        for alias in success_executed_actions
    )

    # 7. Evaluate success outputs
    missing_outputs: list[str] = []
    non_empty_required_outputs = 0
    empty_required_outputs = 0

    for output_alias in success_outputs:
        if output_alias not in frame.outputs:
            missing_outputs.append(output_alias)
            continue
        if _is_empty_value(frame.outputs[output_alias]):
            if output_alias in acceptable_empty_outputs:
                empty_required_outputs += 1
            else:
                return _evaluate_success_outputs(
                    passed_count, failed_count,
                    missing_outputs=[output_alias],
                    failed_steps=failed_steps,
                    runtime_errors=runtime_errors,
                    message=f"Empty output is not acceptable: {output_alias}",
                    success_outputs=success_outputs,
                    success_pending_actions=success_pending_actions,
                    success_executed_actions=success_executed_actions,
                    pending_action_summary=pending_action_summary,
                    evidence_refs=evidence_refs,
                    error_refs=error_refs,
                )
        else:
            non_empty_required_outputs += 1

    if missing_outputs:
        return _evaluate_success_outputs(
            passed_count, failed_count,
            missing_outputs=missing_outputs,
            failed_steps=failed_steps,
            runtime_errors=runtime_errors,
            message="Required outputs are missing.",
            success_outputs=success_outputs,
            success_pending_actions=success_pending_actions,
            success_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
        )

    # 8. No success criteria defined — acceptable no-data
    if not success_outputs and not success_pending_actions and not success_executed_actions:
        return _evaluate_acceptable_empty_outputs(
            passed_count, failed_count,
            required_state=required_state,
            failed_steps=failed_steps,
            runtime_errors=runtime_errors,
            success_outputs=success_outputs,
            success_pending_actions=success_pending_actions,
            success_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
            message="Completion gate passed with no required outputs.",
        )

    if required_state and required_state not in {"COMPLETED", "COMPLETED_NO_DATA", "FAILED_COMPLETION"}:
        return _failed_result(
            passed_count, failed_count,
            [], [], failed_steps, runtime_errors,
            message=f"Unsupported required_state: {required_state}",
            outcome=OUTCOME_COMPLETION_REQUIREMENT_FAILED,
            reason_code="INVALID_REQUIRED_STATE",
            required_outputs=success_outputs,
            required_pending_actions=success_pending_actions,
            required_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
        )

    # 9. All outputs are acceptable-empty
    if success_outputs and non_empty_required_outputs == 0 and empty_required_outputs == len(success_outputs):
        return _evaluate_acceptable_empty_outputs(
            passed_count, failed_count,
            required_state=required_state,
            failed_steps=failed_steps,
            runtime_errors=runtime_errors,
            success_outputs=success_outputs,
            success_pending_actions=success_pending_actions,
            success_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
            message="Completion gate passed with acceptable empty outputs.",
        )

    # 10. Success with data
    outcome = OUTCOME_DRY_RUN_EXECUTED if dry_run_executed else OUTCOME_SUCCESS_WITH_DATA
    reason_code = "DRY_RUN_EXECUTED" if dry_run_executed else "SUCCESS"
    return {
        "ok": True,
        "status": required_state or "COMPLETED",
        "outcome": outcome,
        "final_state": required_state or "COMPLETED",
        "message": "Completion gate passed.",
        "reason_code": reason_code,
        "required_outputs": success_outputs,
        "missing_outputs": [],
        "required_pending_actions": success_pending_actions,
        "missing_pending_actions": [],
        "required_executed_actions": success_executed_actions,
        "missing_executed_actions": [],
        "validation_summary": {"passed": passed_count, "failed": failed_count, "warnings": 0},
        "pending_action_summary": pending_action_summary,
        "evidence_refs": evidence_refs,
        "error_refs": error_refs,
        "metadata": {},
        # Legacy compat fields
        "failed_steps": failed_steps,
        "errors": runtime_errors,
    }


def apply_completion_result(
    frame: TaskFrame,
    completion_result: dict[str, Any],
) -> None:
    """Write canonical completion result to frame, transition state, and emit audit event."""
    if "final_state" not in completion_result:
        raise CompletionGateError("Completion result missing final_state.")

    frame.completion_gate_result = completion_result
    final_state = completion_result["final_state"]
    status = completion_result.get("status", "")

    if final_state != frame.state:
        from .taskframe import TASKFRAME_STATES, VALID_TRANSITIONS

        if frame.state not in VALID_TRANSITIONS:
            raise CompletionGateError(f"Unknown frame state: {frame.state}")
        if final_state not in TASKFRAME_STATES:
            raise CompletionGateError(f"Unknown final state: {final_state}")
        if final_state in VALID_TRANSITIONS[frame.state]:
            transition_state(frame, final_state)
        elif final_state in {"FAILED_COMPLETION", "FAILED_VALIDATION"}:
            frame.state = final_state
        else:
            raise CompletionGateError(f"Invalid completion transition: {frame.state} -> {final_state}")

    if status in {"AWAITING_APPROVAL", "APPROVED_WAITING_EXECUTION"}:
        add_audit_event(frame, "COMPLETION_GATE_WAITING", completion_result.get("message", ""), completion_result)
    elif completion_result.get("ok"):
        add_audit_event(frame, "COMPLETION_GATE_PASSED", completion_result.get("message", ""), completion_result)
    else:
        add_audit_event(frame, "COMPLETION_GATE_FAILED", completion_result.get("message", ""), completion_result)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _evaluate_failed_validation(
    passed_count: int,
    failed_count: int,
    failed_steps: list[str],
    runtime_errors: list[dict],
    required_outputs: list[str],
    required_pending_actions: list[str],
    required_executed_actions: list[str],
    pending_action_summary: dict,
    evidence_refs: list[str],
    error_refs: list[str],
) -> dict[str, Any]:
    return _failed_result(
        passed_count, failed_count,
        missing_outputs=[], missing_pending_actions=[],
        failed_steps=failed_steps, runtime_errors=runtime_errors,
        message="Validation failed.",
        final_state="FAILED_VALIDATION",
        outcome=OUTCOME_VALIDATION_FAILED,
        reason_code="VALIDATION_FAILED",
        required_outputs=required_outputs,
        required_pending_actions=required_pending_actions,
        required_executed_actions=required_executed_actions,
        pending_action_summary=pending_action_summary,
        evidence_refs=evidence_refs,
        error_refs=error_refs,
    )


def _evaluate_pending_approval(
    passed_count: int,
    failed_count: int,
    pending_actions: list[dict],
    pending_action_statuses: set,
    allow_pending_approval: bool,
    success_pending_actions: list[str],
    required_state: str,
    failed_steps: list[str],
    runtime_errors: list[dict],
    success_outputs: list[str],
    success_executed_actions: list[str],
    pending_action_summary: dict,
    evidence_refs: list[str],
    error_refs: list[str],
) -> dict[str, Any]:
    if not allow_pending_approval:
        if success_pending_actions and all(
            any(item.get("output_alias") == alias for item in pending_actions)
            for alias in success_pending_actions
        ):
            return _waiting_result(
                passed_count, failed_count,
                status=required_state or "WAITING_FOR_EXECUTE",
                final_state=required_state or "WAITING_FOR_EXECUTE",
                message="Required pending action exists. Waiting for execution.",
                missing_outputs=[], missing_pending_actions=[],
                failed_steps=failed_steps, runtime_errors=runtime_errors,
                outcome=OUTCOME_PENDING_APPROVAL,
                reason_code="PENDING_APPROVAL",
                required_outputs=success_outputs,
                required_pending_actions=success_pending_actions,
                required_executed_actions=success_executed_actions,
                pending_action_summary=pending_action_summary,
                evidence_refs=evidence_refs,
                error_refs=error_refs,
            )
        return _failed_result(
            passed_count, failed_count,
            missing_outputs=[], missing_pending_actions=[],
            failed_steps=failed_steps, runtime_errors=runtime_errors,
            message="Pending approval is not allowed by completion contract.",
            outcome=OUTCOME_COMPLETION_REQUIREMENT_FAILED,
            reason_code="UNEXPECTED_PENDING_ACTION",
            required_outputs=success_outputs,
            required_pending_actions=success_pending_actions,
            required_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
        )

    if "PENDING_APPROVAL" in pending_action_statuses:
        return _waiting_result(
            passed_count, failed_count,
            status="AWAITING_APPROVAL",
            final_state="WAITING_FOR_EXECUTE",
            message="Required pending action exists. Waiting for approval.",
            missing_outputs=[], missing_pending_actions=[],
            failed_steps=failed_steps, runtime_errors=runtime_errors,
            outcome=OUTCOME_PENDING_APPROVAL,
            reason_code="PENDING_APPROVAL",
            required_outputs=success_outputs,
            required_pending_actions=success_pending_actions,
            required_executed_actions=success_executed_actions,
            pending_action_summary=pending_action_summary,
            evidence_refs=evidence_refs,
            error_refs=error_refs,
        )

    return _waiting_result(
        passed_count, failed_count,
        status="APPROVED_WAITING_EXECUTION",
        final_state="WAITING_FOR_EXECUTE",
        message="Approved pending action exists. Waiting for execution.",
        missing_outputs=[], missing_pending_actions=[],
        failed_steps=failed_steps, runtime_errors=runtime_errors,
        outcome=OUTCOME_PENDING_APPROVAL,
        reason_code="APPROVED_WAITING_EXECUTION",
        required_outputs=success_outputs,
        required_pending_actions=success_pending_actions,
        required_executed_actions=success_executed_actions,
        pending_action_summary=pending_action_summary,
        evidence_refs=evidence_refs,
        error_refs=error_refs,
    )


def _evaluate_success_outputs(
    passed_count: int,
    failed_count: int,
    missing_outputs: list[str],
    failed_steps: list[str],
    runtime_errors: list[dict],
    message: str,
    success_outputs: list[str],
    success_pending_actions: list[str],
    success_executed_actions: list[str],
    pending_action_summary: dict,
    evidence_refs: list[str],
    error_refs: list[str],
) -> dict[str, Any]:
    return _failed_result(
        passed_count, failed_count,
        missing_outputs=missing_outputs,
        missing_pending_actions=[],
        failed_steps=failed_steps,
        runtime_errors=runtime_errors,
        message=message,
        outcome=OUTCOME_COMPLETION_REQUIREMENT_FAILED,
        reason_code="MISSING_OUTPUTS",
        required_outputs=success_outputs,
        required_pending_actions=success_pending_actions,
        required_executed_actions=success_executed_actions,
        pending_action_summary=pending_action_summary,
        evidence_refs=evidence_refs,
        error_refs=error_refs,
    )


def _evaluate_acceptable_empty_outputs(
    passed_count: int,
    failed_count: int,
    required_state: str,
    failed_steps: list[str],
    runtime_errors: list[dict],
    success_outputs: list[str],
    success_pending_actions: list[str],
    success_executed_actions: list[str],
    pending_action_summary: dict,
    evidence_refs: list[str],
    error_refs: list[str],
    message: str = "Completion gate passed with acceptable empty outputs.",
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": required_state or "COMPLETED_NO_DATA",
        "outcome": OUTCOME_SUCCESS_NO_DATA,
        "final_state": required_state or "COMPLETED_NO_DATA",
        "message": message,
        "reason_code": "SUCCESS_NO_DATA",
        "required_outputs": success_outputs,
        "missing_outputs": [],
        "required_pending_actions": success_pending_actions,
        "missing_pending_actions": [],
        "required_executed_actions": success_executed_actions,
        "missing_executed_actions": [],
        "validation_summary": {"passed": passed_count, "failed": failed_count, "warnings": 0},
        "pending_action_summary": pending_action_summary,
        "evidence_refs": evidence_refs,
        "error_refs": error_refs,
        "metadata": {},
        "failed_steps": failed_steps,
        "errors": runtime_errors,
    }


def _evaluate_executed_actions(
    passed_count: int,
    failed_count: int,
    missing_executed_actions: list[str],
    failed_steps: list[str],
    runtime_errors: list[dict],
    success_outputs: list[str],
    success_pending_actions: list[str],
    success_executed_actions: list[str],
    pending_action_summary: dict,
    evidence_refs: list[str],
    error_refs: list[str],
) -> dict[str, Any]:
    return _failed_result(
        passed_count, failed_count,
        missing_outputs=[],
        missing_pending_actions=[],
        failed_steps=failed_steps,
        runtime_errors=runtime_errors,
        missing_executed_actions=missing_executed_actions,
        outcome=OUTCOME_COMPLETION_REQUIREMENT_FAILED,
        reason_code="MISSING_EXECUTED_ACTIONS",
        required_outputs=success_outputs,
        required_pending_actions=success_pending_actions,
        required_executed_actions=success_executed_actions,
        pending_action_summary=pending_action_summary,
        evidence_refs=evidence_refs,
        error_refs=error_refs,
    )


def _evaluate_failed_or_rejected_actions(
    passed_count: int,
    failed_count: int,
    missing_outputs: list[str],
    missing_pending_actions: list[str],
    failed_steps: list[str],
    runtime_errors: list[dict],
    required_outputs: list[str],
    required_pending_actions: list[str],
    required_executed_actions: list[str],
    pending_action_summary: dict,
    evidence_refs: list[str],
    error_refs: list[str],
    rejected: bool = False,
    live_blocked: bool = False,
) -> dict[str, Any]:
    if live_blocked:
        outcome = OUTCOME_LIVE_EXECUTION_BLOCKED
        reason_code = "LIVE_BLOCKED"
        status = "LIVE_BLOCKED"
        final_state = "FAILED_EXECUTION"
        message = "Live execution is blocked. No side effect was executed."
    elif rejected:
        outcome = OUTCOME_PENDING_ACTION_REJECTED
        reason_code = "REJECTED"
        status = "FAILED_COMPLETION"
        final_state = "FAILED_COMPLETION"
        message = "Pending action was rejected."
    else:
        outcome = OUTCOME_EXECUTION_FAILED
        reason_code = "EXECUTION_FAILED"
        status = "FAILED_COMPLETION"
        final_state = "FAILED_COMPLETION"
        message = "Completion gate failed."

    return {
        "ok": False,
        "status": status,
        "outcome": outcome,
        "final_state": final_state,
        "message": message,
        "reason_code": reason_code,
        "required_outputs": required_outputs,
        "missing_outputs": missing_outputs,
        "required_pending_actions": required_pending_actions,
        "missing_pending_actions": missing_pending_actions,
        "required_executed_actions": required_executed_actions,
        "missing_executed_actions": [],
        "validation_summary": {"passed": passed_count, "failed": failed_count, "warnings": 0},
        "pending_action_summary": pending_action_summary,
        "evidence_refs": evidence_refs,
        "error_refs": error_refs,
        "metadata": {},
        "failed_steps": failed_steps,
        "errors": runtime_errors,
    }


# ---------------------------------------------------------------------------
# Internal result builders
# ---------------------------------------------------------------------------

def _waiting_result(
    passed_count: int,
    failed_count: int,
    status: str,
    final_state: str,
    message: str,
    missing_outputs: list[str],
    missing_pending_actions: list[str],
    failed_steps: list[str],
    runtime_errors: list[dict[str, Any]],
    outcome: str = OUTCOME_PENDING_APPROVAL,
    reason_code: str = "PENDING_APPROVAL",
    required_outputs: list[str] | None = None,
    required_pending_actions: list[str] | None = None,
    required_executed_actions: list[str] | None = None,
    pending_action_summary: dict | None = None,
    evidence_refs: list[str] | None = None,
    error_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "outcome": outcome,
        "final_state": final_state,
        "message": message,
        "reason_code": reason_code,
        "required_outputs": list(required_outputs or []),
        "missing_outputs": missing_outputs,
        "required_pending_actions": list(required_pending_actions or []),
        "missing_pending_actions": missing_pending_actions,
        "required_executed_actions": list(required_executed_actions or []),
        "missing_executed_actions": [],
        "validation_summary": {"passed": passed_count, "failed": failed_count, "warnings": 0},
        "pending_action_summary": pending_action_summary or _empty_pending_action_summary(),
        "evidence_refs": list(evidence_refs or []),
        "error_refs": list(error_refs or []),
        "metadata": {},
        "failed_steps": failed_steps,
        "errors": runtime_errors,
    }


def _failed_result(
    passed_count: int,
    failed_count: int,
    missing_outputs: list[str],
    missing_pending_actions: list[str],
    failed_steps: list[str],
    runtime_errors: list[dict[str, Any]],
    message: str = "Completion gate failed.",
    missing_executed_actions: list[str] | None = None,
    final_state: str = "FAILED_COMPLETION",
    outcome: str = OUTCOME_COMPLETION_REQUIREMENT_FAILED,
    reason_code: str = "COMPLETION_GATE_FAILED",
    required_outputs: list[str] | None = None,
    required_pending_actions: list[str] | None = None,
    required_executed_actions: list[str] | None = None,
    pending_action_summary: dict | None = None,
    evidence_refs: list[str] | None = None,
    error_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": final_state,
        "outcome": outcome,
        "final_state": final_state,
        "message": message,
        "reason_code": reason_code,
        "required_outputs": list(required_outputs or []),
        "missing_outputs": missing_outputs,
        "required_pending_actions": list(required_pending_actions or []),
        "missing_pending_actions": missing_pending_actions,
        "required_executed_actions": list(required_executed_actions or []),
        "missing_executed_actions": list(missing_executed_actions or []),
        "validation_summary": {"passed": passed_count, "failed": failed_count, "warnings": 0},
        "pending_action_summary": pending_action_summary or _empty_pending_action_summary(),
        "evidence_refs": list(evidence_refs or []),
        "error_refs": list(error_refs or []),
        "metadata": {},
        "failed_steps": failed_steps,
        "errors": runtime_errors,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pending_action_summary(frame: TaskFrame) -> dict[str, int]:
    summary = _empty_pending_action_summary()
    for action in frame.pending_actions:
        status = str(action.get("status", "")).upper()
        if status == "PENDING_APPROVAL":
            summary["pending_approval"] += 1
        elif status == "APPROVED":
            summary["approved"] += 1
        elif status == "EXECUTING":
            summary["executing"] += 1
        elif status == "REJECTED":
            summary["rejected"] += 1
        elif status == "FAILED":
            summary["failed"] += 1
    for action in frame.executed_actions:
        status = str(action.get("status", "")).upper()
        if status == "EXECUTED":
            summary["executed"] += 1
    return summary


def _empty_pending_action_summary() -> dict[str, int]:
    return {
        "pending_approval": 0,
        "approved": 0,
        "executing": 0,
        "executed": 0,
        "rejected": 0,
        "failed": 0,
    }


def _is_active_runtime_error(frame: TaskFrame, error: dict[str, Any]) -> bool:
    data = error.get("data", {}) if isinstance(error, dict) else {}
    step_id = data.get("step_id")
    if not step_id:
        return True
    for step in frame.steps:
        if step.step_id == step_id:
            return step.status == "FAILED"
    return True


def _is_empty_value(value: Any) -> bool:
    return value in (None, "", [], {})
