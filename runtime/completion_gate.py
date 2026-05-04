from __future__ import annotations

from typing import Any

from .errors import CompletionGateError
from .models import Manifest, TaskFrame
from .taskframe import add_audit_event, transition_state


def evaluate_completion(
    frame: TaskFrame,
    manifest: Manifest,
) -> dict[str, Any]:
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

    if failed_count > 0 and not runtime_errors and not failed_steps:
        return _failed_result(
            passed_count,
            failed_count,
            [],
            [],
            failed_steps,
            runtime_errors,
            message="Validation failed.",
            final_state="FAILED_VALIDATION",
        )

    if failed_count > 0 or runtime_errors or failed_steps:
        return _failed_result(
            passed_count,
            failed_count,
            [],
            [],
            failed_steps,
            runtime_errors,
        )

    pending_actions = [item for item in frame.pending_actions if item.get("status") in {"PENDING_APPROVAL", "APPROVED", "EXECUTING"}]
    pending_action_statuses = {item.get("status") for item in pending_actions}

    if pending_actions:
        if not allow_pending_approval:
            if success_pending_actions and all(
                any(item.get("output_alias") == alias for item in frame.pending_actions)
                for alias in success_pending_actions
            ):
                return _waiting_result(
                    passed_count,
                    failed_count,
                    required_state or "WAITING_FOR_EXECUTE",
                    required_state or "WAITING_FOR_EXECUTE",
                    "Required pending action exists. Waiting for execution.",
                    [],
                    [],
                    failed_steps,
                    runtime_errors,
                )
            return _failed_result(
                passed_count,
                failed_count,
                [],
                [],
                failed_steps,
                runtime_errors,
                message="Pending approval is not allowed by completion contract.",
            )
        if "PENDING_APPROVAL" in pending_action_statuses:
            return _waiting_result(
                passed_count,
                failed_count,
                "AWAITING_APPROVAL",
                "WAITING_FOR_EXECUTE",
                "Required pending action exists. Waiting for approval.",
                [],
                [],
                failed_steps,
                runtime_errors,
            )
        return _waiting_result(
            passed_count,
            failed_count,
            "APPROVED_WAITING_EXECUTION",
            "WAITING_FOR_EXECUTE",
            "Approved pending action exists. Waiting for execution.",
            [],
            [],
            failed_steps,
            runtime_errors,
        )

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
            passed_count,
            failed_count,
            [],
            missing_pending_actions,
            failed_steps,
            runtime_errors,
            missing_executed_actions=missing_executed_actions,
        )

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
                return _failed_result(
                    passed_count,
                    failed_count,
                    [output_alias],
                    [],
                    failed_steps,
                    runtime_errors,
                    message=f"Empty output is not acceptable: {output_alias}",
                )
        else:
            non_empty_required_outputs += 1

    if missing_outputs:
        return _failed_result(
            passed_count,
            failed_count,
            missing_outputs,
            [],
            failed_steps,
            runtime_errors,
            message="Required outputs are missing.",
        )

    if not success_outputs and not success_pending_actions and not success_executed_actions:
        return {
            "ok": True,
            "status": "COMPLETED_NO_DATA",
            "final_state": "COMPLETED_NO_DATA",
            "message": "Completion gate passed with no required outputs.",
            "validation_summary": {"passed": passed_count, "failed": failed_count},
            "missing_outputs": [],
            "missing_pending_actions": [],
            "missing_executed_actions": [],
            "failed_steps": failed_steps,
            "errors": runtime_errors,
        }

    if required_state and required_state not in {"COMPLETED", "COMPLETED_NO_DATA", "FAILED_COMPLETION"}:
        return _failed_result(
            passed_count,
            failed_count,
            missing_outputs,
            [],
            failed_steps,
            runtime_errors,
            message=f"Unsupported required_state: {required_state}",
        )

    if success_outputs and non_empty_required_outputs == 0 and empty_required_outputs == len(success_outputs):
        return {
            "ok": True,
            "status": required_state or "COMPLETED_NO_DATA",
            "final_state": required_state or "COMPLETED_NO_DATA",
            "message": "Completion gate passed with acceptable empty outputs.",
            "validation_summary": {"passed": passed_count, "failed": failed_count},
            "missing_outputs": [],
            "missing_pending_actions": [],
            "missing_executed_actions": [],
            "failed_steps": failed_steps,
            "errors": runtime_errors,
        }

    return {
        "ok": True,
        "status": required_state or "COMPLETED",
        "final_state": required_state or "COMPLETED",
        "message": "Completion gate passed.",
        "validation_summary": {"passed": passed_count, "failed": failed_count},
        "missing_outputs": [],
        "missing_pending_actions": [],
        "missing_executed_actions": [],
        "failed_steps": failed_steps,
        "errors": runtime_errors,
    }


def apply_completion_result(
    frame: TaskFrame,
    completion_result: dict[str, Any],
) -> None:
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
        event_type = "COMPLETION_WAITING_FOR_APPROVAL" if status == "AWAITING_APPROVAL" else "COMPLETION_APPROVED_WAITING_EXECUTION"
        add_audit_event(frame, event_type, completion_result.get("message", ""), completion_result)
    elif completion_result.get("ok"):
        add_audit_event(frame, "COMPLETION_GATE_PASSED", completion_result.get("message", ""), completion_result)
    else:
        add_audit_event(frame, "COMPLETION_GATE_FAILED", completion_result.get("message", ""), completion_result)


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
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "final_state": final_state,
        "message": message,
        "validation_summary": {"passed": passed_count, "failed": failed_count},
        "missing_outputs": missing_outputs,
        "missing_pending_actions": missing_pending_actions,
        "missing_executed_actions": [],
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
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": final_state,
        "final_state": final_state,
        "message": message,
        "validation_summary": {"passed": passed_count, "failed": failed_count},
        "missing_outputs": missing_outputs,
        "missing_pending_actions": missing_pending_actions,
        "missing_executed_actions": list(missing_executed_actions or []),
        "failed_steps": failed_steps,
        "errors": runtime_errors,
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
