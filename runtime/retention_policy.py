from __future__ import annotations

from copy import deepcopy
from typing import Any

from .errors import CleanupConfirmationError, CleanupPolicyError, RetentionPolicyError


DEFAULT_RETENTION_POLICY: dict[str, Any] = {
    "schema_version": 1,
    "mode": "derived_artifacts_only",
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

SUPPORTED_CLEANUP_MODES = {
    "derived_artifacts_only",
    "reports_only",
    "indexes_only",
    "approval_packs_only",
    "temp_only",
    "run_dirs",
    "all",
}

_BOOL_FIELDS = {
    "dry_run",
    "confirm_cleanup",
    "delete_reports",
    "delete_artifact_index",
    "delete_temp_files",
    "delete_empty_dirs",
    "delete_expired_approval_packs",
    "delete_run_dirs",
    "protect_live_execution",
    "protect_pending_actions",
    "protect_ready_approval_packs",
}

_AGE_FIELDS = {"min_age_days", "max_report_age_days", "max_temp_age_days", "max_approval_pack_age_days"}


def normalize_retention_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    if policy is None:
        return deepcopy(DEFAULT_RETENTION_POLICY)
    if not isinstance(policy, dict):
        raise RetentionPolicyError("Policy must be a dict or None.")
    normalized = deepcopy(DEFAULT_RETENTION_POLICY)
    normalized.update(policy)
    return normalized


def validate_retention_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        raise RetentionPolicyError("Policy must be a dict.")

    schema_version = policy.get("schema_version")
    if schema_version != 1:
        raise RetentionPolicyError("schema_version must be 1.")

    mode = policy.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise CleanupPolicyError("mode must be a non-empty string.")
    mode = mode.strip()
    if mode not in SUPPORTED_CLEANUP_MODES:
        raise CleanupPolicyError(f"Unsupported cleanup mode: {mode}")
    if mode in {"run_dirs", "all"}:
        raise CleanupPolicyError("Run directory cleanup is not implemented in Spec 023.")

    dry_run = policy.get("dry_run")
    confirm_cleanup = policy.get("confirm_cleanup")
    if not isinstance(dry_run, bool):
        raise RetentionPolicyError("dry_run must be a bool.")
    if not isinstance(confirm_cleanup, bool):
        raise RetentionPolicyError("confirm_cleanup must be a bool.")
    if not dry_run and not confirm_cleanup:
        raise CleanupConfirmationError("Destructive cleanup requires confirm_cleanup=true.")

    for key in _BOOL_FIELDS - {"dry_run", "confirm_cleanup"}:
        if not isinstance(policy.get(key), bool):
            raise RetentionPolicyError(f"{key} must be a bool.")

    for key in _AGE_FIELDS:
        value = policy.get(key)
        if not isinstance(value, (int, float)):
            raise RetentionPolicyError(f"{key} must be a non-negative number.")
        if value < 0:
            raise RetentionPolicyError(f"{key} must be a non-negative number.")

    protect_states = policy.get("protect_states")
    if not isinstance(protect_states, list) or not all(isinstance(item, str) for item in protect_states):
        raise RetentionPolicyError("protect_states must be a list[str].")

    if policy.get("delete_run_dirs") is True:
        raise CleanupPolicyError("Run directory cleanup is not implemented in Spec 023.")


def is_destructive_cleanup(policy: dict[str, Any]) -> bool:
    return not bool(policy.get("dry_run", True))


def cleanup_mode_allows(policy: dict[str, Any], candidate_type: str) -> bool:
    mode = str(policy.get("mode", "")).strip()
    if candidate_type == "run_dir":
        return False
    if mode == "derived_artifacts_only":
        return candidate_type in {"report", "artifact_index", "temp_file", "empty_dir", "approval_pack"}
    if mode == "reports_only":
        return candidate_type == "report"
    if mode == "indexes_only":
        return candidate_type == "artifact_index"
    if mode == "approval_packs_only":
        return candidate_type == "approval_pack"
    if mode == "temp_only":
        return candidate_type == "temp_file"
    return False
