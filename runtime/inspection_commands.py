from __future__ import annotations

from typing import Any

from .arg_resolver import resolve_command_args
from .errors import InspectionCommandError, InspectionTargetNotFoundError
from .inspection import RunInspector
from .models import InspectionResult, StepRuntime, TaskFrame
from .taskframe import add_audit_event, record_error, set_output, utc_now


class InspectionCommandRunner:
    def __init__(self, inspector: RunInspector | None = None):
        self.inspector = inspector or RunInspector()

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> InspectionResult:
        step.status = "RUNNING"
        if step.kind != "inspection":
            message = f"Unsupported inspection step kind: {step.kind}"
            return self._fail(frame, step, message, "InspectionCommandError")
        if not step.output_alias:
            message = "Inspection command requires an output alias."
            return self._fail(frame, step, message, "InspectionCommandError")

        try:
            args = _coerce_args(resolve_command_args(frame, _step_args(step)), step.action)
            add_audit_event(
                frame,
                "INSPECTION_COMMAND_STARTED",
                "Inspection command started.",
                {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "args": dict(args)},
            )
            result = self._run_action(step.action, args)
            if result.ok:
                set_output(frame, step.output_alias, result.data)
                step.result_ref = step.output_alias
                step.status = "COMPLETED"
                add_audit_event(
                    frame,
                    "INSPECTION_COMMAND_COMPLETED",
                    "Inspection command completed.",
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
            else:
                step.status = "FAILED"
                step.error = result.error
                step.last_error = result.error
                record_error(
                    frame,
                    "inspection_command_failed",
                    result.error,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
                add_audit_event(
                    frame,
                    "INSPECTION_COMMAND_FAILED",
                    result.error,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
            return result
        except Exception as exc:
            return self._fail(frame, step, str(exc), type(exc).__name__)

    def _run_action(self, action: str, args: dict[str, Any]) -> InspectionResult:
        frame_id = str(args.get("frame_id", ""))
        if action == "list_runs":
            return self.inspector.list_runs(limit=int(args.get("limit", 20)))
        if action == "cleanup_reports":
            return self.inspector.get_cleanup_reports()
        if not frame_id:
            raise InspectionCommandError("Inspection commands require frame_id.")
        if action == "summary":
            return self.inspector.get_run_summary(frame_id)
        if action == "taskframe":
            return self.inspector.get_taskframe(frame_id)
        if action == "outputs":
            return self.inspector.get_outputs(frame_id)
        if action == "audit":
            return self.inspector.get_audit(frame_id, limit=args.get("limit"))
        if action == "validations":
            return self.inspector.get_validations(frame_id, failed_only=bool(args.get("failed_only", False)))
        if action == "errors":
            return self.inspector.get_errors(frame_id)
        if action == "pending_actions":
            return self.inspector.get_pending_actions(frame_id)
        if action == "executed_actions":
            return self.inspector.get_executed_actions(frame_id)
        if action == "attempts":
            return self.inspector.get_attempts(frame_id)
        if action == "tool_calls":
            return self.inspector.get_tool_calls(frame_id)
        if action == "llm_calls":
            return self.inspector.get_llm_calls(frame_id)
        raise InspectionCommandError(f"Unsupported inspection action: {action}")

    def _fail(self, frame: TaskFrame, step: StepRuntime, message: str, error_type: str) -> InspectionResult:
        step.status = "FAILED"
        step.error = message
        step.last_error = message
        record_error(
            frame,
            "inspection_command_failed",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
        )
        add_audit_event(
            frame,
            "INSPECTION_COMMAND_FAILED",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": error_type},
        )
        return InspectionResult(
            ok=False,
            action=step.action,
            frame_id=frame.frame_id,
            data=None,
            error=message,
            metadata={"error_type": error_type},
        )


def _step_args(step: StepRuntime) -> dict[str, str]:
    from .command_parser import parse_command

    return parse_command(step.command).args


def _coerce_args(args: dict[str, str], action: str) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for key, value in args.items():
        if key == "limit":
            try:
                coerced[key] = int(value)
            except (TypeError, ValueError) as exc:
                raise InspectionCommandError("limit must be an integer.") from exc
        elif key == "failed_only":
            lowered = str(value).strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                coerced[key] = True
            elif lowered in {"false", "0", "no", "n"}:
                coerced[key] = False
            else:
                raise InspectionCommandError("failed_only must be a boolean value.")
        else:
            coerced[key] = value
    return coerced
