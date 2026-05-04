from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .artifact_cleanup import ArtifactCleaner, get_cleanup_dir
from .artifact_index import get_artifact_index_path, rebuild_and_save_artifact_index
from .artifact_search import ArtifactSearcher
from .arg_resolver import resolve_command_args
from .cleanup_commands import CleanupCommandRunner
from .errors import MaintenanceCommandError, MaintenancePolicyError
from .models import MaintenanceResult, StepRuntime, TaskFrame, maintenance_error, maintenance_ok
from .persistence import ensure_dir
from .run_report import generate_approval_pack_report, generate_pending_action_report, generate_run_report
from .taskframe import add_audit_event, record_error, set_output, utc_now


class MaintenanceCommandRunner:
    def __init__(self, runtime_data_dir: str | Path = "runtime_data"):
        self.runtime_data_dir = Path(runtime_data_dir)

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> MaintenanceResult:
        step.status = "RUNNING"
        if step.kind != "maintenance":
            return self._fail(frame, step, f"Unsupported maintenance step kind: {step.kind}", "MaintenanceCommandError")
        if not step.output_alias:
            return self._fail(frame, step, "Maintenance command requires an output alias.", "MaintenanceCommandError")

        try:
            args = _coerce_args(resolve_command_args(frame, _step_args(step)))
            add_audit_event(
                frame,
                "MAINTENANCE_COMMAND_STARTED",
                "Maintenance command started.",
                {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "args": dict(args)},
            )
            result = self._run_action(step.action, args)
            set_output(frame, step.output_alias, result.data)
            step.result_ref = step.output_alias
            if result.ok:
                step.status = "COMPLETED"
                step.error = ""
                step.last_error = ""
                add_audit_event(
                    frame,
                    "MAINTENANCE_COMMAND_COMPLETED",
                    "Maintenance command completed.",
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
            else:
                step.status = "FAILED"
                step.error = result.error
                step.last_error = result.error
                record_error(
                    frame,
                    "maintenance_command_failed",
                    result.error,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
                add_audit_event(
                    frame,
                    "MAINTENANCE_COMMAND_FAILED",
                    result.error,
                    {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
                )
            return result
        except Exception as exc:
            return self._fail(frame, step, str(exc), type(exc).__name__)

    def _run_action(self, action: str, args: dict[str, Any]) -> MaintenanceResult:
        if action == "index_rebuild":
            index = rebuild_and_save_artifact_index(self.runtime_data_dir)
            return maintenance_ok(
                action,
                {
                    "action": "index_rebuild",
                    "index_path": str(get_artifact_index_path(self.runtime_data_dir)),
                    "record_count": int(index.get("record_count", 0) or 0),
                    "generated_at": index.get("generated_at", utc_now()),
                    "ok": True,
                },
            )

        if action == "cleanup_dry_run":
            policy = self._build_cleanup_policy(args)
            policy["dry_run"] = True
            policy["confirm_cleanup"] = False
            cleaner = ArtifactCleaner(self.runtime_data_dir)
            result = cleaner.plan_cleanup(policy)
            return maintenance_ok(
                action,
                {
                    "action": "cleanup_dry_run",
                    "cleanup_id": result.cleanup_id,
                    "dry_run": True,
                    "summary": dict(result.summary),
                    "report_path": result.report_path,
                    "ok": True,
                },
            )

        if action in {"report_failed_runs", "report_pending_runs", "report_live_packs"}:
            rebuild = self._parse_bool(args.get("rebuild", True), "rebuild") if "rebuild" in args else True
            limit = self._parse_limit(args.get("limit", 20))
            searcher = ArtifactSearcher(self.runtime_data_dir)
            if action == "report_failed_runs":
                matched = searcher.search_failed_runs(limit=limit, rebuild=rebuild)
                reports, errors = self._generate_reports_for_records(matched.get("runs", []), "failed")
            elif action == "report_pending_runs":
                matched = searcher.search_pending_runs(limit=limit, rebuild=rebuild)
                reports, errors = self._generate_reports_for_records(matched.get("runs", []), "pending")
            else:
                matched = searcher.search_live_packs(limit=limit, rebuild=rebuild)
                reports, errors = self._generate_reports_for_records(matched.get("runs", []), "approval_pack")
            return maintenance_ok(
                action,
                {
                    "action": action,
                    "matched_count": int(matched.get("count", 0) or 0),
                    "generated_count": len(reports),
                    "errors": errors,
                    "reports": reports,
                    "ok": True,
                },
            )

        if action == "summary":
            searcher = ArtifactSearcher(self.runtime_data_dir)
            summary = searcher.summarize(rebuild=True)
            summary["cleanup_report_count"] = self._count_cleanup_reports()
            summary["action"] = "summary"
            summary["ok"] = True
            return maintenance_ok(action, summary)

        raise MaintenancePolicyError(f"Unsupported maintenance action: {action}")

    def _build_cleanup_policy(self, args: dict[str, Any]) -> dict[str, Any]:
        policy: dict[str, Any] = {
            "schema_version": 1,
            "mode": str(args.get("mode", "derived_artifacts_only")),
            "dry_run": True,
            "confirm_cleanup": False,
            "delete_reports": True,
            "delete_artifact_index": True,
            "delete_temp_files": True,
            "delete_empty_dirs": True,
            "delete_expired_approval_packs": False,
            "delete_run_dirs": False,
            "min_age_days": 0,
            "max_report_age_days": 30,
            "max_temp_age_days": 7,
            "max_approval_pack_age_days": 30,
            "protect_states": [
                "WAITING_FOR_EXECUTE",
                "EXECUTING_PENDING",
                "FAILED_VALIDATION",
                "FAILED_EXECUTION",
                "FAILED_COMPLETION",
            ],
            "protect_live_execution": True,
            "protect_pending_actions": True,
            "protect_ready_approval_packs": True,
        }
        for key, value in args.items():
            if key in policy:
                policy[key] = value
        policy["dry_run"] = True
        policy["confirm_cleanup"] = False
        return policy

    def _generate_reports_for_records(self, records: list[dict[str, Any]], report_kind: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        reports: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in records:
            frame_id = str(record.get("frame_id", "")).strip()
            if not frame_id or frame_id in seen:
                continue
            seen.add(frame_id)
            try:
                if report_kind == "failed":
                    report = generate_run_report(self.runtime_data_dir, frame_id, rebuild=False)
                elif report_kind == "pending":
                    report = generate_pending_action_report(self.runtime_data_dir, frame_id, rebuild=False)
                else:
                    report = generate_approval_pack_report(self.runtime_data_dir, frame_id, rebuild=False)
                reports.append(
                    {
                        "frame_id": frame_id,
                        "markdown_path": report["markdown_path"],
                        "html_path": report["html_path"],
                    }
                )
            except Exception as exc:
                errors.append({"frame_id": frame_id, "error": str(exc), "error_type": type(exc).__name__})
        return reports, errors

    def _count_cleanup_reports(self) -> int:
        cleanup_dir = get_cleanup_dir(self.runtime_data_dir)
        if not cleanup_dir.is_dir():
            return 0
        return sum(1 for path in cleanup_dir.glob("cleanup_*.json") if path.is_file())

    def _parse_bool(self, value: Any, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        raise MaintenancePolicyError(f"{field_name} must be true or false.")

    def _parse_limit(self, value: Any) -> int:
        if isinstance(value, bool):
            raise MaintenancePolicyError("limit must be numeric.")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError as exc:
                raise MaintenancePolicyError("limit must be numeric.") from exc
        raise MaintenancePolicyError("limit must be numeric.")

    def _fail(self, frame: TaskFrame, step: StepRuntime, message: str, error_type: str) -> MaintenanceResult:
        step.status = "FAILED"
        step.error = message
        step.last_error = message
        record_error(
            frame,
            "maintenance_command_failed",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
        )
        add_audit_event(
            frame,
            "MAINTENANCE_COMMAND_FAILED",
            message,
            {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias, "error_type": error_type},
        )
        return maintenance_error(action=step.action, error=message, metadata={"error_type": error_type})


def run_maintenance_tick(
    runtime_engine,
    scheduler,
    dry_run: bool = True,
    schedule_prefix: str = "maintenance.",
) -> list[TaskFrame]:
    if not isinstance(schedule_prefix, str) or not schedule_prefix.strip():
        raise MaintenancePolicyError("schedule_prefix must be a non-empty string.")

    frames: list[TaskFrame] = []
    events = scheduler.create_events_for_enabled_by_prefix(schedule_prefix)
    for event in events:
        try:
            frame = runtime_engine.handle_event(event, dry_run=dry_run)
        except Exception:
            continue
        frames.append(frame)
    return frames


def _step_args(step: StepRuntime) -> dict[str, str]:
    from .command_parser import parse_command

    return parse_command(step.command).args


def _coerce_args(args: dict[str, str]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for key, value in args.items():
        if key in {"dry_run", "confirm_cleanup", "delete_reports", "delete_artifact_index", "delete_temp_files", "delete_empty_dirs", "delete_expired_approval_packs", "delete_run_dirs", "rebuild"}:
            coerced[key] = _parse_bool(value, key)
        elif key in {"min_age_days", "max_report_age_days", "max_temp_age_days", "max_approval_pack_age_days", "limit"}:
            coerced[key] = _parse_number(value, key)
        else:
            coerced[key] = value
    return coerced


def _parse_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise MaintenancePolicyError(f"{field_name} must be true or false.")


def _parse_number(value: Any, field_name: str) -> int | float:
    if isinstance(value, bool):
        raise MaintenancePolicyError(f"{field_name} must be numeric.")
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value) if "." in value.strip() else int(value)
        except ValueError as exc:
            raise MaintenancePolicyError(f"{field_name} must be numeric.") from exc
    raise MaintenancePolicyError(f"{field_name} must be numeric.")
