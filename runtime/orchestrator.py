from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .approval import approve_action, reject_action
from .artifact_cleanup import ArtifactCleaner
from .cleanup_commands import CleanupCommandRunner
from .conditions import evaluate_condition_with_trace
from .completion_gate import apply_completion_result, evaluate_completion
from .approval_commands import ApprovalCommandRunner
from .errors import ConditionError, MemoryCommandError, PendingActionError, ToolExecutionBlocked
from .errors import LiveExecutionBlocked
from .inspection import RunInspector
from .inspection_commands import InspectionCommandRunner
from .llm_adapter import BaseLLMAdapter, FakeLLMAdapter
from .llm_commands import LLMCommandRunner
from .memory_commands import MemoryCommandRunner
from .memory_store import MemoryStore
from .maintenance import MaintenanceCommandRunner
from .models import Manifest, TaskFrame, validation_fail, validation_ok
from .pending_actions import get_pending_action, list_pending_actions
from .retry_policy import classify_error, is_retryable_error, normalize_retry_policy, should_retry_step, sleep_before_retry
from .taskframe import add_audit_event, create_taskframe, record_error, transition_state, utc_now
from .timing import build_timing_record, duration_ms, monotonic_now, timeout_exceeded
from .tool_runner import ToolRunner
from .validation import run_manifest_validations, run_validation_step


CUSTOM_VALIDATION_STEP_KINDS = {
    "validate_required_inputs",
}


