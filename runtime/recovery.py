from __future__ import annotations

import html
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import DuplicateSideEffectBlocked, RecoveryAssessmentError, RecoveryPolicyError, RuntimeStoreError
from .failure_summary import build_failure_summary
from .manifest_loader import load_manifest_by_id
from .persistence import ensure_dir, read_json, write_json_atomic
from .runtime_environment import load_runtime_profile, profile_safety_summary
from .runtime_store import validate_runtime_store
from .taskframe import TASKFRAME_STATES, json_safe, utc_now
from .taskframe_reload import load_taskframe


DEFAULT_RECOVERY_THRESHOLDS: dict[str, int] = {
    "running_stale_minutes": 10,
    "waiting_for_input_stale_hours": 24,
    "waiting_for_execute_stale_days": 7,
    "external_dependency_retry_window_minutes": 30,
}

RECOVERY_DIR_NAME = "recovery"


@dataclass(slots=True)
class RecoveryAssessment:
    frame_id: str
    manifest_id: str
    state: str
    failed_step_id: str
    recovery_status: str
    safe_to_retry: bool
    safe_to_resume: bool
    side_effect_risk: str
    reason: str
    recommended_action: str
    profile: str = "demo"
    created_at: str = ""
    updated_at: str = ""
    age_seconds: int = 0
    current_step_id: str = ""
    completed_steps: int = 0
    failed_steps: int = 0
    pending_action_count: int = 0
    executed_action_count: int = 0
    retry_attempts: int = 0
    validation_failed_count: int = 0
    idempotency_keys: list[str] = field(default_factory=list)
    recovery_blockers: list[dict[str, Any]] = field(default_factory=list)
    recovery_warnings: list[dict[str, Any]] = field(default_factory=list)
    command_suggestion: str = ""
    runtime_store_ok: bool = False
    runtime_store_issue_count: int = 0
    runtime_store_issues: list[dict[str, Any]] = field(default_factory=list)
    profile_safety: dict[str, Any] = field(default_factory=dict)
    runtime_store_validation_status: str = "unknown"
    manifest_version: int = 0
    step_status: str = ""
    failure_category: str = ""
    failure_title: str = ""
    failure_explanation: str = ""
    safe_to_retry_reason: str = ""
    safe_to_resume_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_idempotency_key(
    manifest_id: str,
    frame_id: str,
    step_id: str,
    action_type: str,
    business_ref: str,
) -> str:
    return ":".join(_normalize_idempotency_segment(part) for part in (manifest_id, frame_id, step_id, action_type, business_ref))


def ensure_pending_action_idempotency(
    frame: Any,
    pending_action: dict[str, Any],
    *,
    step_id: str | None = None,
) -> dict[str, Any]:
    frame_data = _coerce_frame(frame)
    manifest_id = str(frame_data.get("manifest_id", "") or "")
    frame_id = str(frame_data.get("frame_id", "") or "")
    action_step_id = str(step_id or pending_action.get("step_id", "") or "")
    action_type = str(pending_action.get("action_type") or pending_action.get("action") or pending_action.get("tool") or action_step_id or "side_effect")
    business_ref = str(pending_action.get("business_ref") or _infer_business_ref(pending_action) or action_step_id or pending_action.get("output_alias", "") or pending_action.get("action_id", ""))
    idempotency_key = str(pending_action.get("idempotency_key") or build_idempotency_key(manifest_id, frame_id, action_step_id or "step", action_type, business_ref))
    pending_action["business_ref"] = business_ref
    pending_action["idempotency_key"] = idempotency_key
    pending_action.setdefault("side_effect_performed", False)
    return pending_action


def verify_pending_action_safe_to_execute(
    frame: Any,
    pending_action: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
    profile_name: str | None = None,
) -> dict[str, Any]:
    frame_data = _coerce_frame(frame, runtime_data_dir=runtime_data_dir)
    action = ensure_pending_action_idempotency(frame_data, pending_action)
    profile = load_runtime_profile(profile_name=profile_name)
    blockers: list[dict[str, Any]] = []
    frame_state = str(frame_data.get("state", "") or "")
    action_status = str(action.get("status", "") or "")
    if profile.get("activation_blocked"):
        blockers.append(
            {
                "id": "profile_reserved",
                "message": str(profile.get("activation_block_reason", "Selected profile is blocked.")),
                "source": "profile",
            }
        )
    if frame_state not in {"WAITING_FOR_EXECUTE", "EXECUTING_PENDING"}:
        blockers.append(
            {
                "id": "frame_state_not_ready",
                "message": f"TaskFrame must be WAITING_FOR_EXECUTE or EXECUTING_PENDING: {frame_state}",
                "source": "runtime",
            }
        )
    if action_status != "APPROVED":
        blockers.append(
            {
                "id": "pending_action_not_approved",
                "message": f"Pending action must be APPROVED: {action_status or 'UNKNOWN'}",
                "source": "approval",
            }
        )
    if action_status == "EXECUTED" or bool(action.get("side_effect_performed", False)):
        blockers.append(
            {
                "id": "duplicate_side_effect_blocked",
                "message": "Pending action already recorded a side effect.",
                "source": "runtime",
            }
        )

    key = str(action.get("idempotency_key", "") or "")
    action_type = str(action.get("action_type") or action.get("action") or action.get("tool") or "")
    business_ref = str(action.get("business_ref") or "")
    executed_matches = _find_duplicate_executions(frame_data, key, action_type, business_ref)
    if executed_matches:
        blockers.append(
            {
                "id": "duplicate_side_effect_blocked",
                "message": "A matching side effect already executed for this frame.",
                "source": "idempotency",
                "matches": executed_matches,
            }
        )

    if blockers:
        return {
            "ok": False,
            "error_code": "DUPLICATE_SIDE_EFFECT_BLOCKED" if any(item.get("id") == "duplicate_side_effect_blocked" for item in blockers) else "RECOVERY_BLOCKED",
            "reason": blockers[0].get("message", "Pending action is not safe to execute."),
            "blockers": blockers,
            "idempotency_key": key,
            "business_ref": business_ref,
            "action_type": action_type,
        }

    return {
        "ok": True,
        "idempotency_key": key,
        "business_ref": business_ref,
        "action_type": action_type,
        "action_id": str(action.get("action_id", "") or ""),
        "frame_state": frame_state,
        "profile": str(profile.get("profile", "demo")),
        "pending_action": dict(action),
    }


