from __future__ import annotations

from pathlib import Path
from typing import Any

from .approval import approve_action, reject_action
from .arg_resolver import resolve_command_args
from .errors import ApprovalCommandBlocked, ApprovalCommandError
from .inspection import RunInspector
from .models import ApprovalCommandResult, StepRuntime, TaskFrame, approval_command_error, approval_command_ok
from .pending_actions import list_pending_actions
from .persistence import persist_frame_update
from .taskframe import add_audit_event, record_error, set_output, transition_state
from .taskframe_reload import load_manifest_for_frame, load_taskframe


class ApprovalCommandRunner:
    def __init__(
        self,
        runtime_data_dir: str | Path = "runtime_data",
        manifest_dir: str | Path = "manifests",
        dry_run_execution_only: bool = True,
    ):
        self.runtime_data_dir = Path(runtime_data_dir)
        self.manifest_dir = Path(manifest_dir)
        self.dry_run_execution_only = dry_run_execution_only
        self.inspector = RunInspector(self.runtime_data_dir)

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> ApprovalCommandResult:
        step.status = "RUNNING"
        if step.kind != "approval":
            return self._fail(frame, step, f"Unsupported approval step kind: {step.kind}", "ApprovalCommandError")
        if not step.output_alias:
            return self._fail(frame, step, "Approval command requires an output alias.", "ApprovalCommandError")

        try:
            args = resolve_command_args(frame, _step_args(step))
            action = step.action
            add_audit_event(
                frame,
                "APPROVAL_COMMAND_STARTED",
                "Approval command started.",
                {"step_id": step.step_id, "action": action, "output_alias": step.output_alias, "args": dict(args)},
            )
            result = self._run_action(frame, step, action, args)
            if result.ok:
                set_output(frame, step.output_alias, result.data)
                step.result_ref = step.output_alias
                step.status = "COMPLETED"
                step.error = ""
                step.last_error = ""
                add_audit_event(
                    frame,
                    "APPROVAL_COMMAND_COMPLETED",
                    "Approval command completed.",
                    {"step_id": step.step_id, "action": action, "output_alias": step.output_alias},
                )
            else:
                step.status = "FAILED"
                step.error = result.error
                step.last_error = result.error
                record_error(
                    frame,
                    "approval_command_failed",
                    result.error,
                    {"step_id": step.step_id, "action": action, "output_alias": step.output_alias},
                )
                add_audit_event(
                    frame,
                    "APPROVAL_COMMAND_FAILED",
                    result.error,
                    {"step_id": step.step_id, "action": action, "output_alias": step.output_alias},
                )
            return result
        except Exception as exc:
            requested_frame_id = ""
            requested_action_id = ""
            try:
                args = resolve_command_args(frame, _step_args(step))
                requested_frame_id = str(args.get("frame_id", "")).strip()
                requested_action_id = str(args.get("action_id", "")).strip()
            except Exception:
                pass
            return self._fail(frame, step, str(exc), type(exc).__name__, frame_id=requested_frame_id, action_id=requested_action_id)

    def _run_action(
        self,
        command_frame: TaskFrame,
        step: StepRuntime,
        action: str,
        args: dict[str, Any],
    ) -> ApprovalCommandResult:
        frame_id = str(args.get("frame_id", ""))
        if action == "list_pending":
            target_frame = self._load_target_frame(frame_id)
            pending = [
                item
                for item in list_pending_actions(target_frame)
                if item.get("status") in {"PENDING_APPROVAL", "APPROVED", "EXECUTING"}
            ]
            return approval_command_ok(
                action,
                {"frame_id": target_frame.frame_id, "count": len(pending), "pending_actions": pending},
                frame_id=target_frame.frame_id,
            )

        if not frame_id:
            raise ApprovalCommandError("Approval commands require frame_id.")

        target_frame = self._load_target_frame(frame_id)

        if action == "approve":
            action_id = self._require_action_id(args)
            self._require_waiting_for_execute(target_frame)
            approved = approve_action(
                target_frame,
                action_id,
                approved_by=str(args.get("approved_by", "system")),
                reason=str(args.get("reason", "")),
            )
            persist_frame_update(approved, self.runtime_data_dir)
            return approval_command_ok(
                action,
                {
                    "frame_id": target_frame.frame_id,
                    "action_id": action_id,
                    "status": "APPROVED",
                    "target_frame_state": target_frame.state,
                    "artifact_saved": True,
                },
                frame_id=target_frame.frame_id,
                action_id=action_id,
            )

        if action == "reject":
            action_id = self._require_action_id(args)
            self._require_waiting_for_execute(target_frame)
            rejected = reject_action(
                target_frame,
                action_id,
                rejected_by=str(args.get("rejected_by", "system")),
                reason=str(args.get("reason", "")),
            )
            transition_state(rejected, "FAILED_COMPLETION")
            persist_frame_update(rejected, self.runtime_data_dir)
            return approval_command_ok(
                action,
                {
                    "frame_id": target_frame.frame_id,
                    "action_id": action_id,
                    "status": "REJECTED",
                    "target_frame_state": target_frame.state,
                    "artifact_saved": True,
                },
                frame_id=target_frame.frame_id,
                action_id=action_id,
            )

        if action == "execute_approved":
            if not self.dry_run_execution_only:
                raise ApprovalCommandBlocked("execute_approved is blocked unless dry_run_execution_only=True.")
            self._require_waiting_for_execute(target_frame)
            approved_actions = list_pending_actions(target_frame, "APPROVED")
            if not approved_actions:
                raise ApprovalCommandError("No approved pending actions to execute.")
            target_manifest = load_manifest_for_frame(target_frame, self.manifest_dir)
            executed = self._execute_approved(target_frame, target_manifest, live_mode=False)
            if target_frame.state not in {"COMPLETED", "COMPLETED_NO_DATA"}:
                persist_frame_update(target_frame, self.runtime_data_dir)
                raise ApprovalCommandError(f"Approved action execution failed: {target_frame.state}")
            persist_frame_update(executed, self.runtime_data_dir)
            return approval_command_ok(
                action,
                {
                    "frame_id": target_frame.frame_id,
                    "target_frame_state": target_frame.state,
                    "executed_action_count": len(target_frame.executed_actions),
                    "pending_action_statuses": {item.get("action_id", ""): item.get("status", "") for item in target_frame.pending_actions},
                    "artifact_saved": True,
                },
                frame_id=target_frame.frame_id,
            )

        if action == "execute_live_approved":
            self._require_waiting_for_execute(target_frame)
            self._require_confirm_live(args)
            approved_actions = list_pending_actions(target_frame, "APPROVED")
            if not approved_actions:
                raise ApprovalCommandError("No approved pending actions to execute.")
            target_manifest = load_manifest_for_frame(target_frame, self.manifest_dir)
            executed = None
            try:
                executed = self._execute_approved(target_frame, target_manifest, live_mode=True)
            finally:
                persist_frame_update(target_frame, self.runtime_data_dir)
            if target_frame.state not in {"COMPLETED", "COMPLETED_NO_DATA"}:
                raise ApprovalCommandError(f"Live approved action execution failed: {target_frame.state}")
            persist_frame_update(executed or target_frame, self.runtime_data_dir)
            return approval_command_ok(
                action,
                {
                    "frame_id": target_frame.frame_id,
                    "target_frame_state": target_frame.state,
                    "executed_action_count": len(target_frame.executed_actions),
                    "pending_action_statuses": {item.get("action_id", ""): item.get("status", "") for item in target_frame.pending_actions},
                    "artifact_saved": True,
                    "live_mode": True,
                },
                frame_id=target_frame.frame_id,
            )

        if action == "approve_and_execute":
            action_id = self._require_action_id(args)
            self._require_waiting_for_execute(target_frame)
            approve_action(
                target_frame,
                action_id,
                approved_by=str(args.get("approved_by", "system")),
                reason=str(args.get("reason", "")),
            )
            persist_frame_update(target_frame, self.runtime_data_dir)
            target_manifest = load_manifest_for_frame(target_frame, self.manifest_dir)
            executed = self._execute_approved(target_frame, target_manifest, live_mode=False)
            if target_frame.state not in {"COMPLETED", "COMPLETED_NO_DATA"}:
                persist_frame_update(target_frame, self.runtime_data_dir)
                raise ApprovalCommandError(f"Approved action execution failed: {target_frame.state}")
            persist_frame_update(executed, self.runtime_data_dir)
            return approval_command_ok(
                action,
                {
                    "frame_id": target_frame.frame_id,
                    "action_id": action_id,
                    "approval_status": "APPROVED",
                    "execution_status": "EXECUTED" if target_frame.state in {"COMPLETED", "COMPLETED_NO_DATA"} else "FAILED",
                    "target_frame_state": target_frame.state,
                    "artifact_saved": True,
                },
                frame_id=target_frame.frame_id,
                action_id=action_id,
            )

        raise ApprovalCommandError(f"Unsupported approval action: {action}")

    def _execute_approved(self, target_frame: TaskFrame, target_manifest, live_mode: bool) -> TaskFrame:
        orchestrator = self._build_orchestrator()
        if live_mode:
            return orchestrator.execute_approved_pending_actions(target_frame, target_manifest, dry_run=False, live_mode=True)
        return orchestrator.execute_approved_pending_actions(target_frame, target_manifest, dry_run=True, live_mode=False)

    def _build_orchestrator(self):
        from .orchestrator import Orchestrator

        return Orchestrator(
            runtime_data_dir=self.runtime_data_dir,
            manifest_dir=self.manifest_dir,
            inspector=self.inspector,
        )

    def _load_target_frame(self, frame_id: str) -> TaskFrame:
        try:
            return load_taskframe(frame_id, self.runtime_data_dir)
        except Exception as exc:
            raise ApprovalCommandError(str(exc)) from exc

    def _require_action_id(self, args: dict[str, Any]) -> str:
        action_id = str(args.get("action_id", "")).strip()
        if not action_id:
            raise ApprovalCommandError("Approval commands require action_id.")
        return action_id

    def _require_waiting_for_execute(self, frame: TaskFrame) -> None:
        if frame.state != "WAITING_FOR_EXECUTE":
            raise ApprovalCommandError(f"TaskFrame must be WAITING_FOR_EXECUTE: {frame.state}")

    def _require_confirm_live(self, args: dict[str, Any]) -> None:
        value = args.get("confirm_live")
        if isinstance(value, bool):
            confirmed = value
        elif isinstance(value, str):
            confirmed = value.strip().lower() in {"true", "1", "yes", "on"}
        else:
            confirmed = False
        if not confirmed:
            raise ApprovalCommandBlocked("Live approval execution requires confirm_live=true.")

    def _fail(
        self,
        frame: TaskFrame,
        step: StepRuntime,
        message: str,
        error_type: str,
        *,
        frame_id: str = "",
        action_id: str = "",
    ) -> ApprovalCommandResult:
        step.status = "FAILED"
        step.error = message
        step.last_error = message
        record_error(
            frame,
            "approval_command_failed",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
        )
        add_audit_event(
            frame,
            "APPROVAL_COMMAND_FAILED",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": error_type},
        )
        return approval_command_error(
            step.action,
            message,
            frame_id=frame_id or frame.frame_id,
            action_id=action_id,
            metadata={"error_type": error_type},
        )


def _step_args(step: StepRuntime) -> dict[str, str]:
    from .command_parser import parse_command

    return parse_command(step.command).args