class Orchestrator:
    def __init__(
        self,
        memory_store: MemoryStore | None = None,
        llm_adapter: BaseLLMAdapter | None = None,
        inspector: RunInspector | None = None,
        runtime_data_dir: str | Path = "runtime_data",
        manifest_dir: str | Path = "manifests",
    ):
        self.memory_store = memory_store or MemoryStore()
        self.llm_adapter = llm_adapter or FakeLLMAdapter()
        self.inspector = inspector or RunInspector()
        self.runtime_data_dir = Path(runtime_data_dir)
        self.manifest_dir = Path(manifest_dir)

    def create_frame_from_manifest(
        self,
        manifest: Manifest,
        trigger: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        raw_input: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TaskFrame:
        frame = create_taskframe(
            manifest=manifest,
            trigger=trigger,
            inputs=inputs,
            raw_input=raw_input,
            metadata=metadata,
        )
        add_audit_event(
            frame,
            "ORCHESTRATOR_FRAME_CREATED",
            "Orchestrator created TaskFrame from manifest.",
            {"manifest_id": manifest.manifest_id},
        )
        return frame

    def prepare_frame(self, frame: TaskFrame) -> TaskFrame:
        if frame.state != "CREATED":
            raise ValueError("TaskFrame can only be prepared from CREATED state.")

        transition_state(frame, "VALIDATING")
        transition_state(frame, "READY")
        add_audit_event(frame, "FRAME_READY", "TaskFrame is ready for execution.")
        return frame

    def run_next_step(self, frame: TaskFrame, manifest: Manifest, dry_run: bool = True) -> TaskFrame:
        if frame.state not in {"READY", "RUNNING", "WAITING_FOR_EXECUTE"}:
            raise ValueError("TaskFrame must be READY, RUNNING, or WAITING_FOR_EXECUTE to run a step.")

        if frame.state == "READY":
            transition_state(frame, "RUNNING")

        pending_index = self._first_pending_step_index(frame)
        if pending_index is None:
            if frame.state == "RUNNING":
                transition_state(frame, "VERIFYING")
            return frame

        step = frame.steps[pending_index]
        if step.when is not None:
            try:
                trace = evaluate_condition_with_trace(frame, step.when)
                should_run = trace["ok"]
            except ConditionError as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                record_error(
                    frame,
                    "step_condition_failed",
                    message,
                    {"step_id": step.step_id, "condition": step.when},
                )
                frame.state = "FAILED_EXECUTION"
                add_audit_event(
                    frame,
                    "STEP_CONDITION_FAILED",
                    message,
                    {
                        "step_id": step.step_id,
                        "condition": step.when,
                        "trace": {"ok": False, "condition": step.when, "error": message},
                    },
                )
                return frame

            if should_run:
                add_audit_event(
                    frame,
                    "STEP_CONDITION_PASSED",
                    "Step condition passed.",
                    {"step_id": step.step_id, "condition": step.when, "trace": trace},
                )
            else:
                step.status = "SKIPPED"
                add_audit_event(
                    frame,
                    "STEP_CONDITION_SKIPPED",
                    "Step condition skipped step.",
                    {"step_id": step.step_id, "condition": step.when, "trace": trace},
                )
                self._advance_current_step_id(frame, pending_index)
                if self._first_pending_step_index(frame) is None and frame.state == "RUNNING":
                    transition_state(frame, "VERIFYING")
                return frame

        retry_policy = normalize_retry_policy(step.retry)
        while step.attempts < step.max_attempts:
            step.attempts += 1
            attempt_started_at = utc_now()
            attempt_start_mono = monotonic_now()
            step.status = "RUNNING"
            step.started_at = attempt_started_at
            add_audit_event(
                frame,
                "STEP_ATTEMPT_STARTED",
                "Step attempt started.",
                {
                    "step_id": step.step_id,
                    "attempt": step.attempts,
                    "max_attempts": step.max_attempts,
                    "retry_policy": dict(retry_policy),
                    "started_at": attempt_started_at,
                    "timeout_seconds": step.timeout_seconds,
                },
            )
            snapshot = self._snapshot_attempt_state(frame, step)

            result, error_info = self._execute_step_once(frame, manifest, step, dry_run=dry_run)
            attempt_ended_at = utc_now()
            attempt_end_mono = monotonic_now()
            attempt_duration_ms = duration_ms(attempt_start_mono, attempt_end_mono)
            timed_out = timeout_exceeded(attempt_duration_ms / 1000.0, step.timeout_seconds)
            timing_data = build_timing_record(
                step.step_id,
                step.attempts,
                attempt_started_at,
                attempt_ended_at,
                attempt_duration_ms,
                step.timeout_seconds,
                timed_out,
            )

            step.started_at = attempt_started_at
            step.ended_at = attempt_ended_at
            step.duration_ms = attempt_duration_ms

            if timed_out:
                timeout_message = f"Step exceeded timeout_seconds={step.timeout_seconds} with duration_ms={attempt_duration_ms:.2f}"
                self._restore_attempt_state(frame, step, snapshot)
                step.status = "FAILED"
                step.error = timeout_message
                step.last_error = timeout_message
                step.started_at = attempt_started_at
                step.ended_at = attempt_ended_at
                step.duration_ms = attempt_duration_ms
                frame.state = "FAILED_VALIDATION" if step.kind in CUSTOM_VALIDATION_STEP_KINDS or step.kind == "validate" else "FAILED_EXECUTION"
                timeout_error_info = {"error_type": "StepTimeoutExceeded", "message": timeout_message, "tag": "timeout"}
                record_error(
                    frame,
                    "step_timeout_exceeded",
                    timeout_message,
                    {
                        "step_id": step.step_id,
                        "attempt": step.attempts,
                        "timeout_seconds": step.timeout_seconds,
                        "duration_ms": attempt_duration_ms,
                    },
                )
                add_audit_event(
                    frame,
                    "STEP_TIMEOUT_EXCEEDED",
                    timeout_message,
                    {
                        "step_id": step.step_id,
                        "attempt": step.attempts,
                        "max_attempts": step.max_attempts,
                        "retry_policy": dict(retry_policy),
                        "error_info": timeout_error_info,
                        **timing_data,
                    },
                )
                add_audit_event(
                    frame,
                    "STEP_TIMING_RECORDED",
                    "Step timing recorded.",
                    {
                        "step_id": step.step_id,
                        "attempt": step.attempts,
                        "max_attempts": step.max_attempts,
                        "retry_policy": dict(retry_policy),
                        **timing_data,
                    },
                )

                policy_retryable = is_retryable_error(timeout_error_info, retry_policy)
                retryable = should_retry_step(step, timeout_error_info)
                self._record_attempt(
                    frame,
                    step,
                    status="FAILED",
                    retryable=policy_retryable,
                    error_info=timeout_error_info,
                    timing=timing_data,
                )
                add_audit_event(
                    frame,
                    "STEP_ATTEMPT_FAILED",
                    "Step attempt failed.",
                    {
                        "step_id": step.step_id,
                        "attempt": step.attempts,
                        "max_attempts": step.max_attempts,
                        "retry_policy": dict(retry_policy),
                        "error_info": timeout_error_info,
                        **timing_data,
                    },
                )

                if retryable and step.attempts < step.max_attempts:
                    add_audit_event(
                        frame,
                        "STEP_RETRY_SCHEDULED",
                        "Step retry scheduled.",
                        {
                            "step_id": step.step_id,
                            "attempt": step.attempts,
                            "max_attempts": step.max_attempts,
                            "retry_policy": dict(retry_policy),
                            "error_info": timeout_error_info,
                            **timing_data,
                        },
                    )
                    step.status = "PENDING"
                    step.error = ""
                    step.last_error = timeout_message
                    frame.state = "RUNNING"
                    sleep_before_retry(retry_policy.get("delay_seconds", 0))
                    continue

                if policy_retryable and step.attempts >= step.max_attempts:
                    add_audit_event(
                        frame,
                        "STEP_RETRY_EXHAUSTED",
                        "Step retries exhausted.",
                        {
                            "step_id": step.step_id,
                            "attempt": step.attempts,
                            "max_attempts": step.max_attempts,
                            "retry_policy": dict(retry_policy),
                            "error_info": timeout_error_info,
                            **timing_data,
                        },
                    )
                else:
                    add_audit_event(
                        frame,
                        "STEP_RETRY_NOT_ALLOWED",
                        "Step retry not allowed.",
                        {
                            "step_id": step.step_id,
                            "attempt": step.attempts,
                            "max_attempts": step.max_attempts,
                            "retry_policy": dict(retry_policy),
                            "error_info": timeout_error_info,
                            **timing_data,
                        },
                    )
                return frame

            add_audit_event(
                frame,
                "STEP_TIMING_RECORDED",
                "Step timing recorded.",
                {
                    "step_id": step.step_id,
                    "attempt": step.attempts,
                    "max_attempts": step.max_attempts,
                    "retry_policy": dict(retry_policy),
                    **timing_data,
                },
            )
            if step.status in {"COMPLETED", "STAGED", "SKIPPED"}:
                step.last_error = ""
                self._record_attempt(
                    frame,
                    step,
                    status=step.status,
                    retryable=False,
                    error_info={"error_type": "", "message": "", "tag": "none"},
                    timing=timing_data,
                )
                add_audit_event(
                    frame,
                    "STEP_ATTEMPT_SUCCEEDED",
                    "Step attempt succeeded.",
                    {
                        "step_id": step.step_id,
                        "attempt": step.attempts,
                        "max_attempts": step.max_attempts,
                        "retry_policy": dict(retry_policy),
                        **timing_data,
                    },
                )
                self._advance_current_step_id(frame, pending_index)
                if self._first_pending_step_index(frame) is None and frame.state == "RUNNING":
                    transition_state(frame, "VERIFYING")
                return frame

            if step.status == "FAILED":
                error_info = error_info or self._current_error_info(frame, step, result)
                policy_retryable = is_retryable_error(error_info, retry_policy)
                retryable = should_retry_step(step, error_info)
                self._record_attempt(
                    frame,
                    step,
                    status="FAILED",
                    retryable=policy_retryable,
                    error_info=error_info,
                    timing=timing_data,
                )
                add_audit_event(
                    frame,
                    "STEP_ATTEMPT_FAILED",
                    "Step attempt failed.",
                    {
                        "step_id": step.step_id,
                        "attempt": step.attempts,
                        "max_attempts": step.max_attempts,
                        "retry_policy": dict(retry_policy),
                        "error_info": error_info,
                        **timing_data,
                    },
                )

                if retryable and step.attempts < step.max_attempts:
                    add_audit_event(
                        frame,
                        "STEP_RETRY_SCHEDULED",
                        "Step retry scheduled.",
                        {
                            "step_id": step.step_id,
                            "attempt": step.attempts,
                            "max_attempts": step.max_attempts,
                            "retry_policy": dict(retry_policy),
                            "error_info": error_info,
                            **timing_data,
                        },
                    )
                    step.status = "PENDING"
                    step.error = ""
                    step.last_error = error_info.get("message", step.last_error)
                    frame.state = "RUNNING"
                    sleep_before_retry(retry_policy.get("delay_seconds", 0))
                    continue

                if policy_retryable and step.attempts >= step.max_attempts:
                    add_audit_event(
                        frame,
                        "STEP_RETRY_EXHAUSTED",
                        "Step retries exhausted.",
                        {
                            "step_id": step.step_id,
                            "attempt": step.attempts,
                            "max_attempts": step.max_attempts,
                            "retry_policy": dict(retry_policy),
                            "error_info": error_info,
                            **timing_data,
                        },
                    )
                else:
                    add_audit_event(
                        frame,
                        "STEP_RETRY_NOT_ALLOWED",
                        "Step retry not allowed.",
                        {
                            "step_id": step.step_id,
                            "attempt": step.attempts,
                            "max_attempts": step.max_attempts,
                            "retry_policy": dict(retry_policy),
                            "error_info": error_info,
                            **timing_data,
                        },
                    )

                if step.kind in CUSTOM_VALIDATION_STEP_KINDS or step.kind == "validate" or (isinstance(error_info, dict) and error_info.get("tag") == "validation"):
                    frame.state = "FAILED_VALIDATION"
                else:
                    frame.state = "FAILED_EXECUTION"
                return frame

        return frame

    def approve_pending_action(
        self,
        frame: TaskFrame,
        action_id: str,
        approved_by: str = "system",
        reason: str = "",
    ) -> TaskFrame:
        action = get_pending_action(frame, action_id)
        if action.get("status") != "PENDING_APPROVAL":
            raise PendingActionError(f"Pending action must be PENDING_APPROVAL to approve: {action.get('status')}")
        approve_action(frame, action_id, approved_by=approved_by, reason=reason)
        return frame

    def reject_pending_action(
        self,
        frame: TaskFrame,
        action_id: str,
        rejected_by: str = "system",
        reason: str = "",
    ) -> TaskFrame:
        action = get_pending_action(frame, action_id)
        if action.get("status") != "PENDING_APPROVAL":
            raise PendingActionError(f"Pending action must be PENDING_APPROVAL to reject: {action.get('status')}")
        reject_action(frame, action_id, rejected_by=rejected_by, reason=reason)
        record_error(
            frame,
            "PENDING_ACTION_REJECTED",
            reason or "Pending action rejected.",
            {
                "action_id": action_id,
                "tool": action.get("tool"),
                "output_alias": action.get("output_alias"),
            },
        )
        transition_state(frame, "FAILED_COMPLETION")
        return frame

    def execute_approved_pending_actions(
        self,
        frame: TaskFrame,
        manifest: Manifest,
        dry_run: bool = True,
        live_mode: bool = False,
    ) -> TaskFrame:
        if frame.state != "WAITING_FOR_EXECUTE":
            raise ValueError("TaskFrame must be WAITING_FOR_EXECUTE to execute approved pending actions.")
        if dry_run and live_mode:
            raise LiveExecutionBlocked("Live execution cannot run in dry-run mode.")
        if not dry_run and not live_mode:
            raise ToolExecutionBlocked("Live execution requires live_mode=True.")

        approved_actions = list_pending_actions(frame, "APPROVED")
        if not approved_actions:
            raise PendingActionError("No approved pending actions to execute.")

        transition_state(frame, "EXECUTING_PENDING")
        runner = ToolRunner(dry_run=dry_run)
        for action in approved_actions:
            if live_mode:
                result = runner.execute_live_pending_action(frame, manifest, action, runtime_live_mode=True)
            else:
                result = runner.execute_pending_action(frame, action)
            if not result.ok:
                if frame.state not in {"FAILED_EXECUTION", "FAILED_COMPLETION", "FAILED_VALIDATION"}:
                    transition_state(frame, "FAILED_EXECUTION")
                return frame

        transition_state(frame, "VERIFYING")
        frame = self.verify_frame(frame, manifest)
        return frame

    def verify_frame(self, frame: TaskFrame, manifest: Manifest) -> TaskFrame:
        if frame.state not in {"VERIFYING", "WAITING_FOR_EXECUTE"}:
            raise ValueError("TaskFrame must be VERIFYING or WAITING_FOR_EXECUTE to verify.")

        run_manifest_validations(frame, manifest, memory_store=self.memory_store)
        completion_result = evaluate_completion(frame, manifest)
        apply_completion_result(frame, completion_result)
        return frame

    def run_until_blocked(
        self,
        frame: TaskFrame,
        manifest: Manifest,
        dry_run: bool = True,
    ) -> TaskFrame:
        while frame.state in {"READY", "RUNNING", "WAITING_FOR_EXECUTE"}:
            pending_index_before = self._first_pending_step_index(frame)
            if pending_index_before is None:
                break
            frame = self.run_next_step(frame, manifest, dry_run=dry_run)
            if frame.state in {
                "WAITING_FOR_INPUT",
                "VERIFYING",
                "FAILED_VALIDATION",
                "FAILED_EXECUTION",
                "FAILED_COMPLETION",
                "COMPLETED",
                "COMPLETED_NO_DATA",
                "CANCELLED",
                "EXPIRED",
            }:
                break
            if frame.state == "WAITING_FOR_EXECUTE" and not bool(getattr(manifest, "completion", {}).get("continue_after_pending", False)):
                break
            if frame.state == "WAITING_FOR_EXECUTE" and self._first_pending_step_index(frame) is None:
                break

        if frame.state in {"VERIFYING", "WAITING_FOR_EXECUTE"}:
            frame = self.verify_frame(frame, manifest)
        return frame

    def _first_pending_step_index(self, frame: TaskFrame) -> int | None:
        for index, step in enumerate(frame.steps):
            if step.status == "PENDING":
                return index
        return None

    def _advance_current_step_id(self, frame: TaskFrame, current_index: int) -> None:
        next_index = None
        for index in range(current_index + 1, len(frame.steps)):
            if frame.steps[index].status == "PENDING":
                next_index = index
                break
        frame.current_step_id = frame.steps[next_index].step_id if next_index is not None else None

    def _run_validation_step(self, frame: TaskFrame, manifest: Manifest, step):
        try:
            result = run_validation_step(
                frame=frame,
                manifest=manifest,
                validation_id=step.action,
                memory_store=self.memory_store,
            )
        except Exception as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            record_error(
                frame,
                "validation_step_failed",
                message,
                {"step_id": step.step_id, "validation_id": step.action, "error_type": type(exc).__name__, "tag": "validation"},
            )
            frame.state = "FAILED_VALIDATION"
            add_audit_event(
                frame,
                "VALIDATION_STEP_FAILED",
                message,
                {"step_id": step.step_id, "validation_id": step.action, "error_type": type(exc).__name__, "tag": "validation"},
            )
            return validation_fail(step.action, "validate", message, {"step_id": step.step_id})

        if result.ok:
            step.status = "COMPLETED"
            step.error = ""
            step.last_error = ""
        else:
            step.status = "FAILED"
            step.error = result.message
            step.last_error = result.message
            record_error(
                frame,
                "validation_step_failed",
                result.message,
                {"step_id": step.step_id, "validation_id": step.action, "error_type": "ValidationEngineError", "tag": "validation"},
            )
            frame.state = "FAILED_VALIDATION"
            add_audit_event(
                frame,
                "VALIDATION_STEP_FAILED",
                result.message,
                {"step_id": step.step_id, "validation_id": step.action, "error_type": "ValidationEngineError", "tag": "validation"},
            )
        return result

    def _execute_step_once(self, frame: TaskFrame, manifest: Manifest, step, dry_run: bool):
        if step.kind == "approval":
            runner = ApprovalCommandRunner(
                runtime_data_dir=self.runtime_data_dir,
                manifest_dir=self.manifest_dir,
            )
            try:
                result = runner.run_step(frame, step)
                return result, None if getattr(result, "ok", False) else self._error_info_from_result(result)
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "approval_command_failed",
                    message,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": type(exc).__name__, "tag": "unknown"},
                )
                return None, classify_error(exc)

        if step.kind == "inspection":
            runner = InspectionCommandRunner(inspector=self.inspector)
            try:
                result = runner.run_step(frame, step)
                return result, None if getattr(result, "ok", False) else self._error_info_from_result(result)
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "inspection_command_failed",
                    message,
                    {"step_id": step.step_id, "action": step.action, "error_type": type(exc).__name__, "tag": "unknown"},
                )
                return None, classify_error(exc)

        if step.kind == "cleanup":
            runner = CleanupCommandRunner(cleaner=ArtifactCleaner(runtime_data_dir=self.runtime_data_dir))
            try:
                result = runner.run_step(frame, step)
                return result, None if getattr(result, "ok", False) else self._error_info_from_result(result)
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "cleanup_command_failed",
                    message,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": type(exc).__name__, "tag": "unknown"},
                )
                return None, classify_error(exc)

        if step.kind == "maintenance":
            runner = MaintenanceCommandRunner(runtime_data_dir=self.runtime_data_dir)
            try:
                result = runner.run_step(frame, step)
                return result, None if getattr(result, "ok", False) else self._error_info_from_result(result)
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "maintenance_command_failed",
                    message,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": type(exc).__name__, "tag": "unknown"},
                )
                return None, classify_error(exc)

        if step.kind == "validate":
            try:
                result = self._run_validation_step(frame, manifest, step)
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_VALIDATION"
                record_error(
                    frame,
                    "validation_step_failed",
                    message,
                    {"step_id": step.step_id, "validation_id": step.action, "error_type": type(exc).__name__, "tag": "validation"},
                )
                return None, {"error_type": type(exc).__name__, "message": message, "tag": "validation"}

            error_info = None if result.ok else {"error_type": "ValidationEngineError", "message": result.message, "tag": "validation"}
            return result, error_info

        if step.kind == "llm":
            runner = LLMCommandRunner(adapter=self.llm_adapter)
            try:
                result = runner.run_step(frame, step)
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "llm_command_failed",
                    message,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": type(exc).__name__, "tag": "unknown"},
                )
                return None, classify_error(exc)
            error_info = self._error_info_from_result(result)
            return result, error_info if not result.ok else None

        if step.kind == "memory":
            runner = MemoryCommandRunner(self.memory_store)
            try:
                result = runner.run_step(frame, step)
                return result, None if getattr(result, "ok", False) else self._error_info_from_result(result)
            except MemoryCommandError as exc:
                error_info = classify_error(exc)
                return None, error_info
            except Exception as exc:
                message = str(exc)
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "memory_command_error",
                    message,
                    {"step_id": step.step_id, "action": step.action, "error_type": type(exc).__name__, "tag": "unknown"},
                )
                error_info = classify_error(exc)
                return None, error_info

        if step.kind == "validate_required_inputs":
            required_inputs = self._custom_step_required_inputs(manifest, step)
            missing = [name for name in required_inputs if name not in frame.inputs]
            result_data = {"step_id": step.step_id, "ok": len(missing) == 0, "missing": missing}
            frame.validations.append(result_data)
            if missing:
                message = f"Missing required inputs: {', '.join(missing)}"
                step.status = "FAILED"
                step.error = message
                step.last_error = message
                frame.state = "FAILED_VALIDATION"
                record_error(
                    frame,
                    "required_input_validation_failed",
                    message,
                    {"step_id": step.step_id, "missing": missing, "tag": "validation"},
                )
                add_audit_event(
                    frame,
                    "REQUIRED_INPUT_VALIDATION_FAILED",
                    message,
                    {"step_id": step.step_id, "missing": missing},
                )
                return validation_fail(step.step_id, "validate_required_inputs", message, {"step_id": step.step_id, "missing": missing}), None
            step.status = "COMPLETED"
            step.error = ""
            step.last_error = ""
            add_audit_event(
                frame,
                "REQUIRED_INPUT_VALIDATION_PASSED",
                "Required inputs validated.",
                {"step_id": step.step_id, "required_inputs": required_inputs},
            )
            return validation_ok(step.step_id, "validate_required_inputs", "Required inputs validated.", {"step_id": step.step_id, "missing": []}), None

        runner = ToolRunner(dry_run=dry_run)
        try:
            result = runner.run_step(frame, step)
        except Exception as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "tool_execution_failed",
                message,
                {"step_id": step.step_id, "tool": f"{step.namespace}/{step.action}" if step.namespace and step.action else "", "error_type": type(exc).__name__, "tag": "transient"},
            )
            return None, classify_error(exc)
        error_info = self._error_info_from_result(result)
        return result, error_info if not result.ok else None

    def _custom_step_required_inputs(self, manifest: Manifest, step) -> list[str]:
        manifest_step = self._manifest_step_by_id(manifest, step.step_id)
        metadata = getattr(manifest_step, "metadata", {}) if manifest_step is not None else {}
        if isinstance(metadata, dict):
            required = metadata.get("required_inputs")
            if isinstance(required, list):
                return [str(item) for item in required if str(item).strip()]
        if isinstance(step.output_alias, str) and step.output_alias.strip():
            return [step.output_alias]
        return []

    def _manifest_step_by_id(self, manifest: Manifest, step_id: str):
        for manifest_step in manifest.steps:
            if manifest_step.id == step_id:
                return manifest_step
        return None

    def _error_info_from_result(self, result) -> dict[str, str]:
        metadata = getattr(result, "metadata", None)
        if isinstance(metadata, dict) and metadata.get("error_type"):
            return {
                "error_type": str(metadata.get("error_type", "UnknownError")),
                "message": str(getattr(result, "error", "")),
                "tag": str(metadata.get("tag", "unknown")),
            }
        return classify_error(getattr(result, "error", ""))

    def _current_error_info(self, frame: TaskFrame, step, result) -> dict[str, str]:
        if result is not None:
            if hasattr(result, "metadata") and isinstance(result.metadata, dict) and result.metadata.get("error_type"):
                return self._error_info_from_result(result)
            if getattr(result, "error", ""):
                return classify_error(result.error)
        if step.last_error:
            return classify_error(step.last_error)
        if step.error:
            return classify_error(step.error)
        return {"error_type": "UnknownError", "message": "", "tag": "unknown"}

    def _record_attempt(
        self,
        frame: TaskFrame,
        step,
        *,
        status: str,
        retryable: bool,
        error_info: dict[str, str],
        timing: dict[str, Any],
    ) -> None:
        frame.attempts.append(
            {
                "step_id": step.step_id,
                "attempt": step.attempts,
                "max_attempts": step.max_attempts,
                "status": status,
                "retryable": retryable,
                "error_type": error_info.get("error_type", ""),
                "error_tag": error_info.get("tag", ""),
                "message": error_info.get("message", ""),
                "started_at": timing.get("started_at", ""),
                "ended_at": timing.get("ended_at", ""),
                "duration_ms": timing.get("duration_ms", 0.0),
                "timeout_seconds": timing.get("timeout_seconds"),
                "timed_out": timing.get("timed_out", False),
                "timestamp": utc_now(),
            }
        )

    def _snapshot_attempt_state(self, frame: TaskFrame, step) -> dict[str, Any]:
        return {
            "state": frame.state,
            "current_step_id": frame.current_step_id,
            "outputs": copy.deepcopy(frame.outputs),
            "evidence": copy.deepcopy(frame.evidence),
            "pending_actions": copy.deepcopy(frame.pending_actions),
            "executed_actions": copy.deepcopy(frame.executed_actions),
            "tool_calls": copy.deepcopy(frame.tool_calls),
            "llm_calls": copy.deepcopy(frame.llm_calls),
            "validations": copy.deepcopy(frame.validations),
            "errors": copy.deepcopy(frame.errors),
            "completion_gate_result": copy.deepcopy(frame.completion_gate_result),
            "final_response": frame.final_response,
            "step": {
                "status": step.status,
                "error": step.error,
                "last_error": step.last_error,
                "result_ref": step.result_ref,
                "started_at": step.started_at,
                "ended_at": step.ended_at,
                "duration_ms": step.duration_ms,
            },
        }

    def _restore_attempt_state(self, frame: TaskFrame, step, snapshot: dict[str, Any]) -> None:
        frame.state = snapshot["state"]
        frame.current_step_id = snapshot["current_step_id"]
        frame.outputs = copy.deepcopy(snapshot["outputs"])
        frame.evidence = copy.deepcopy(snapshot["evidence"])
        frame.pending_actions = copy.deepcopy(snapshot["pending_actions"])
        frame.executed_actions = copy.deepcopy(snapshot["executed_actions"])
        frame.tool_calls = copy.deepcopy(snapshot["tool_calls"])
        frame.llm_calls = copy.deepcopy(snapshot["llm_calls"])
        frame.validations = copy.deepcopy(snapshot["validations"])
        frame.errors = copy.deepcopy(snapshot["errors"])
        frame.completion_gate_result = copy.deepcopy(snapshot["completion_gate_result"])
        frame.final_response = snapshot["final_response"]
        step.status = snapshot["step"]["status"]
        step.error = snapshot["step"]["error"]
        step.last_error = snapshot["step"]["last_error"]
        step.result_ref = snapshot["step"]["result_ref"]
        step.started_at = snapshot["step"]["started_at"]
        step.ended_at = snapshot["step"]["ended_at"]
        step.duration_ms = snapshot["step"]["duration_ms"]
