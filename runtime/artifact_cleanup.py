from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import CleanupConfirmationError, CleanupExecutionError
from .models import CleanupCandidate, CleanupResult
from .persistence import read_json, write_json_atomic
from .retention_policy import (
    cleanup_mode_allows,
    is_destructive_cleanup,
    normalize_retention_policy,
    validate_retention_policy,
)
from .taskframe import utc_now


CLEANUP_DIR_NAME = "cleanup"
CLEANUP_REPORT_PREFIX = "cleanup_"
CLEANUP_REPORT_SUFFIX = ".json"


def new_cleanup_id() -> str:
    return f"cln_{uuid4().hex}"


def get_cleanup_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / CLEANUP_DIR_NAME


def get_cleanup_report_path(
    cleanup_id: str,
    runtime_data_dir: str | Path = "runtime_data",
) -> Path:
    return get_cleanup_dir(runtime_data_dir) / f"{CLEANUP_REPORT_PREFIX}{cleanup_id}{CLEANUP_REPORT_SUFFIX}"


def file_age_days(path: str | Path, now: float | None = None) -> float:
    target = Path(path)
    if not target.exists():
        return 0.0
    current = datetime.fromtimestamp(now, tz=timezone.utc) if now is not None else datetime.now(timezone.utc)
    modified = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
    return max(0.0, (current - modified).total_seconds() / 86400.0)


def file_size_bytes(path: str | Path) -> int:
    target = Path(path)
    if not target.exists():
        return 0
    try:
        return int(target.stat().st_size)
    except OSError:
        return 0


def is_temp_file(path: str | Path) -> bool:
    target = Path(path)
    name = target.name
    return name.startswith("~") or name.endswith(".tmp") or name.endswith(".bak") or name.endswith(".part")


def load_frame_summary_safe(frame_id: str, runtime_data_dir: str | Path) -> dict[str, Any] | None:
    from .persistence import get_summary_path

    path = get_summary_path(frame_id, runtime_data_dir)
    try:
        data = read_json(path)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_taskframe_safe(frame_id: str, runtime_data_dir: str | Path) -> dict[str, Any] | None:
    from .persistence import load_taskframe_dict

    try:
        data = load_taskframe_dict(frame_id, runtime_data_dir)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def frame_is_protected(
    frame_id: str,
    policy: dict[str, Any],
    runtime_data_dir: str | Path = "runtime_data",
) -> tuple[bool, str]:
    summary = load_frame_summary_safe(frame_id, runtime_data_dir)
    taskframe = load_taskframe_safe(frame_id, runtime_data_dir)

    if summary is None and taskframe is None:
        return True, "Unknown evidence state must not be deleted."

    state = ""
    pending_action_count = None
    live_side_effect_count = None

    if isinstance(summary, dict):
        state = str(summary.get("state", ""))
        pending_action_count = summary.get("pending_action_count")
        live_side_effect_count = summary.get("executed_action_count")

    if not state and isinstance(taskframe, dict):
        state = str(taskframe.get("state", ""))
    if pending_action_count is None and isinstance(taskframe, dict):
        pending_actions = taskframe.get("pending_actions")
        if isinstance(pending_actions, list):
            pending_action_count = len(pending_actions)
    if live_side_effect_count is None and isinstance(taskframe, dict):
        executed_actions = taskframe.get("executed_actions")
        if isinstance(executed_actions, list):
            live_side_effect_count = len(executed_actions)

    if not state or pending_action_count is None or live_side_effect_count is None:
        if isinstance(taskframe, dict) or isinstance(summary, dict):
            # Missing critical fields means the evidence cannot be trusted.
            return True, "Malformed frame evidence must not be deleted."
        return True, "Unknown evidence state must not be deleted."

    protect_states = policy.get("protect_states", [])
    if state in protect_states:
        return True, f"Frame state protected: {state}"

    if bool(policy.get("protect_pending_actions", True)) and int(pending_action_count or 0) > 0:
        return True, "Frame has pending actions."

    if bool(policy.get("protect_live_execution", True)) and int(live_side_effect_count or 0) > 0:
        return True, "Frame has live execution evidence."

    if bool(policy.get("protect_ready_approval_packs", True)):
        approval_dir = Path(runtime_data_dir) / "runs" / frame_id / "approval_packs"
        if approval_dir.is_dir():
            for path in approval_dir.glob("*.json"):
                try:
                    pack = read_json(path)
                except Exception:
                    return True, "Malformed approval pack must not be deleted."
                if not isinstance(pack, dict):
                    return True, "Malformed approval pack must not be deleted."
                status = str(pack.get("status", "")).strip().upper()
                if status == "READY_FOR_CONFIRMATION":
                    return True, "Frame has READY_FOR_CONFIRMATION approval packs."

    return False, ""