def assess_recovery(
    frame: Any,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    profile_name: str | None = None,
    step_id: str | None = None,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frame_data = _coerce_frame(frame, runtime_data_dir=runtime_data_dir)
    if not frame_data:
        return _not_recoverable_assessment("", "", "UNKNOWN", "TaskFrame could not be loaded.", "Load the TaskFrame artifact and rerun the assessment.")

    runtime_root = Path(runtime_data_dir)
    runtime_root.mkdir(parents=True, exist_ok=True)
    profile = load_runtime_profile(profile_name=profile_name)
    profile_safety = profile_safety_summary(profile)
    runtime_store_validation = _safe_validate_runtime_store(runtime_root, manifest_dir=manifest_dir)
    runtime_store_ok = bool(runtime_store_validation.get("ok", False))
    runtime_store_issues = [dict(item) for item in runtime_store_validation.get("issues", []) if isinstance(item, dict)]
    failure_summary = build_failure_summary(frame_data)
    thresholds = _normalize_thresholds(thresholds)

    state = str(frame_data.get("state", "") or "")
    frame_id = str(frame_data.get("frame_id", "") or "")
    manifest_id = str(frame_data.get("manifest_id", "") or "")
    created_at = str(frame_data.get("created_at", "") or "")
    updated_at = str(frame_data.get("updated_at", "") or "")
    current_step_id = str(frame_data.get("current_step_id", "") or "")
    failed_step_id = str(step_id or failure_summary.get("failed_step_id") or current_step_id or _first_failed_step_id(frame_data))
    step = _find_step(frame_data, failed_step_id)
    step_status = str(step.get("status", "") or "") if step else ""
    step_kind = str(step.get("kind", "") or "") if step else ""
    step_retry = dict(step.get("retry", {}) or {}) if step else {}
    age_seconds = _age_seconds(created_at, updated_at)
    step_index = _step_index(frame_data, failed_step_id)
    completed_steps = _count_steps(frame_data, "COMPLETED")
    failed_steps = _count_steps(frame_data, "FAILED")
    pending_action_count = _count_actions(frame_data, "pending_actions")
    executed_action_count = _count_actions(frame_data, "executed_actions")
    validation_failed_count = _count_validation_failures(frame_data)
    retry_attempts = _count_attempts(frame_data, failed_step_id)
    side_effect_risk, idempotency_keys, side_effect_blockers = _assess_side_effect_risk(frame_data)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    manifest, manifest_version = _safe_load_manifest(manifest_id, manifest_dir)
    if not manifest:
        return _not_recoverable_assessment(frame_id, manifest_id, state, "Manifest could not be loaded.", "Fix the manifest reference before retrying or resuming.")

    if profile.get("activation_blocked"):
        blockers.append({"id": "profile_blocked", "message": str(profile.get("activation_block_reason", "Selected profile is blocked.")), "source": "profile"})
    if not runtime_store_ok:
        warnings.append({"id": "runtime_store_validation_failed", "message": "Runtime store validation reported issues.", "issues": runtime_store_issues})
    if side_effect_risk == "unknown":
        return _not_recoverable_assessment(frame_id, manifest_id, state, "Unknown side-effect status prevents safe recovery.", "Inspect the pending and executed action records before retrying.")

    duplicate_risk = _duplicate_side_effect_risk(frame_data, failed_step_id)
    if duplicate_risk:
        blockers.append(duplicate_risk)

    if validation_failed_count or state == "FAILED_VALIDATION" or failure_summary.get("failure_category") == "business_validation_failure":
        return _build_assessment(
            frame_data,
            manifest_version=manifest_version,
            recovery_status="manual_review_required",
            safe_to_retry=False,
            safe_to_resume=False,
            side_effect_risk=side_effect_risk,
            reason=str(failure_summary.get("failure_message") or failure_summary.get("failure_reason") or "Validation failed."),
            recommended_action="Review the validation failure and correct the manifest or input data before retrying.",
            profile=profile,
            profile_safety=profile_safety,
            runtime_store_validation=runtime_store_validation,
            failed_step_id=failed_step_id,
            step=step,
            step_index=step_index,
            age_seconds=age_seconds,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            pending_action_count=pending_action_count,
            executed_action_count=executed_action_count,
            validation_failed_count=validation_failed_count,
            retry_attempts=retry_attempts,
            idempotency_keys=idempotency_keys,
            blockers=blockers,
            warnings=warnings,
            step_retry=step_retry,
            state=state,
        )

    failure_category = str(failure_summary.get("failure_category", "") or "")
    failure_reason = str(failure_summary.get("failure_reason") or failure_summary.get("failure_message") or "Recovery assessment completed.")
    recommended_action = str(failure_summary.get("recommended_action") or "Inspect the run before retrying.")

    if failure_category in {"external_auth_failure", "profile_policy_block"}:
        blockers.append(
            {
                "id": failure_category,
                "message": failure_reason,
                "source": "failure_summary",
            }
        )
        return _build_assessment(
            frame_data,
            manifest_version=manifest_version,
            recovery_status="blocked",
            safe_to_retry=False,
            safe_to_resume=False,
            side_effect_risk=side_effect_risk,
            reason=failure_reason,
            recommended_action=recommended_action or "Fix credentials or profile policy before retrying.",
            profile=profile,
            profile_safety=profile_safety,
            runtime_store_validation=runtime_store_validation,
            failed_step_id=failed_step_id,
            step=step,
            step_index=step_index,
            age_seconds=age_seconds,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            pending_action_count=pending_action_count,
            executed_action_count=executed_action_count,
            validation_failed_count=validation_failed_count,
            retry_attempts=retry_attempts,
            idempotency_keys=idempotency_keys,
            blockers=blockers,
            warnings=warnings,
            step_retry=step_retry,
            state=state,
            failure_category=failure_category,
            failure_title=str(failure_summary.get("failure_title", "") or ""),
            failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
        )

    if failure_category == "runtime_store_integrity_issue" or not runtime_store_ok:
        return _build_assessment(
            frame_data,
            manifest_version=manifest_version,
            recovery_status="manual_review_required",
            safe_to_retry=False,
            safe_to_resume=False,
            side_effect_risk=side_effect_risk,
            reason=failure_reason,
            recommended_action="Repair the runtime store issues and rerun recovery assessment.",
            profile=profile,
            profile_safety=profile_safety,
            runtime_store_validation=runtime_store_validation,
            failed_step_id=failed_step_id,
            step=step,
            step_index=step_index,
            age_seconds=age_seconds,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            pending_action_count=pending_action_count,
            executed_action_count=executed_action_count,
            validation_failed_count=validation_failed_count,
            retry_attempts=retry_attempts,
            idempotency_keys=idempotency_keys,
            blockers=blockers,
            warnings=warnings,
            step_retry=step_retry,
            state=state,
            failure_category=failure_category,
            failure_title=str(failure_summary.get("failure_title", "") or ""),
            failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
        )

    if state == "RUNNING":
        if _is_stale_running(age_seconds, thresholds):
            resume_ok, resume_reason = _can_resume(frame_data, manifest, runtime_store_validation, profile, failed_step_id, side_effect_risk, duplicate_risk, step)
            status = "resumable" if resume_ok else "manual_review_required"
            return _build_assessment(
                frame_data,
                manifest_version=manifest_version,
                recovery_status=status,
                safe_to_retry=False,
                safe_to_resume=resume_ok,
                side_effect_risk=side_effect_risk,
                reason=resume_reason,
                recommended_action="Use the dry-run resume command after reviewing the stale run." if resume_ok else "Inspect the stale run before resuming.",
                profile=profile,
                profile_safety=profile_safety,
                runtime_store_validation=runtime_store_validation,
                failed_step_id=failed_step_id,
                step=step,
                step_index=step_index,
                age_seconds=age_seconds,
                completed_steps=completed_steps,
                failed_steps=failed_steps,
                pending_action_count=pending_action_count,
                executed_action_count=executed_action_count,
                validation_failed_count=validation_failed_count,
                retry_attempts=retry_attempts,
                idempotency_keys=idempotency_keys,
                blockers=blockers,
                warnings=warnings,
                step_retry=step_retry,
                state=state,
                failure_category=failure_category,
                failure_title=str(failure_summary.get("failure_title", "") or ""),
                failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
            )
        resume_ok, resume_reason = _can_resume(frame_data, manifest, runtime_store_validation, profile, failed_step_id, side_effect_risk, duplicate_risk, step)
        return _build_assessment(
            frame_data,
            manifest_version=manifest_version,
            recovery_status="resumable" if resume_ok else "manual_review_required",
            safe_to_retry=False,
            safe_to_resume=resume_ok,
            side_effect_risk=side_effect_risk,
            reason=resume_reason,
            recommended_action="Use the dry-run resume command when the current step is safe to continue." if resume_ok else "Inspect the current step outputs before resuming.",
            profile=profile,
            profile_safety=profile_safety,
            runtime_store_validation=runtime_store_validation,
            failed_step_id=failed_step_id,
            step=step,
            step_index=step_index,
            age_seconds=age_seconds,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            pending_action_count=pending_action_count,
            executed_action_count=executed_action_count,
            validation_failed_count=validation_failed_count,
            retry_attempts=retry_attempts,
            idempotency_keys=idempotency_keys,
            blockers=blockers,
            warnings=warnings,
            step_retry=step_retry,
            state=state,
            failure_category=failure_category,
            failure_title=str(failure_summary.get("failure_title", "") or ""),
            failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
        )

    if state == "WAITING_FOR_EXECUTE":
        resume_ok, resume_reason = _can_resume(frame_data, manifest, runtime_store_validation, profile, failed_step_id, side_effect_risk, duplicate_risk, step)
        return _build_assessment(
            frame_data,
            manifest_version=manifest_version,
            recovery_status="resumable" if resume_ok else "manual_review_required",
            safe_to_retry=False,
            safe_to_resume=resume_ok,
            side_effect_risk=side_effect_risk,
            reason=resume_reason,
            recommended_action="Use the dry-run resume command to continue from the last safe point." if resume_ok else "Inspect pending approvals before resuming.",
            profile=profile,
            profile_safety=profile_safety,
            runtime_store_validation=runtime_store_validation,
            failed_step_id=failed_step_id,
            step=step,
            step_index=step_index,
            age_seconds=age_seconds,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            pending_action_count=pending_action_count,
            executed_action_count=executed_action_count,
            validation_failed_count=validation_failed_count,
            retry_attempts=retry_attempts,
            idempotency_keys=idempotency_keys,
            blockers=blockers,
            warnings=warnings,
            step_retry=step_retry,
            state=state,
            failure_category=failure_category,
            failure_title=str(failure_summary.get("failure_title", "") or ""),
            failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
        )

    if state == "FAILED_EXECUTION":
        retry_ok, retry_reason = _can_retry(frame_data, step, failure_summary, side_effect_risk)
        if retry_ok:
            return _build_assessment(
                frame_data,
                manifest_version=manifest_version,
                recovery_status="retryable",
                safe_to_retry=True,
                safe_to_resume=False,
                side_effect_risk=side_effect_risk,
                reason=retry_reason,
                recommended_action=f"Use the dry-run retry command for step {failed_step_id}." if failed_step_id else "Use the dry-run retry command after reviewing the failed step.",
                profile=profile,
                profile_safety=profile_safety,
                runtime_store_validation=runtime_store_validation,
                failed_step_id=failed_step_id,
                step=step,
                step_index=step_index,
                age_seconds=age_seconds,
                completed_steps=completed_steps,
                failed_steps=failed_steps,
                pending_action_count=pending_action_count,
                executed_action_count=executed_action_count,
                validation_failed_count=validation_failed_count,
                retry_attempts=retry_attempts,
                idempotency_keys=idempotency_keys,
                blockers=blockers,
                warnings=warnings,
                step_retry=step_retry,
                state=state,
                failure_category=failure_category,
                failure_title=str(failure_summary.get("failure_title", "") or ""),
                failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
                command_suggestion=f"taskframe recover retry-step {frame_id} --step {failed_step_id} --dry-run" if frame_id else "",
            )
        if side_effect_risk in {"staged", "executed"}:
            status = "blocked" if side_effect_risk == "executed" else "manual_review_required"
            reason = "A side effect was already staged or executed, so retry is not automatic."
            return _build_assessment(
                frame_data,
                manifest_version=manifest_version,
                recovery_status=status,
                safe_to_retry=False,
                safe_to_resume=False,
                side_effect_risk=side_effect_risk,
                reason=reason,
                recommended_action="Inspect the pending or executed side-effect records before retrying.",
                profile=profile,
                profile_safety=profile_safety,
                runtime_store_validation=runtime_store_validation,
                failed_step_id=failed_step_id,
                step=step,
                step_index=step_index,
                age_seconds=age_seconds,
                completed_steps=completed_steps,
                failed_steps=failed_steps,
                pending_action_count=pending_action_count,
                executed_action_count=executed_action_count,
                validation_failed_count=validation_failed_count,
                retry_attempts=retry_attempts,
                idempotency_keys=idempotency_keys,
                blockers=blockers,
                warnings=warnings,
                step_retry=step_retry,
                state=state,
                failure_category=failure_category,
                failure_title=str(failure_summary.get("failure_title", "") or ""),
                failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
            )
        return _build_assessment(
            frame_data,
            manifest_version=manifest_version,
            recovery_status="manual_review_required",
            safe_to_retry=False,
            safe_to_resume=False,
            side_effect_risk=side_effect_risk,
            reason=retry_reason,
            recommended_action="Review the failed step and recovery blockers before retrying.",
            profile=profile,
            profile_safety=profile_safety,
            runtime_store_validation=runtime_store_validation,
            failed_step_id=failed_step_id,
            step=step,
            step_index=step_index,
            age_seconds=age_seconds,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            pending_action_count=pending_action_count,
            executed_action_count=executed_action_count,
            validation_failed_count=validation_failed_count,
            retry_attempts=retry_attempts,
            idempotency_keys=idempotency_keys,
            blockers=blockers,
            warnings=warnings,
            step_retry=step_retry,
            state=state,
            failure_category=failure_category,
            failure_title=str(failure_summary.get("failure_title", "") or ""),
            failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
        )

    return _build_assessment(
        frame_data,
        manifest_version=manifest_version,
        recovery_status="not_recoverable",
        safe_to_retry=False,
        safe_to_resume=False,
        side_effect_risk=side_effect_risk,
        reason=failure_reason if failure_reason else "No recovery action is needed.",
        recommended_action=recommended_action or "No recovery action is needed.",
        profile=profile,
        profile_safety=profile_safety,
        runtime_store_validation=runtime_store_validation,
        failed_step_id=failed_step_id,
        step=step,
        step_index=step_index,
        age_seconds=age_seconds,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        pending_action_count=pending_action_count,
        executed_action_count=executed_action_count,
        validation_failed_count=validation_failed_count,
        retry_attempts=retry_attempts,
        idempotency_keys=idempotency_keys,
        blockers=blockers,
        warnings=warnings,
        step_retry=step_retry,
        state=state,
        failure_category=failure_category,
        failure_title=str(failure_summary.get("failure_title", "") or ""),
        failure_explanation=str(failure_summary.get("operator_explanation", "") or ""),
    )


def generate_recovery_report(
    frame: Any,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    profile_name: str | None = None,
    step_id: str | None = None,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assessment = assess_recovery(
        frame,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        profile_name=profile_name,
        step_id=step_id,
        thresholds=thresholds,
    )
    frame_id = str(assessment.get("frame_id", "") or "unknown_frame")
    recovery_dir = ensure_dir(Path(runtime_data_dir) / RECOVERY_DIR_NAME)
    timestamp = _safe_timestamp(utc_now())
    json_path = recovery_dir / f"recovery_assessment_{_safe_filename(frame_id)}.json"
    md_path = recovery_dir / f"recovery_assessment_{_safe_filename(frame_id)}.md"
    payload = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "runtime_data_dir": str(Path(runtime_data_dir)),
        "profile": assessment.get("profile", "demo"),
        "frame": _coerce_frame(frame, runtime_data_dir=runtime_data_dir),
        "assessment": assessment,
        "runtime_store_validation": assessment.get("runtime_store_validation_status", ""),
        "runtime_store_issues": assessment.get("runtime_store_issues", []),
        "timestamp_key": timestamp,
    }
    write_json_atomic(json_path, json_safe(payload))
    md_path.write_text(render_recovery_report_markdown(payload), encoding="utf-8")
    return {
        "ok": True,
        "frame_id": frame_id,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "assessment": assessment,
        "payload": payload,
    }


def render_recovery_report_markdown(report: dict[str, Any]) -> str:
    assessment = dict(report.get("assessment", {}) or {})
    frame = dict(report.get("frame", {}) or {})
    steps = _steps_for_frame(frame)
    lines = [
        "# Recovery Assessment",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Frame ID | {assessment.get('frame_id', '')} |",
        f"| Manifest ID | {assessment.get('manifest_id', '')} |",
        f"| State | {assessment.get('state', '')} |",
        f"| Recovery Status | {assessment.get('recovery_status', '')} |",
        f"| Safe to Retry | {str(assessment.get('safe_to_retry', False)).lower()} |",
        f"| Safe to Resume | {str(assessment.get('safe_to_resume', False)).lower()} |",
        f"| Side-effect Risk | {assessment.get('side_effect_risk', '')} |",
        f"| Recommended Action | {assessment.get('recommended_action', '')} |",
        f"| Command Suggestion | {assessment.get('command_suggestion', '')} |",
        "",
        "## Frame State",
        "",
        f"- Created At: {frame.get('created_at', '')}",
        f"- Updated At: {frame.get('updated_at', '')}",
        f"- Current Step: {assessment.get('current_step_id', '')}",
        f"- Failed Step: {assessment.get('failed_step_id', '')}",
        f"- Completed Steps: {assessment.get('completed_steps', 0)}",
        f"- Failed Steps: {assessment.get('failed_steps', 0)}",
        f"- Pending Actions: {assessment.get('pending_action_count', 0)}",
        f"- Executed Actions: {assessment.get('executed_action_count', 0)}",
        f"- Retry Attempts: {assessment.get('retry_attempts', 0)}",
        "",
        "## Idempotency Keys",
    ]
    idempotency_keys = assessment.get("idempotency_keys", []) or []
    if not idempotency_keys:
        lines.append("- None")
    else:
        lines.extend(f"- {key}" for key in idempotency_keys)
    lines.extend(
        [
            "",
            "## Recovery Classification",
            "",
            f"- Status: {assessment.get('recovery_status', '')}",
            f"- Reason: {assessment.get('reason', '')}",
            f"- Failure Category: {assessment.get('failure_category', '')}",
            f"- Failure Title: {assessment.get('failure_title', '')}",
            f"- Failure Explanation: {assessment.get('failure_explanation', '')}",
            f"- Profile: {assessment.get('profile', '')}",
            f"- Runtime Store OK: {str(assessment.get('runtime_store_ok', False)).lower()}",
            "",
            "## Pending Actions",
        ]
    )
    pending_actions = [item for item in frame.get("pending_actions", []) if isinstance(item, dict)]
    if not pending_actions:
        lines.append("No pending actions.")
    else:
        for action in pending_actions:
            lines.append(
                f"- {action.get('action_id', '')} | {action.get('status', '')} | {action.get('tool', '')} | {action.get('idempotency_key', '')} | {action.get('business_ref', '')}"
            )
    lines.extend(["", "## Retry Attempts"])
    attempts = [item for item in frame.get("attempts", []) if isinstance(item, dict)]
    if not attempts:
        lines.append("No retry attempts recorded.")
    else:
        for attempt in attempts:
            if assessment.get("failed_step_id") and str(attempt.get("step_id", "")) != str(assessment.get("failed_step_id", "")):
                continue
            lines.append(
                f"- attempt {attempt.get('attempt', '')} | status={attempt.get('status', '')} | retryable={str(attempt.get('retryable', False)).lower()} | error={attempt.get('message', '')}"
            )
    lines.extend(
        [
            "",
            "## Previous Executions",
        ]
    )
    executed_actions = [item for item in frame.get("executed_actions", []) if isinstance(item, dict)]
    if not executed_actions:
        lines.append("No executed actions.")
    else:
        for action in executed_actions:
            lines.append(
                f"- {action.get('action_id', '')} | {action.get('status', '')} | {action.get('tool', '')} | {action.get('idempotency_key', '')} | {action.get('business_ref', '')}"
            )
    lines.extend(
        [
            "",
            "## Runtime Store",
            "",
            f"- Validation Status: {assessment.get('runtime_store_validation_status', '')}",
            f"- Validation OK: {str(assessment.get('runtime_store_ok', False)).lower()}",
            f"- Issue Count: {assessment.get('runtime_store_issue_count', 0)}",
            "",
            "## Profile Safety",
            "",
            f"- Demo Safe: {str((assessment.get('profile_safety') or {}).get('safe_for_demo', False)).lower()}",
            f"- Pilot Safe: {str((assessment.get('profile_safety') or {}).get('safe_for_pilot', False)).lower()}",
            f"- Release Safe: {str((assessment.get('profile_safety') or {}).get('safe_for_release', False)).lower()}",
        ]
    )
    return "\n".join(lines)


def write_recovery_report(
    frame: Any,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    profile_name: str | None = None,
    step_id: str | None = None,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return generate_recovery_report(
        frame,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        profile_name=profile_name,
        step_id=step_id,
        thresholds=thresholds,
    )


def recover_assess(
    frame_id: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    profile_name: str | None = None,
    step_id: str | None = None,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frame = load_taskframe(frame_id, runtime_data_dir)
    report = generate_recovery_report(
        frame,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        profile_name=profile_name,
        step_id=step_id,
        thresholds=thresholds,
    )
    payload = dict(report.get("assessment", {}) or {})
    payload["report_path"] = report.get("json_path", "")
    payload["report_markdown_path"] = report.get("markdown_path", "")
    payload["dry_run"] = True
    return payload


def recover_retry_step(
    frame_id: str,
    *,
    step_id: str,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    profile_name: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    if not dry_run:
        raise RecoveryPolicyError("Live retry is not enabled in this spec.")
    frame = load_taskframe(frame_id, runtime_data_dir)
    report = generate_recovery_report(
        frame,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        profile_name=profile_name,
        step_id=step_id,
    )
    payload = dict(report.get("assessment", {}) or {})
    payload["step_id"] = step_id
    payload["dry_run"] = True
    payload["report_path"] = report.get("json_path", "")
    payload["report_markdown_path"] = report.get("markdown_path", "")
    if payload.get("recovery_status") == "retryable":
        payload["command_suggestion"] = f"taskframe recover retry-step {frame_id} --step {step_id} --dry-run"
    return payload


def recover_resume(
    frame_id: str,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    manifest_dir: str | Path = "manifests",
    profile_name: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    if not dry_run:
        raise RecoveryPolicyError("Live resume is not enabled in this spec.")
    frame = load_taskframe(frame_id, runtime_data_dir)
    report = generate_recovery_report(
        frame,
        runtime_data_dir=runtime_data_dir,
        manifest_dir=manifest_dir,
        profile_name=profile_name,
    )
    payload = dict(report.get("assessment", {}) or {})
    payload["dry_run"] = True
    payload["report_path"] = report.get("json_path", "")
    payload["report_markdown_path"] = report.get("markdown_path", "")
    if payload.get("recovery_status") == "resumable":
        payload["command_suggestion"] = f"taskframe recover resume {frame_id} --dry-run"
    return payload


def _build_assessment(
    frame_data: dict[str, Any],
    *,
    manifest_version: int,
    recovery_status: str,
    safe_to_retry: bool,
    safe_to_resume: bool,
    side_effect_risk: str,
    reason: str,
    recommended_action: str,
    profile: dict[str, Any],
    profile_safety: dict[str, Any],
    runtime_store_validation: dict[str, Any],
    failed_step_id: str,
    step: dict[str, Any] | None,
    step_index: int,
    age_seconds: int,
    completed_steps: int,
    failed_steps: int,
    pending_action_count: int,
    executed_action_count: int,
    validation_failed_count: int,
    retry_attempts: int,
    idempotency_keys: list[str],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    step_retry: dict[str, Any],
    state: str,
    failure_category: str = "",
    failure_title: str = "",
    failure_explanation: str = "",
    command_suggestion: str = "",
) -> dict[str, Any]:
    frame_id = str(frame_data.get("frame_id", "") or "")
    manifest_id = str(frame_data.get("manifest_id", "") or "")
    created_at = str(frame_data.get("created_at", "") or "")
    updated_at = str(frame_data.get("updated_at", "") or "")
    current_step_id = str(frame_data.get("current_step_id", "") or "")
    if not command_suggestion:
        if recovery_status == "retryable" and failed_step_id:
            command_suggestion = f"taskframe recover retry-step {frame_id} --step {failed_step_id} --dry-run"
        elif recovery_status == "resumable" and frame_id:
            command_suggestion = f"taskframe recover resume {frame_id} --dry-run"
    assessment = RecoveryAssessment(
        frame_id=frame_id,
        manifest_id=manifest_id,
        state=state,
        failed_step_id=failed_step_id,
        recovery_status=recovery_status,
        safe_to_retry=safe_to_retry,
        safe_to_resume=safe_to_resume,
        side_effect_risk=side_effect_risk,
        reason=reason,
        recommended_action=recommended_action,
        profile=str(profile.get("profile", "demo")),
        created_at=created_at,
        updated_at=updated_at,
        age_seconds=age_seconds,
        current_step_id=current_step_id,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        pending_action_count=pending_action_count,
        executed_action_count=executed_action_count,
        retry_attempts=retry_attempts,
        validation_failed_count=validation_failed_count,
        idempotency_keys=list(dict.fromkeys(idempotency_keys)),
        recovery_blockers=blockers,
        recovery_warnings=warnings,
        command_suggestion=command_suggestion,
        runtime_store_ok=bool(runtime_store_validation.get("ok", False)),
        runtime_store_issue_count=len(runtime_store_validation.get("issues", []) or []),
        runtime_store_issues=[dict(item) for item in runtime_store_validation.get("issues", []) if isinstance(item, dict)],
        profile_safety=profile_safety,
        runtime_store_validation_status="ok" if runtime_store_validation.get("ok", False) else "warning",
        manifest_version=manifest_version,
        step_status=str(step.get("status", "") or "") if step else "",
        failure_category=failure_category,
        failure_title=failure_title,
        failure_explanation=failure_explanation,
        safe_to_retry_reason="retryable" if safe_to_retry else "retry not safe",
        safe_to_resume_reason="resumable" if safe_to_resume else "resume not safe",
    )
    payload = assessment.to_dict()
    payload["command_suggestion"] = command_suggestion
    payload["step_retry_policy"] = step_retry
    payload["step_index"] = step_index
    payload["side_effect_risk"] = side_effect_risk
    return json_safe(payload)


def _not_recoverable_assessment(frame_id: str, manifest_id: str, state: str, reason: str, recommended_action: str) -> dict[str, Any]:
    return json_safe(
        {
            "frame_id": frame_id,
            "manifest_id": manifest_id,
            "state": state,
            "failed_step_id": "",
            "recovery_status": "not_recoverable",
            "safe_to_retry": False,
            "safe_to_resume": False,
            "side_effect_risk": "unknown",
            "reason": reason,
            "recommended_action": recommended_action,
            "profile": "demo",
            "created_at": "",
            "updated_at": "",
            "age_seconds": 0,
            "current_step_id": "",
            "completed_steps": 0,
            "failed_steps": 0,
            "pending_action_count": 0,
            "executed_action_count": 0,
            "retry_attempts": 0,
            "validation_failed_count": 0,
            "idempotency_keys": [],
            "recovery_blockers": [],
            "recovery_warnings": [],
            "command_suggestion": "",
            "runtime_store_ok": False,
            "runtime_store_issue_count": 0,
            "runtime_store_issues": [],
            "profile_safety": {},
            "runtime_store_validation_status": "unknown",
            "manifest_version": 0,
            "step_status": "",
            "failure_category": "",
            "failure_title": "",
            "failure_explanation": "",
            "safe_to_retry_reason": "retry not safe",
            "safe_to_resume_reason": "resume not safe",
        }
    )


def _can_retry(frame_data: dict[str, Any], step: dict[str, Any] | None, failure_summary: dict[str, Any], side_effect_risk: str) -> tuple[bool, str]:
    if not step:
        return False, "A failed step could not be identified."
    if side_effect_risk != "none":
        return False, "A side effect was already staged or executed."
    if str(step.get("kind", "") or "") in {"validate"}:
        return False, "Validation steps are not auto-retried."
    failure_category = str(failure_summary.get("failure_category", "") or "")
    if failure_category == "business_validation_failure":
        return False, "Business validation failures require manual review."
    failure_category = str(failure_summary.get("failure_category", "") or "")
    error_info = {
        "error_type": failure_category or str(failure_summary.get("failure_type", "") or "UnknownError"),
        "message": str(failure_summary.get("failure_message", "") or ""),
        "tag": _error_tag_from_failure_summary(failure_summary),
    }
    from .retry_policy import should_retry_step

    if failure_category not in {"external_dependency_unavailable", "tool_execution_failure", "unknown_failure"} and not should_retry_step(step, error_info):
        return False, "Retry policy does not allow this failure to retry."
    if not should_retry_step(step, error_info):
        return False, "Retry policy does not allow this failure to retry."
    return True, str(failure_summary.get("recommended_action", "") or "Retry is allowed.")


def _can_resume(
    frame_data: dict[str, Any],
    manifest: Any,
    runtime_store_validation: dict[str, Any],
    profile: dict[str, Any],
    failed_step_id: str,
    side_effect_risk: str,
    duplicate_risk: dict[str, Any] | None,
    step: dict[str, Any] | None,
) -> tuple[bool, str]:
    if profile.get("activation_blocked"):
        return False, str(profile.get("activation_block_reason", "Selected profile is blocked."))
    if not runtime_store_validation.get("ok", False):
        return False, "Runtime store validation must pass before resuming."
    if duplicate_risk:
        return False, "Duplicate side effect risk must be resolved before resuming."
    if side_effect_risk == "unknown":
        return False, "Unknown side-effect status prevents resume."
    if not failed_step_id and not str(frame_data.get("current_step_id", "") or ""):
        return False, "A current step could not be identified."
    if not _previous_outputs_present(frame_data, failed_step_id):
        return False, "Previous completed steps are missing required outputs."
    if manifest is None:
        return False, "The manifest is required to resume."
    if step and str(step.get("status", "") or "") in {"FAILED", "RUNNING", "STAGED", "COMPLETED"}:
        return True, "The frame is ready to continue from the last safe point."
    return True, "The frame is ready to continue from the last safe point."


def _duplicate_side_effect_risk(frame_data: dict[str, Any], failed_step_id: str) -> dict[str, Any] | None:
    pending_actions = [item for item in frame_data.get("pending_actions", []) if isinstance(item, dict)]
    executed_actions = [item for item in frame_data.get("executed_actions", []) if isinstance(item, dict)]
    for action in pending_actions:
        normalized = ensure_pending_action_idempotency(frame_data, action, step_id=str(action.get("step_id", "") or failed_step_id))
        if str(normalized.get("status", "")).upper() not in {"APPROVED", "EXECUTING", "EXECUTED"}:
            continue
        matches = _find_duplicate_executions(frame_data, str(normalized.get("idempotency_key", "")), str(normalized.get("action_type", "") or normalized.get("action", "") or normalized.get("tool", "")), str(normalized.get("business_ref", "")))
        if matches:
            return {
                "id": "duplicate_side_effect_blocked",
                "message": "Duplicate side effect risk detected.",
                "source": "idempotency",
                "matches": matches,
            }
    for action in executed_actions:
        normalized = ensure_pending_action_idempotency(frame_data, action, step_id=str(action.get("step_id", "") or failed_step_id))
        if str(normalized.get("status", "")).upper() == "EXECUTED":
            return {
                "id": "duplicate_side_effect_blocked",
                "message": "An executed side effect already exists for this frame.",
                "source": "executed_actions",
                "matches": [dict(normalized)],
            }
    return None


def _find_duplicate_executions(frame_data: dict[str, Any], idempotency_key: str, action_type: str, business_ref: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for collection_name in ("executed_actions", "pending_actions"):
        for item in frame_data.get(collection_name, []) or []:
            if not isinstance(item, dict):
                continue
            normalized = ensure_pending_action_idempotency(frame_data, item, step_id=str(item.get("step_id", "") or "step"))
            status = str(normalized.get("status", "") or "").upper()
            if idempotency_key and str(normalized.get("idempotency_key", "")) == idempotency_key and status == "EXECUTED":
                matches.append(dict(normalized))
                continue
            if status == "EXECUTED" and action_type and business_ref:
                if str(normalized.get("action_type", "") or normalized.get("action", "") or normalized.get("tool", "")) == action_type and str(normalized.get("business_ref", "")) == business_ref:
                    matches.append(dict(normalized))
    return matches


def _previous_outputs_present(frame_data: dict[str, Any], failed_step_id: str) -> bool:
    steps = _steps_for_frame(frame_data)
    if not steps:
        return True
    stop_index = _step_index(frame_data, failed_step_id)
    if stop_index < 0:
        stop_index = len(steps)
    outputs = dict(frame_data.get("outputs", {}) or {})
    for step in steps[:stop_index]:
        if str(step.get("status", "")).upper() != "COMPLETED":
            continue
        output_alias = str(step.get("output_alias", "") or "")
        if output_alias and output_alias not in outputs:
            return False
    return True


def _assess_side_effect_risk(frame_data: dict[str, Any]) -> tuple[str, list[str], list[dict[str, Any]]]:
    actions = [item for item in frame_data.get("pending_actions", []) if isinstance(item, dict)] + [item for item in frame_data.get("executed_actions", []) if isinstance(item, dict)]
    if not actions:
        return "none", [], []
    keys: list[str] = []
    blockers: list[dict[str, Any]] = []
    staged = False
    executed = False
    unknown = False
    for action in actions:
        normalized = ensure_pending_action_idempotency(frame_data, action, step_id=str(action.get("step_id", "") or "step"))
        key = str(normalized.get("idempotency_key", "") or "")
        if key:
            keys.append(key)
        status = str(normalized.get("status", "") or "").upper()
        if status == "EXECUTED" or bool(normalized.get("side_effect_performed", False)):
            executed = True
        elif status in {"PENDING_APPROVAL", "APPROVED", "EXECUTING"}:
            staged = True
        else:
            unknown = True
            blockers.append({"id": "unknown_side_effect_status", "message": f"Unknown pending action status: {status}", "source": "pending_actions", "action_id": normalized.get("action_id", "")})
    if executed:
        return "executed", keys, blockers
    if staged:
        return "staged", keys, blockers
    if unknown:
        return "unknown", keys, blockers
    return "none", keys, blockers


def _safe_validate_runtime_store(runtime_root: Path, *, manifest_dir: str | Path) -> dict[str, Any]:
    try:
        return validate_runtime_store(runtime_root, manifest_dir=manifest_dir)
    except RuntimeStoreError as exc:
        return {
            "ok": False,
            "schema_version": 1,
            "runtime_data_dir": str(runtime_root),
            "manifest_dir": str(Path(manifest_dir)),
            "required_folders": {},
            "artifact_counts": {},
            "taskframes": [],
            "approval_packs": [],
            "reports": [],
            "evidence": [],
            "tool_health": [],
            "indexes": [],
            "cleanup": [],
            "migrations": [],
            "orphaned_artifacts": [],
            "corrupted_paths": [],
            "issues": [
                {
                    "category": "runtime_store_error",
                    "severity": "error",
                    "path": str(runtime_root),
                    "message": str(exc),
                    "recommended_action": "Repair the runtime store before retrying or resuming.",
                }
            ],
            "index_rebuildable": False,
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "ok": False,
            "schema_version": 1,
            "runtime_data_dir": str(runtime_root),
            "manifest_dir": str(Path(manifest_dir)),
            "required_folders": {},
            "artifact_counts": {},
            "taskframes": [],
            "approval_packs": [],
            "reports": [],
            "evidence": [],
            "tool_health": [],
            "indexes": [],
            "cleanup": [],
            "migrations": [],
            "orphaned_artifacts": [],
            "corrupted_paths": [],
            "issues": [
                {
                    "category": "runtime_store_error",
                    "severity": "error",
                    "path": str(runtime_root),
                    "message": str(exc),
                    "recommended_action": "Repair the runtime store before retrying or resuming.",
                }
            ],
            "index_rebuildable": False,
        }


def _safe_load_manifest(manifest_id: str, manifest_dir: str | Path) -> tuple[dict[str, Any] | None, int]:
    if not manifest_id:
        return None, 0
    try:
        manifest = load_manifest_by_id(manifest_id, manifest_dir)
    except Exception:
        return None, 0
    return _manifest_to_dict(manifest), int(getattr(manifest, "version", 0) or 0)


def _manifest_to_dict(manifest: Any) -> dict[str, Any]:
    if manifest is None:
        return {}
    if isinstance(manifest, dict):
        return dict(manifest)
    if is_dataclass(manifest):
        return dict(asdict(manifest))
    return dict(getattr(manifest, "__dict__", {}) or {})


def _coerce_frame(frame: Any, *, runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    if frame is None:
        return {}
    if isinstance(frame, dict):
        return dict(frame)
    if isinstance(frame, str):
        try:
            loaded = load_taskframe(frame, runtime_data_dir)
        except Exception:
            return {}
        return _coerce_frame(loaded, runtime_data_dir=runtime_data_dir)
    if is_dataclass(frame):
        return dict(asdict(frame))
    if hasattr(frame, "frame_id") and hasattr(frame, "manifest_id"):
        try:
            return dict(frame.__dict__)
        except Exception:
            return {}
    return {}


def _steps_for_frame(frame_data: dict[str, Any]) -> list[dict[str, Any]]:
    steps = frame_data.get("steps", [])
    return [item for item in steps if isinstance(item, dict)]


def _find_step(frame_data: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    if not step_id:
        return None
    for step in _steps_for_frame(frame_data):
        if str(step.get("step_id") or step.get("id") or "") == step_id:
            return dict(step)
    return None


def _step_index(frame_data: dict[str, Any], step_id: str) -> int:
    if not step_id:
        return -1
    for index, step in enumerate(_steps_for_frame(frame_data)):
        if str(step.get("step_id") or step.get("id") or "") == step_id:
            return index
    return -1


def _first_failed_step_id(frame_data: dict[str, Any]) -> str:
    for step in _steps_for_frame(frame_data):
        status = str(step.get("status", "") or "").upper()
        if status.startswith("FAILED"):
            return str(step.get("step_id") or step.get("id") or "")
    return ""


def _count_steps(frame_data: dict[str, Any], status: str) -> int:
    return sum(1 for step in _steps_for_frame(frame_data) if str(step.get("status", "") or "").upper() == status.upper())


def _count_actions(frame_data: dict[str, Any], key: str) -> int:
    actions = frame_data.get(key, [])
    return len([item for item in actions if isinstance(item, dict)])


def _count_validation_failures(frame_data: dict[str, Any]) -> int:
    return sum(1 for item in frame_data.get("validations", []) if isinstance(item, dict) and item.get("ok") is False)


def _count_attempts(frame_data: dict[str, Any], step_id: str) -> int:
    attempts = [item for item in frame_data.get("attempts", []) if isinstance(item, dict)]
    if not step_id:
        return len(attempts)
    return sum(1 for item in attempts if str(item.get("step_id", "") or "") == step_id)


def _normalize_thresholds(thresholds: dict[str, Any] | None) -> dict[str, int]:
    normalized = dict(DEFAULT_RECOVERY_THRESHOLDS)
    if thresholds:
        for key, value in thresholds.items():
            if key in normalized and isinstance(value, (int, float)) and not isinstance(value, bool):
                normalized[key] = int(value)
    return normalized


def _is_stale_running(age_seconds: int, thresholds: dict[str, int]) -> bool:
    return age_seconds >= int(thresholds.get("running_stale_minutes", DEFAULT_RECOVERY_THRESHOLDS["running_stale_minutes"])) * 60


def _age_seconds(created_at: str, updated_at: str) -> int:
    dt = _parse_timestamp(updated_at) or _parse_timestamp(created_at)
    if dt is None:
        return 0
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _infer_business_ref(action: dict[str, Any]) -> str:
    for key in ("business_ref", "invoice_ref", "po_id", "order_id", "sku", "message_id", "customer_id", "subject", "recipient", "to", "chat", "title", "body", "reply", "name"):
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    args = action.get("args", {})
    if isinstance(args, dict):
        for key in ("invoice_ref", "po_id", "order_id", "sku", "message_id", "customer_id", "subject", "recipient", "to", "chat", "title", "body", "reply", "name"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _normalize_idempotency_segment(value: str) -> str:
    text = str(value or "").strip()
    return text.replace(":", "_") or "unknown"


def _safe_timestamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace(".", "").replace("Z", "Z")


def _safe_filename(value: str) -> str:
    text = str(value or "").strip()
    safe = [ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text]
    return "".join(safe) or "frame"


def _error_tag_from_failure_summary(failure_summary: dict[str, Any]) -> str:
    category = str(failure_summary.get("failure_category", "") or "")
    if category in {"business_validation_failure"}:
        return "validation"
    if category in {"external_auth_failure", "external_dependency_unavailable"}:
        return "transient"
    if category in {"tool_execution_failure"}:
        return "transient"
    return "unknown"


DUPLICATE_SIDE_EFFECT_BLOCKED = "DUPLICATE_SIDE_EFFECT_BLOCKED"


def build_recovery_assessment_stub() -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "assessment_type": "recovery_assessment_stub",
        "description": "Recovery is operator-initiated via dry-run planning. No autonomous recovery daemon.",
        "capabilities": [
            "assess_recovery",
            "retry_step_dry_run",
            "resume_dry_run",
            "idempotency_key_generation",
            "duplicate_side_effect_blocking",
        ],
        "idempotency_constant": DUPLICATE_SIDE_EFFECT_BLOCKED,
        "ok": True,
    }
