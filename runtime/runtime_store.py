from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .errors import RuntimeStoreBackupError, RuntimeStorePolicyError, RuntimeStoreRestoreError, RuntimeStoreValidationError
from .manifest_loader import load_manifest_by_id
from .persistence import ensure_dir, read_json, write_json_atomic
from .taskframe import TASKFRAME_STATES, json_safe, utc_now


RUNTIME_STORE_DIRS = (
    "taskframes",
    "reports",
    "approval_packs",
    "evidence",
    "recovery",
    "tool_health",
    "indexes",
    "backups",
    "cleanup",
    "migrations",
)

LEGACY_RUNTIME_DIRS = ("runs", "readiness", "portfolio_evidence")
DEFAULT_RUNTIME_STORE_RETENTION_POLICY: dict[str, Any] = {
    "schema_version": 1,
    "keep_completed_days": 30,
    "keep_failed_days": 90,
    "keep_pending_days": 365,
    "keep_approval_packs_days": 365,
    "keep_evidence_packs_days": 365,
    "delete_only_derived_artifacts": True,
    "protect_live_data": True,
    "protect_pending_actions": True,
}


def get_runtime_store_dir(name: str, runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / name


def get_runtime_store_paths(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Path]:
    root = Path(runtime_data_dir)
    return {name: root / name for name in RUNTIME_STORE_DIRS}


def ensure_runtime_store_layout(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Path]:
    paths = get_runtime_store_paths(runtime_data_dir)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def get_runtime_store_index_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "indexes" / "runtime_store_index.json"


def get_runtime_store_backup_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "backups"


def get_runtime_store_backup_manifest_name() -> str:
    return "backup_manifest.json"


def normalize_runtime_store_retention_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    if policy is None:
        return dict(DEFAULT_RUNTIME_STORE_RETENTION_POLICY)
    if not isinstance(policy, dict):
        raise RuntimeStorePolicyError("Retention policy must be a dict or None.")
    normalized = dict(DEFAULT_RUNTIME_STORE_RETENTION_POLICY)
    normalized.update(policy)
    return normalized


def validate_runtime_store_retention_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        raise RuntimeStorePolicyError("Retention policy must be a dict.")
    if int(policy.get("schema_version", 0) or 0) != 1:
        raise RuntimeStorePolicyError("Retention policy schema_version must be 1.")
    for key in (
        "keep_completed_days",
        "keep_failed_days",
        "keep_pending_days",
        "keep_approval_packs_days",
        "keep_evidence_packs_days",
    ):
        value = policy.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise RuntimeStorePolicyError(f"{key} must be a non-negative number.")
    for key in ("delete_only_derived_artifacts", "protect_live_data", "protect_pending_actions"):
        if not isinstance(policy.get(key), bool):
            raise RuntimeStorePolicyError(f"{key} must be a bool.")


def validate_runtime_store(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    manifest_dir: str | Path = "manifests",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    snapshot = _collect_runtime_store_snapshot(runtime_root, manifest_dir=manifest_dir)
    index_ok = False
    try:
        rebuilt_index = rebuild_runtime_store_index(runtime_root, manifest_dir=manifest_dir, persist=False, _precomputed=snapshot)
        index_ok = bool(rebuilt_index.get("ok", False))
    except Exception as exc:
        _issue(snapshot["issues"], "index_rebuild_failed", str(get_runtime_store_index_path(runtime_root)), f"Runtime store index could not be rebuilt: {exc}", "Repair the corrupted runtime store index.", severity="error")

    ok = not any(item.get("severity") == "error" for item in snapshot["issues"]) and index_ok
    return {
        "ok": ok,
        "schema_version": 1,
        "runtime_data_dir": str(runtime_root),
        "manifest_dir": str(Path(manifest_dir)),
        "required_folders": {name: (runtime_root / name).is_dir() for name in RUNTIME_STORE_DIRS},
        "artifact_counts": snapshot["artifact_counts"],
        "taskframes": snapshot["taskframes"],
        "approval_packs": snapshot["approval_packs"],
        "reports": snapshot["reports"],
        "evidence": snapshot["evidence"],
        "tool_health": snapshot["tool_health"],
        "indexes": snapshot["indexes"],
        "cleanup": snapshot["cleanup"],
        "migrations": snapshot["migrations"],
        "orphaned_artifacts": snapshot["orphaned_artifacts"],
        "corrupted_paths": snapshot["corrupted_paths"],
        "issues": snapshot["issues"],
        "index_rebuildable": index_ok,
    }


def rebuild_runtime_store_index(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    manifest_dir: str | Path = "manifests",
    persist: bool = True,
    _precomputed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    validation = _precomputed if _precomputed is not None else _collect_runtime_store_snapshot(runtime_root, manifest_dir=manifest_dir)
    index = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "runtime_data_dir": str(runtime_root),
        "artifact_counts": dict(validation.get("artifact_counts", {})),
        "ok": not any(item.get("severity") == "error" for item in validation.get("issues", [])),
        "issues": list(validation.get("issues", [])),
        "taskframes": list(validation.get("taskframes", [])),
        "approval_packs": list(validation.get("approval_packs", [])),
        "reports": list(validation.get("reports", [])),
        "evidence": list(validation.get("evidence", [])),
        "tool_health": list(validation.get("tool_health", [])),
        "indexes": list(validation.get("indexes", [])),
        "cleanup": list(validation.get("cleanup", [])),
        "migrations": list(validation.get("migrations", [])),
    }
    if persist:
        ensure_dir(get_runtime_store_index_path(runtime_root).parent)
        write_json_atomic(get_runtime_store_index_path(runtime_root), index)
    return index


def load_runtime_store_index(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    path = get_runtime_store_index_path(runtime_data_dir)
    if not path.is_file():
        return {
            "schema_version": 1,
            "generated_at": "",
            "runtime_data_dir": str(Path(runtime_data_dir)),
            "artifact_counts": {},
            "ok": False,
            "issues": [],
            "taskframes": [],
            "approval_packs": [],
            "reports": [],
            "evidence": [],
            "tool_health": [],
            "indexes": [],
            "cleanup": [],
            "migrations": [],
        }
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def backup_runtime_store(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    manifest_dir: str | Path = "manifests",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    ensure_runtime_store_layout(runtime_root)
    validation = validate_runtime_store(runtime_root, manifest_dir=manifest_dir)
    backup_dir = ensure_dir(get_runtime_store_backup_dir(runtime_root))
    timestamp = _safe_timestamp(utc_now())
    backup_id = f"taskframe_backup_{timestamp}"
    backup_path = backup_dir / f"{backup_id}.zip"
    manifest = {
        "backup_id": backup_id,
        "created_at": utc_now(),
        "source_runtime_dir": str(runtime_root),
        "artifact_counts": dict(validation.get("artifact_counts", {})),
        "profile": _runtime_profile_name(),
        "contains_live_data": False,
        "contains_pending_actions": bool(_count_pending_actions(validation)),
        "schema_version": 1,
    }
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_backup_manifest(archive, manifest)
        for folder_name in (*RUNTIME_STORE_DIRS, *LEGACY_RUNTIME_DIRS):
            if folder_name == "backups":
                continue
            folder = runtime_root / folder_name
            if not folder.exists():
                continue
            _zip_path(archive, runtime_root, folder)
    manifest_path = backup_dir / f"{backup_id}.manifest.json"
    write_json_atomic(manifest_path, manifest)
    return {
        "ok": True,
        "backup_id": backup_id,
        "backup_path": str(backup_path),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "validation": validation,
    }


def restore_runtime_store_backup(
    backup_path: str | Path,
    target_path: str | Path,
    *,
    validate_only: bool = True,
    manifest_dir: str | Path = "manifests",
) -> dict[str, Any]:
    archive_path = Path(backup_path)
    target_root = Path(target_path)
    if not archive_path.is_file():
        raise RuntimeStoreRestoreError(f"Backup archive not found: {archive_path}")
    if not validate_only:
        raise RuntimeStoreRestoreError("Active runtime_data overwrite restore is not supported.")

    ensure_dir(target_root)
    if any(target_root.iterdir()):
        raise RuntimeStoreRestoreError(f"Restore target must be empty: {target_root}")

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = _read_backup_manifest(archive)
        _validate_backup_manifest(manifest, archive_path)
        _validate_backup_members(archive)
        archive.extractall(target_root)

    ensure_runtime_store_layout(target_root)
    validation = validate_runtime_store(target_root, manifest_dir=manifest_dir)
    report = {
        "ok": bool(validation.get("ok", False)) and bool(manifest),
        "backup_path": str(archive_path),
        "target_path": str(target_root),
        "validate_only": True,
        "manifest": manifest,
        "validation": validation,
        "issues": list(validation.get("issues", [])),
        "created_at": utc_now(),
        "schema_version": 1,
    }
    write_json_atomic(target_root / "restore_report.json", report)
    return report


def build_runtime_store_retention_plan(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    policy: dict[str, Any] | None = None,
    manifest_dir: str | Path = "manifests",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    normalized = normalize_runtime_store_retention_policy(policy)
    validate_runtime_store_retention_policy(normalized)
    validation = validate_runtime_store(runtime_root, manifest_dir=manifest_dir)
    frames = validation.get("taskframes", [])
    candidates: list[dict[str, Any]] = []
    protected: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        state = str(frame.get("state", "")).upper()
        frame_id = str(frame.get("frame_id", "")).strip()
        age_days = _frame_age_days(frame)
        pending_count = int(frame.get("pending_action_count", 0) or 0)
        if state in {"WAITING_FOR_EXECUTE", "EXECUTING_PENDING"} or (bool(normalized.get("protect_pending_actions", True)) and pending_count > 0):
            protected.append(
                {
                    "frame_id": frame_id,
                    "path": frame.get("artifact_dir", ""),
                    "reason": "Frame has pending actions or is waiting for execution.",
                }
            )
            continue
        threshold = _retention_threshold_days(state, normalized)
        if age_days < threshold:
            continue
        for key, path in _retention_paths_for_frame(frame, runtime_root):
            candidates.append(
                {
                    "candidate_type": key,
                    "path": str(path),
                    "frame_id": frame_id,
                    "reason": f"{key} older than retention threshold.",
                    "age_days": age_days,
                    "protected": False,
                }
            )
    return {
        "ok": True,
        "dry_run": True,
        "schema_version": 1,
        "runtime_data_dir": str(runtime_root),
        "policy": normalized,
        "candidate_count": len(candidates),
        "protected_count": len(protected),
        "candidates": candidates,
        "protected": protected,
        "validation": validation,
    }


def cleanup_runtime_store(
    runtime_data_dir: str | Path = "runtime_data",
    *,
    policy: dict[str, Any] | None = None,
    manifest_dir: str | Path = "manifests",
    dry_run: bool = True,
) -> dict[str, Any]:
    plan = build_runtime_store_retention_plan(runtime_data_dir, policy=policy, manifest_dir=manifest_dir)
    plan["dry_run"] = True
    plan["cleanup_performed"] = False
    plan["requested_dry_run"] = bool(dry_run)
    plan["message"] = "Cleanup is dry-run only in the current runtime-store spec."
    return plan


def runtime_store_contract(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    return {
        "runtime_data_dir": str(runtime_root),
        "layout": {name: str(runtime_root / name) for name in RUNTIME_STORE_DIRS},
        "legacy_layout": {name: str(runtime_root / name) for name in LEGACY_RUNTIME_DIRS},
        "backup_manifest_name": get_runtime_store_backup_manifest_name(),
        "index_path": str(get_runtime_store_index_path(runtime_root)),
        "schema_version": 1,
    }


def _scan_taskframes(
    runtime_root: Path,
    *,
    manifest_dir: str | Path,
    issues: list[dict[str, Any]],
    corrupted_paths: list[str],
) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for path in _iter_candidate_json_files(runtime_root / "taskframes", recursive=True):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if not isinstance(payload, dict):
            continue
        frame_id = _frame_id_from_taskframe_path(path)
        payload = dict(payload)
        payload["frame_id"] = str(payload.get("frame_id", frame_id) or frame_id)
        payload["artifact_dir"] = str(path.parent)
        payload["pending_action_count"] = len(payload.get("pending_actions", []) or []) if isinstance(payload.get("pending_actions", []), list) else 0
        payload["executed_action_count"] = len(payload.get("executed_actions", []) or []) if isinstance(payload.get("executed_actions", []), list) else 0
        payload["error_count"] = len(payload.get("errors", []) or []) if isinstance(payload.get("errors", []), list) else 0
        _validate_taskframe_payload(payload, path, manifest_dir=manifest_dir, issues=issues)
        discovered.append(payload)
    for path in _iter_legacy_taskframe_paths(runtime_root):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if not isinstance(payload, dict):
            continue
        payload = dict(payload)
        frame_id = str(payload.get("frame_id", path.parent.name) or path.parent.name)
        payload["frame_id"] = frame_id
        payload["artifact_dir"] = str(path.parent)
        payload["pending_action_count"] = len(payload.get("pending_actions", []) or []) if isinstance(payload.get("pending_actions", []), list) else 0
        payload["executed_action_count"] = len(payload.get("executed_actions", []) or []) if isinstance(payload.get("executed_actions", []), list) else 0
        payload["error_count"] = len(payload.get("errors", []) or []) if isinstance(payload.get("errors", []), list) else 0
        _validate_taskframe_payload(payload, path, manifest_dir=manifest_dir, issues=issues)
        discovered.append(payload)
    return discovered


def _collect_runtime_store_snapshot(runtime_root: Path, *, manifest_dir: str | Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []
    corrupted_paths: list[str] = []

    for folder_name in RUNTIME_STORE_DIRS:
        folder = runtime_root / folder_name
        if not folder.is_dir():
            _issue(issues, "missing_folder", str(folder), f"Missing runtime store folder: {folder_name}", "Seed or create the runtime store folder.", severity="error")

    taskframes = _scan_taskframes(runtime_root, manifest_dir=manifest_dir, issues=issues, corrupted_paths=corrupted_paths)
    taskframe_ids = {item["frame_id"] for item in taskframes if item.get("frame_id")}

    approval_packs = _scan_approval_packs(runtime_root, taskframe_ids, issues=issues, corrupted_paths=corrupted_paths)
    reports = _scan_reports(runtime_root, taskframe_ids, issues=issues, corrupted_paths=corrupted_paths)
    evidence = _scan_evidence(runtime_root, taskframe_ids, issues=issues, corrupted_paths=corrupted_paths)
    tool_health = _scan_tool_health(runtime_root, issues=issues, corrupted_paths=corrupted_paths)
    indexes = _scan_indexes(runtime_root, issues=issues, corrupted_paths=corrupted_paths)
    cleanup = _scan_json_directory(runtime_root / "cleanup", "cleanup", issues=issues, corrupted_paths=corrupted_paths)
    migrations = _scan_json_directory(runtime_root / "migrations", "migration", issues=issues, corrupted_paths=corrupted_paths)

    for item in approval_packs:
        frame_id = str(item.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", item["path"], "Approval pack references a missing TaskFrame.", "Restore or remove the orphaned approval pack.", severity="warning")
            orphaned.append(item)

    for item in reports:
        frame_id = str(item.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", item["path"], "Report references a missing TaskFrame.", "Restore or remove the orphaned report.", severity="warning")
            orphaned.append(item)

    for item in evidence:
        frame_id = str(item.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", item["path"], "Evidence artifact references a missing TaskFrame.", "Restore or remove the orphaned evidence artifact.", severity="warning")
            orphaned.append(item)

    counts = {
        "taskframes": len(taskframes),
        "approval_packs": len(approval_packs),
        "reports": len(reports),
        "evidence": len(evidence),
        "tool_health": len(tool_health),
        "indexes": len(indexes),
        "cleanup": len(cleanup),
        "migrations": len(migrations),
    }

    return {
        "artifact_counts": counts,
        "taskframes": taskframes,
        "approval_packs": approval_packs,
        "reports": reports,
        "evidence": evidence,
        "tool_health": tool_health,
        "indexes": indexes,
        "cleanup": cleanup,
        "migrations": migrations,
        "orphaned_artifacts": orphaned,
        "corrupted_paths": corrupted_paths,
        "issues": issues,
    }


def _validate_taskframe_payload(
    payload: dict[str, Any],
    path: Path,
    *,
    manifest_dir: str | Path,
    issues: list[dict[str, Any]],
) -> None:
    frame_id = str(payload.get("frame_id", "")).strip()
    manifest_id = str(payload.get("manifest_id", "")).strip()
    state = str(payload.get("state", "")).strip()
    for field in ("frame_id", "manifest_id", "state", "created_at", "updated_at"):
        if not str(payload.get(field, "")).strip():
            _issue(issues, "missing_required_field", str(path), f"TaskFrame missing required field: {field}", "Repair the TaskFrame JSON or restore it from backup.", severity="error")
    if state and state not in TASKFRAME_STATES:
        _issue(issues, "unknown_state", str(path), f"TaskFrame has unknown state: {state}", "Repair the TaskFrame state or reload from a trusted source.", severity="error")
    if manifest_id:
        try:
            load_manifest_by_id(manifest_id, manifest_dir)
        except Exception as exc:
            _issue(issues, "missing_manifest", str(path), f"TaskFrame references missing manifest '{manifest_id}': {exc}", "Restore the manifest or update the TaskFrame reference.", severity="error")


def _scan_approval_packs(
    runtime_root: Path,
    taskframe_ids: set[str],
    *,
    issues: list[dict[str, Any]],
    corrupted_paths: list[str],
) -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for path in _iter_candidate_json_files(runtime_root / "approval_packs", recursive=True):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if not isinstance(payload, dict):
            continue
        record = _normalize_approval_pack(payload, path)
        packs.append(record)
        frame_id = str(record.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", str(path), "Approval pack references a missing TaskFrame.", "Restore or remove the orphaned approval pack.", severity="warning")
    for path in _iter_legacy_approval_pack_paths(runtime_root):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if not isinstance(payload, dict):
            continue
        record = _normalize_approval_pack(payload, path)
        packs.append(record)
        frame_id = str(record.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", str(path), "Approval pack references a missing TaskFrame.", "Restore or remove the orphaned approval pack.", severity="warning")
    return packs


def _normalize_approval_pack(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    frame_id = str(payload.get("frame_id") or path.parent.name or "").strip()
    return {
        "path": str(path),
        "frame_id": frame_id,
        "manifest_id": str(payload.get("manifest_id", "")),
        "state": str(payload.get("state", "")),
        "schema_version": int(payload.get("schema_version", 1) or 1),
    }


def _scan_reports(
    runtime_root: Path,
    taskframe_ids: set[str],
    *,
    issues: list[dict[str, Any]],
    corrupted_paths: list[str],
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in _iter_report_files(runtime_root / "reports"):
        record = _normalize_report_record(path, issues, corrupted_paths)
        reports.append(record)
        frame_id = str(record.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", str(path), "Report references a missing TaskFrame.", "Restore or remove the orphaned report.", severity="warning")
    for path in _iter_legacy_report_paths(runtime_root):
        record = _normalize_report_record(path, issues, corrupted_paths)
        reports.append(record)
        frame_id = str(record.get("frame_id", "")).strip()
        if frame_id and frame_id not in taskframe_ids:
            _issue(issues, "orphaned_artifact", str(path), "Report references a missing TaskFrame.", "Restore or remove the orphaned report.", severity="warning")
    return reports


def _normalize_report_record(path: Path, issues: list[dict[str, Any]], corrupted_paths: list[str]) -> dict[str, Any]:
    frame_id = _frame_id_from_report_path(path)
    payload = _safe_read_json(path, issues, corrupted_paths) if path.suffix == ".json" else None
    if isinstance(payload, dict):
        frame_id = str(payload.get("frame_id", frame_id) or frame_id)
    return {
        "path": str(path),
        "frame_id": frame_id,
        "report_type": path.stem,
        "schema_version": int(payload.get("schema_version", 1) or 1) if isinstance(payload, dict) else 1,
    }


def _scan_evidence(
    runtime_root: Path,
    taskframe_ids: set[str],
    *,
    issues: list[dict[str, Any]],
    corrupted_paths: list[str],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in _iter_candidate_json_files(runtime_root / "evidence", recursive=True):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if not isinstance(payload, dict):
            continue
        record = {
            "path": str(path),
            "frame_id": str(payload.get("frame_id", _frame_id_from_evidence_path(path)) or _frame_id_from_evidence_path(path)),
            "schema_version": int(payload.get("bundle_version", payload.get("schema_version", 1)) or 1),
        }
        artifacts.append(record)
        _validate_evidence_artifact(payload, path, taskframe_ids, issues)
    for path in _iter_legacy_evidence_paths(runtime_root):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if not isinstance(payload, dict):
            continue
        record = {
            "path": str(path),
            "frame_id": str(payload.get("frame_id", _frame_id_from_evidence_path(path)) or _frame_id_from_evidence_path(path)),
            "schema_version": int(payload.get("bundle_version", payload.get("schema_version", 1)) or 1),
        }
        artifacts.append(record)
        _validate_evidence_artifact(payload, path, taskframe_ids, issues)
    return artifacts


def _validate_evidence_artifact(
    payload: dict[str, Any],
    path: Path,
    taskframe_ids: set[str],
    issues: list[dict[str, Any]],
) -> None:
    frame_id = str(payload.get("frame_id", "")).strip()
    if frame_id and frame_id not in taskframe_ids:
        _issue(issues, "orphaned_artifact", str(path), "Evidence artifact references a missing TaskFrame.", "Restore or remove the orphaned evidence artifact.", severity="warning")
    artifact_paths = payload.get("artifact_paths", {})
    if isinstance(artifact_paths, dict):
        for artifact_path in artifact_paths.values():
            if not isinstance(artifact_path, str) or not artifact_path.strip():
                continue
            referenced = Path(artifact_path)
            if not referenced.is_absolute():
                referenced = path.parent.parent / artifact_path
            if not referenced.exists():
                _issue(issues, "missing_evidence_file", str(path), f"Missing referenced evidence file: {artifact_path}", "Restore the referenced artifact or regenerate the evidence bundle.", severity="error")


def _scan_tool_health(runtime_root: Path, *, issues: list[dict[str, Any]], corrupted_paths: list[str]) -> list[dict[str, Any]]:
    return _scan_json_directory(runtime_root / "tool_health", "tool_health", issues=issues, corrupted_paths=corrupted_paths)


def _scan_indexes(runtime_root: Path, *, issues: list[dict[str, Any]], corrupted_paths: list[str]) -> list[dict[str, Any]]:
    index_records = _scan_json_directory(runtime_root / "indexes", "index", issues=issues, corrupted_paths=corrupted_paths)
    for record in index_records:
        if int(record.get("schema_version", 1) or 1) != 1:
            _issue(issues, "schema_version_unknown", record["path"], "Index has an unknown schema version.", "Rebuild the runtime store index.", severity="warning")
    return index_records


def _scan_json_directory(
    directory: Path,
    kind: str,
    *,
    issues: list[dict[str, Any]],
    corrupted_paths: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not directory.is_dir():
        return records
    for path in _iter_candidate_json_files(directory, recursive=True):
        payload = _safe_read_json(path, issues, corrupted_paths)
        if isinstance(payload, dict):
            records.append({"path": str(path), "kind": kind, "schema_version": int(payload.get("schema_version", 1) or 1)})
    return records


def _iter_candidate_json_files(root: Path, recursive: bool = True) -> Iterable[Path]:
    if not root.is_dir():
        return []
    iterator = root.rglob("*.json") if recursive else root.glob("*.json")
    return sorted(path for path in iterator if path.is_file())


def _iter_report_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in {".json", ".md", ".html"})


def _iter_legacy_taskframe_paths(runtime_root: Path) -> Iterable[Path]:
    runs_dir = runtime_root / "runs"
    if not runs_dir.is_dir():
        return []
    return sorted(path for path in runs_dir.rglob("taskframe.json") if path.is_file())


def _iter_legacy_approval_pack_paths(runtime_root: Path) -> Iterable[Path]:
    runs_dir = runtime_root / "runs"
    if not runs_dir.is_dir():
        return []
    return sorted(path for path in runs_dir.rglob("approval_packs/*.json") if path.is_file())


def _iter_legacy_report_paths(runtime_root: Path) -> Iterable[Path]:
    runs_dir = runtime_root / "runs"
    if not runs_dir.is_dir():
        return []
    return sorted(path for path in runs_dir.rglob("reports/*") if path.is_file() and path.suffix in {".json", ".md", ".html"})


def _iter_legacy_evidence_paths(runtime_root: Path) -> Iterable[Path]:
    runs_dir = runtime_root / "runs"
    if not runs_dir.is_dir():
        return []
    return sorted(path for path in runs_dir.rglob("reports/evidence_bundle.json") if path.is_file())


def _safe_read_json(path: Path, issues: list[dict[str, Any]], corrupted_paths: list[str]) -> dict[str, Any] | list[Any] | None:
    try:
        payload = read_json(path)
    except Exception as exc:
        corrupted_paths.append(str(path))
        _issue(issues, "invalid_json", str(path), f"Invalid JSON: {exc}", "Repair or replace the corrupted JSON artifact.", severity="error")
        return None
    return payload


def _issue(
    issues: list[dict[str, Any]],
    category: str,
    path: str,
    message: str,
    recommendation: str,
    *,
    severity: str,
) -> None:
    issues.append(
        {
            "category": category,
            "path": path,
            "message": message,
            "recommendation": recommendation,
            "severity": severity,
        }
    )


def _validate_backup_manifest(manifest: dict[str, Any], archive_path: Path) -> None:
    if not isinstance(manifest, dict):
        raise RuntimeStoreRestoreError(f"Malformed backup manifest in archive: {archive_path}")
    if int(manifest.get("schema_version", 0) or 0) != 1:
        raise RuntimeStoreRestoreError("Backup manifest schema_version must be 1.")
    if not str(manifest.get("backup_id", "")).strip():
        raise RuntimeStoreRestoreError("Backup manifest missing backup_id.")
    if not str(manifest.get("source_runtime_dir", "")).strip():
        raise RuntimeStoreRestoreError("Backup manifest missing source_runtime_dir.")


def _validate_backup_members(archive: zipfile.ZipFile) -> None:
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        if not name or name.startswith("/") or ":" in name.split("/")[0]:
            raise RuntimeStoreRestoreError(f"Unsafe backup member path: {member.filename}")
        parts = PurePosixPath(name).parts
        if any(part == ".." for part in parts):
            raise RuntimeStoreRestoreError(f"Unsafe backup member path traversal: {member.filename}")


def _read_backup_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        with archive.open(get_runtime_store_backup_manifest_name()) as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    except KeyError as exc:
        raise RuntimeStoreRestoreError("Backup archive is missing backup_manifest.json.") from exc
    except Exception as exc:
        raise RuntimeStoreRestoreError(f"Unable to read backup manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeStoreRestoreError("Backup manifest must be a JSON object.")
    return payload


def _write_backup_manifest(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> None:
    archive.writestr(get_runtime_store_backup_manifest_name(), json.dumps(json_safe(manifest), indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _zip_path(archive: zipfile.ZipFile, runtime_root: Path, path: Path) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                archive.write(child, arcname=str(child.relative_to(runtime_root)).replace("\\", "/"))
    elif path.is_file():
        archive.write(path, arcname=str(path.relative_to(runtime_root)).replace("\\", "/"))


def _frame_id_from_taskframe_path(path: Path) -> str:
    if path.parent.name == "taskframes":
        return path.stem
    if len(path.parents) >= 2 and path.parents[1].name == "taskframes":
        return path.parents[0].name
    return path.parent.name


def _frame_id_from_report_path(path: Path) -> str:
    if path.parent.name in {"reports", "taskframes", "approval_packs", "evidence"} and path.parent.parent.name:
        return path.parent.parent.name if path.parent.parent.name != "runs" else path.parent.name
    if path.parent.name == "reports" and path.parent.parent.name == "runs":
        return path.parent.parent.name
    if len(path.parents) >= 2 and path.parents[1].name == "runs":
        return path.parents[0].name
    if path.parent.name == "reports":
        return path.parent.name
    return path.stem


def _frame_id_from_evidence_path(path: Path) -> str:
    if path.parent.name == "evidence" and path.parent.parent.name:
        return path.parent.parent.name
    if "runs" in path.parts:
        try:
            idx = path.parts.index("runs")
            return path.parts[idx + 1]
        except Exception:
            return path.stem
    return path.stem


def _runtime_profile_name() -> str:
    try:
        from .runtime_environment import load_runtime_profile

        profile = load_runtime_profile()
        return str(profile.get("profile", "") or "demo")
    except Exception:
        return "demo"


def _count_pending_actions(validation: dict[str, Any]) -> int:
    total = 0
    for frame in validation.get("taskframes", []) or []:
        if isinstance(frame, dict):
            if isinstance(frame.get("pending_actions"), list):
                total += len(frame.get("pending_actions", []))
            else:
                total += int(frame.get("pending_action_count", 0) or 0)
    return total


def _safe_timestamp(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", value) or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _frame_age_days(frame: dict[str, Any]) -> float:
    for key in ("updated_at", "created_at"):
        value = str(frame.get(key, "")).strip()
        if not value:
            continue
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            current = datetime.now(timezone.utc)
            return max(0.0, (current - moment).total_seconds() / 86400.0)
        except Exception:
            continue
    return 0.0


def _retention_threshold_days(state: str, policy: dict[str, Any]) -> float:
    if state.startswith("FAILED"):
        return float(policy.get("keep_failed_days", 90))
    if state in {"WAITING_FOR_EXECUTE", "EXECUTING_PENDING"}:
        return float(policy.get("keep_pending_days", 365))
    return float(policy.get("keep_completed_days", 30))


def _retention_paths_for_frame(frame: dict[str, Any], runtime_root: Path) -> list[tuple[str, Path]]:
    frame_id = str(frame.get("frame_id", "")).strip()
    paths: list[tuple[str, Path]] = []
    if not frame_id:
        return paths
    legacy_root = runtime_root / "runs" / frame_id
    if legacy_root.is_dir():
        for filename in ("run_report.md", "run_report.html", "approval_pack_report.md", "approval_pack_report.html", "evidence_bundle.json", "summary.json"):
            candidate = legacy_root / "reports" / filename
            if candidate.exists():
                paths.append(("report", candidate))
        approval_dir = legacy_root / "approval_packs"
        if approval_dir.is_dir():
            for item in approval_dir.glob("*.json"):
                paths.append(("approval_pack", item))
    canonical = runtime_root / "taskframes" / f"{frame_id}.json"
    if canonical.exists():
        paths.append(("taskframe", canonical))
    return paths