class ArtifactCleanupPlanner:
    def __init__(self, runtime_data_dir: str | Path = "runtime_data"):
        self.runtime_data_dir = Path(runtime_data_dir)

    def discover_candidates(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        candidates.extend(self.discover_report_candidates(policy))
        candidates.extend(self.discover_index_candidates(policy))
        candidates.extend(self.discover_temp_candidates(policy))
        candidates.extend(self.discover_empty_dir_candidates(policy))
        candidates.extend(self.discover_approval_pack_candidates(policy))
        return candidates

    def discover_report_candidates(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        if not bool(policy.get("delete_reports", True)):
            return []
        if not cleanup_mode_allows(policy, "report"):
            return []

        results: list[dict[str, Any]] = []
        runs_dir = self.runtime_data_dir / "runs"
        if not runs_dir.is_dir():
            return results

        max_age = float(policy.get("max_report_age_days", 0))
        for frame_dir in sorted(runs_dir.iterdir()):
            if not frame_dir.is_dir() or not frame_dir.name.startswith("frame_"):
                continue
            frame_id = frame_dir.name
            reports_dir = frame_dir / "reports"
            if not reports_dir.is_dir():
                continue
            protected, protection_reason = frame_is_protected(frame_id, policy, self.runtime_data_dir)
            for path in sorted(reports_dir.iterdir()):
                if not path.is_file():
                    continue
                age_days = file_age_days(path)
                if age_days < max_age:
                    continue
                candidate = CleanupCandidate(
                    candidate_id=new_cleanup_id(),
                    candidate_type="report",
                    path=str(path),
                    frame_id=frame_id,
                    reason="report older than max_report_age_days",
                    protected=protected,
                    protection_reason=protection_reason if protected else "",
                    size_bytes=file_size_bytes(path),
                    age_days=age_days,
                    metadata={"filename": path.name},
                )
                results.append(asdict(candidate))
        return results

    def discover_index_candidates(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        if not bool(policy.get("delete_artifact_index", True)):
            return []
        if not cleanup_mode_allows(policy, "artifact_index"):
            return []

        path = self.runtime_data_dir / "runs" / "artifact_index.json"
        if not path.is_file():
            return []
        age_days = file_age_days(path)
        if age_days < float(policy.get("min_age_days", 0)):
            return []
        candidate = CleanupCandidate(
            candidate_id=new_cleanup_id(),
            candidate_type="artifact_index",
            path=str(path),
            reason="artifact_index.json older than min_age_days",
            size_bytes=file_size_bytes(path),
            age_days=age_days,
            metadata={"filename": path.name},
        )
        return [asdict(candidate)]

    def discover_temp_candidates(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        if not bool(policy.get("delete_temp_files", True)):
            return []
        if not cleanup_mode_allows(policy, "temp_file"):
            return []

        results: list[dict[str, Any]] = []
        threshold = float(policy.get("max_temp_age_days", 0))
        if not self.runtime_data_dir.exists():
            return results
        for path in sorted(self.runtime_data_dir.rglob("*")):
            if not path.is_file() or not is_temp_file(path):
                continue
            age_days = file_age_days(path)
            if age_days < threshold:
                continue
            candidate = CleanupCandidate(
                candidate_id=new_cleanup_id(),
                candidate_type="temp_file",
                path=str(path),
                reason="temp file older than max_temp_age_days",
                size_bytes=file_size_bytes(path),
                age_days=age_days,
                metadata={"filename": path.name},
            )
            results.append(asdict(candidate))
        return results

    def discover_empty_dir_candidates(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        if not bool(policy.get("delete_empty_dirs", True)):
            return []
        if not cleanup_mode_allows(policy, "empty_dir"):
            return []

        results: list[dict[str, Any]] = []
        runtime_root = self.runtime_data_dir.resolve()
        runs_root = (self.runtime_data_dir / "runs").resolve()
        cleanup_root = get_cleanup_dir(self.runtime_data_dir).resolve()
        if not self.runtime_data_dir.exists():
            return results
        for path in sorted(self.runtime_data_dir.rglob("*")):
            if not path.is_dir():
                continue
            resolved = path.resolve()
            if resolved in {runtime_root, runs_root, cleanup_root}:
                continue
            if path.parent.resolve() == runs_root:
                continue
            try:
                has_children = any(path.iterdir())
            except OSError:
                continue
            if has_children:
                continue
            candidate = CleanupCandidate(
                candidate_id=new_cleanup_id(),
                candidate_type="empty_dir",
                path=str(path),
                reason="empty directory",
                size_bytes=0,
                age_days=0.0,
                metadata={"dirname": path.name},
            )
            results.append(asdict(candidate))
        return results

    def discover_approval_pack_candidates(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        if not bool(policy.get("delete_expired_approval_packs", False)):
            return []
        if not cleanup_mode_allows(policy, "approval_pack"):
            return []

        results: list[dict[str, Any]] = []
        runs_dir = self.runtime_data_dir / "runs"
        if not runs_dir.is_dir():
            return results

        threshold = float(policy.get("max_approval_pack_age_days", 0))
        for frame_dir in sorted(runs_dir.iterdir()):
            if not frame_dir.is_dir() or not frame_dir.name.startswith("frame_"):
                continue
            frame_id = frame_dir.name
            approval_dir = frame_dir / "approval_packs"
            if not approval_dir.is_dir():
                continue
            protected_frame, protection_reason = frame_is_protected(frame_id, policy, self.runtime_data_dir)
            for path in sorted(approval_dir.glob("*.json")):
                if not path.is_file():
                    continue
                age_days = file_age_days(path)
                if age_days < threshold:
                    continue
                try:
                    pack = read_json(path)
                except Exception:
                    pack = None
                if not isinstance(pack, dict):
                    candidate = CleanupCandidate(
                        candidate_id=new_cleanup_id(),
                        candidate_type="approval_pack",
                        path=str(path),
                        frame_id=frame_id,
                        reason="malformed approval pack",
                        protected=True,
                        protection_reason="Malformed approval pack must not be deleted.",
                        size_bytes=file_size_bytes(path),
                        age_days=age_days,
                        metadata={"filename": path.name},
                    )
                    results.append(asdict(candidate))
                    continue
                status = str(pack.get("status", "")).strip().upper()
                if status == "READY_FOR_CONFIRMATION" and bool(policy.get("protect_ready_approval_packs", True)):
                    candidate = CleanupCandidate(
                        candidate_id=new_cleanup_id(),
                        candidate_type="approval_pack",
                        path=str(path),
                        frame_id=frame_id,
                        reason="approval pack pending confirmation",
                        protected=True,
                        protection_reason="READY_FOR_CONFIRMATION approval packs are protected.",
                        size_bytes=file_size_bytes(path),
                        age_days=age_days,
                        metadata={"filename": path.name, "status": status},
                    )
                    results.append(asdict(candidate))
                    continue
                if status not in {"USED", "FAILED", "EXPIRED", "INVALIDATED"}:
                    candidate = CleanupCandidate(
                        candidate_id=new_cleanup_id(),
                        candidate_type="approval_pack",
                        path=str(path),
                        frame_id=frame_id,
                        reason="approval pack has unknown status",
                        protected=True,
                        protection_reason="Unknown approval pack status must not be deleted.",
                        size_bytes=file_size_bytes(path),
                        age_days=age_days,
                        metadata={"filename": path.name, "status": status},
                    )
                    results.append(asdict(candidate))
                    continue
                candidate = CleanupCandidate(
                    candidate_id=new_cleanup_id(),
                    candidate_type="approval_pack",
                    path=str(path),
                    frame_id=frame_id,
                    reason="expired approval pack",
                    protected=protected_frame,
                    protection_reason=protection_reason if protected_frame else "",
                    size_bytes=file_size_bytes(path),
                    age_days=age_days,
                    metadata={"filename": path.name, "status": status},
                )
                results.append(asdict(candidate))
        return results


class ArtifactCleaner:
    def __init__(self, runtime_data_dir: str | Path = "runtime_data"):
        self.runtime_data_dir = Path(runtime_data_dir)
        self.planner = ArtifactCleanupPlanner(runtime_data_dir)

    def plan_cleanup(self, policy: dict[str, Any] | None = None) -> CleanupResult:
        normalized = normalize_retention_policy(policy)
        normalized["dry_run"] = True
        normalized["confirm_cleanup"] = False
        validate_retention_policy(normalized)
        cleanup_id = new_cleanup_id()
        candidates = self.planner.discover_candidates(normalized)
        protected = [candidate for candidate in candidates if bool(candidate.get("protected", False))]
        deletable = [candidate for candidate in candidates if not bool(candidate.get("protected", False))]
        summary = self._build_summary(candidates, protected, deletable, [], [])
        report_path = self._write_report(cleanup_id, True, normalized, candidates, protected, [], [], summary)
        return CleanupResult(
            ok=True,
            cleanup_id=cleanup_id,
            dry_run=True,
            policy=normalized,
            candidates=candidates,
            deleted=[],
            protected=protected,
            errors=[],
            summary=summary,
            report_path=str(report_path),
            metadata={"created_at": utc_now()},
        )

    def execute_cleanup(self, policy: dict[str, Any] | None = None) -> CleanupResult:
        normalized = normalize_retention_policy(policy)
        validate_retention_policy(normalized)
        if not normalized.get("dry_run", True):
            if not bool(normalized.get("confirm_cleanup", False)):
                raise CleanupConfirmationError("Destructive cleanup requires confirm_cleanup=true.")
        if not is_destructive_cleanup(normalized):
            raise CleanupConfirmationError("execute_cleanup requires dry_run=false.")
        if not bool(normalized.get("confirm_cleanup", False)):
            raise CleanupConfirmationError("execute_cleanup requires confirm_cleanup=true.")

        cleanup_id = new_cleanup_id()
        candidates = self.planner.discover_candidates(normalized)
        protected = [candidate for candidate in candidates if bool(candidate.get("protected", False))]
        deleted: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for candidate in candidates:
            if bool(candidate.get("protected", False)):
                continue
            try:
                deleted_item = self._delete_candidate(candidate)
                if deleted_item is not None:
                    deleted.append(deleted_item)
            except Exception as exc:
                if isinstance(exc, CleanupExecutionError) and "escapes runtime_data_dir" in str(exc):
                    raise
                errors.append(
                    {
                        "candidate_id": candidate.get("candidate_id", ""),
                        "candidate_type": candidate.get("candidate_type", ""),
                        "path": candidate.get("path", ""),
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )

        summary = self._build_summary(candidates, protected, [item for item in candidates if item not in protected], deleted, errors)
        report_path = self._write_report(cleanup_id, False, normalized, candidates, protected, deleted, errors, summary)
        return CleanupResult(
            ok=len(errors) == 0,
            cleanup_id=cleanup_id,
            dry_run=False,
            policy=normalized,
            candidates=candidates,
            deleted=deleted,
            protected=protected,
            errors=errors,
            summary=summary,
            report_path=str(report_path),
            error="" if not errors else "One or more cleanup operations failed.",
            metadata={"created_at": utc_now()},
        )

    def _delete_candidate(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        path = Path(str(candidate.get("path", "")))
        if not self._is_path_within_runtime_data(path):
            raise CleanupExecutionError(f"Path escapes runtime_data_dir: {path}")

        size_bytes = file_size_bytes(path)
        if candidate.get("candidate_type") == "empty_dir":
            if not path.exists():
                raise CleanupExecutionError(f"Cleanup candidate missing: {path}")
            if not path.is_dir():
                raise CleanupExecutionError(f"Expected directory candidate: {path}")
            path.rmdir()
        else:
            if not path.exists():
                raise CleanupExecutionError(f"Cleanup candidate missing: {path}")
            if not path.is_file():
                raise CleanupExecutionError(f"Expected file candidate: {path}")
            path.unlink()

        deleted_candidate = dict(candidate)
        deleted_candidate["size_bytes"] = size_bytes
        return deleted_candidate

    def _build_summary(
        self,
        candidates: list[dict[str, Any]],
        protected: list[dict[str, Any]],
        deletable: list[dict[str, Any]],
        deleted: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "candidate_count": len(candidates),
            "protected_count": len(protected),
            "deletable_count": len(deletable),
            "deleted_count": len(deleted),
            "error_count": len(errors),
            "total_candidate_bytes": sum(int(item.get("size_bytes", 0) or 0) for item in candidates),
            "total_deleted_bytes": sum(int(item.get("size_bytes", 0) or 0) for item in deleted),
        }

    def _write_report(
        self,
        cleanup_id: str,
        dry_run: bool,
        policy: dict[str, Any],
        candidates: list[dict[str, Any]],
        protected: list[dict[str, Any]],
        deleted: list[dict[str, Any]],
        errors: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> Path:
        report_path = get_cleanup_report_path(cleanup_id, self.runtime_data_dir)
        payload = {
            "cleanup_id": cleanup_id,
            "created_at": utc_now(),
            "dry_run": dry_run,
            "policy": policy,
            "summary": summary,
            "candidates": candidates,
            "protected": protected,
            "deleted": deleted,
            "errors": errors,
        }
        write_json_atomic(report_path, payload)
        return report_path

    def _is_path_within_runtime_data(self, path: Path) -> bool:
        try:
            return path.resolve().is_relative_to(self.runtime_data_dir.resolve())
        except AttributeError:
            runtime_root = self.runtime_data_dir.resolve()
            try:
                path.resolve().relative_to(runtime_root)
                return True
            except ValueError:
                return False
