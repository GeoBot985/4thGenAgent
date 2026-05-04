from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .arg_resolver import resolve_command_args
from .artifact_cleanup import ArtifactCleaner
from .errors import CleanupConfirmationError, CleanupPolicyError
from .models import CleanupResult, StepRuntime, TaskFrame
from .retention_policy import normalize_retention_policy, validate_retention_policy
from .taskframe import add_audit_event, record_error, set_output, json_safe


class CleanupCommandRunner:
    def __init__(self, cleaner: ArtifactCleaner | None = None):
        self.cleaner = cleaner or ArtifactCleaner()

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> CleanupResult:
        step.status = "RUNNING"
        if step.kind != "cleanup":
            return self._fail(frame, step, f"Unsupported cleanup step kind: {step.kind}", "CleanupPolicyError")
        if not step.output_alias:
            return self._fail(frame, step, "Cleanup command requires an output alias.", "CleanupPolicyError")

        try:
            args = resolve_command_args(frame, _step_args(step))
            policy = self._build_policy(step.action, args)
            add_audit_event(
                frame,
                "CLEANUP_COMMAND_STARTED",
                "Cleanup command started.",
                {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "policy": dict(policy)},
            )
            result = self._run_action(step.action, policy)
            set_output(frame, step.output_alias, json_safe(asdict(result)))
            step.result_ref = step.output_alias
            if result.ok:
                step.status = "COMPLETED"
                step.error = ""
                step.last_error = ""
                add_audit_event(
                    frame,
                    "CLEANUP_COMMAND_COMPLETED",
                    "Cleanup command completed.",
                    {
                        "step_id": step.step_id,
                        "action": step.action,
                        "output_alias": step.output_alias,
                        "cleanup_id": result.cleanup_id,
                        "report_path": result.report_path,
                    },
                )
            else:
                step.status = "FAILED"
                step.error = result.error
                step.last_error = result.error
                record_error(
                    frame,
                    "cleanup_command_failed",
                    result.error,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
                add_audit_event(
                    frame,
                    "CLEANUP_COMMAND_FAILED",
                    result.error,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
            return result
        except Exception as exc:
            return self._fail(frame, step, str(exc), type(exc).__name__)

    def _run_action(self, action: str, policy: dict[str, Any]) -> CleanupResult:
        if action == "plan" or action in {"reports_plan", "index_plan", "temp_plan"}:
            if action == "reports_plan":
                policy["mode"] = "reports_only"
            elif action == "index_plan":
                policy["mode"] = "indexes_only"
            elif action == "temp_plan":
                policy["mode"] = "temp_only"
            policy["dry_run"] = True
            policy["confirm_cleanup"] = False
            validate_retention_policy(policy)
            return self.cleaner.plan_cleanup(policy)

        if action == "execute":
            if not isinstance(policy.get("dry_run"), bool) or policy.get("dry_run") is not False:
                raise CleanupConfirmationError("c:execute requires dry_run=false.")
            if not isinstance(policy.get("confirm_cleanup"), bool) or policy.get("confirm_cleanup") is not True:
                raise CleanupConfirmationError("c:execute requires confirm_cleanup=true.")
            validate_retention_policy(policy)
            return self.cleaner.execute_cleanup(policy)

        raise CleanupPolicyError(f"Unsupported cleanup action: {action}")

    def _build_policy(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        policy = normalize_retention_policy(None)
        policy.update(self._coerce_args(args))
        if action == "reports_plan":
            policy["mode"] = "reports_only"
            policy["dry_run"] = True
            policy["confirm_cleanup"] = False
        elif action == "index_plan":
            policy["mode"] = "indexes_only"
            policy["dry_run"] = True
            policy["confirm_cleanup"] = False
        elif action == "temp_plan":
            policy["mode"] = "temp_only"
            policy["dry_run"] = True
            policy["confirm_cleanup"] = False
        elif action == "plan":
            policy["dry_run"] = True
            policy["confirm_cleanup"] = False
        return policy

    def _coerce_args(self, args: dict[str, Any]) -> dict[str, Any]:
        coerced: dict[str, Any] = {}
        for key, value in args.items():
            if key in {"dry_run", "confirm_cleanup", "delete_reports", "delete_artifact_index", "delete_temp_files", "delete_empty_dirs", "delete_expired_approval_packs", "delete_run_dirs"}:
                coerced[key] = self._parse_bool(value, key)
            elif key in {"min_age_days", "max_report_age_days", "max_temp_age_days", "max_approval_pack_age_days"}:
                coerced[key] = self._parse_number(value, key)
            elif key == "mode":
                coerced[key] = self._parse_mode(value)
            else:
                coerced[key] = value
        return coerced

    def _parse_bool(self, value: Any, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        raise CleanupPolicyError(f"{field_name} must be true or false.")

    def _parse_number(self, value: Any, field_name: str) -> int | float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                if "." in value.strip():
                    return float(value)
                return int(value)
            except ValueError as exc:
                raise CleanupPolicyError(f"{field_name} must be numeric.") from exc
        raise CleanupPolicyError(f"{field_name} must be numeric.")

    def _parse_mode(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise CleanupPolicyError("mode must be a non-empty string.")
        return value.strip()

    def _fail(self, frame: TaskFrame, step: StepRuntime, message: str, error_type: str) -> CleanupResult:
        step.status = "FAILED"
        step.error = message
        step.last_error = message
        result = CleanupResult(
            ok=False,
            cleanup_id="",
            dry_run=True,
            policy=normalize_retention_policy(None),
            error=message,
            metadata={"error_type": error_type},
        )
        if step.output_alias:
            set_output(frame, step.output_alias, json_safe(asdict(result)))
            step.result_ref = step.output_alias
        record_error(
            frame,
            "cleanup_command_failed",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
        )
        add_audit_event(
            frame,
            "CLEANUP_COMMAND_FAILED",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": error_type},
        )
        return result


def _step_args(step: StepRuntime) -> dict[str, str]:
    from .command_parser import parse_command

    return parse_command(step.command).args
