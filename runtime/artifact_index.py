from __future__ import annotations

from pathlib import Path
from typing import Any

from .persistence import read_json, write_json_atomic
from .taskframe import json_safe, utc_now


ARTIFACT_INDEX_FILE = "artifact_index.json"


def get_artifact_index_path(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / "runs" / ARTIFACT_INDEX_FILE


def rebuild_artifact_index(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    runs_dir = runtime_root / "runs"
    records: list[dict[str, Any]] = []

    if runs_dir.is_dir():
        for frame_dir in sorted(runs_dir.iterdir()):
            if not frame_dir.is_dir() or not frame_dir.name.startswith("frame_"):
                continue
            record = _build_record(frame_dir, runtime_root)
            if record is not None:
                records.append(record)

    index = {
        "generated_at": utc_now(),
        "runtime_data_dir": str(runtime_root),
        "record_count": len(records),
        "records": records,
    }
    return index


def rebuild_and_save_artifact_index(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    index = rebuild_artifact_index(runtime_data_dir)
    write_json_atomic(get_artifact_index_path(runtime_data_dir), index)
    return index


def load_artifact_index(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    path = get_artifact_index_path(runtime_data_dir)
    if not path.is_file():
        return {"generated_at": "", "runtime_data_dir": str(Path(runtime_data_dir)), "record_count": 0, "records": []}
    data = read_json(path)
    if not isinstance(data, dict):
        return {"generated_at": "", "runtime_data_dir": str(Path(runtime_data_dir)), "record_count": 0, "records": []}
    records = data.get("records", [])
    if not isinstance(records, list):
        records = []
    data["records"] = records
    data["record_count"] = int(data.get("record_count", len(records)) or len(records))
    return data


def _build_record(frame_dir: Path, runtime_root: Path) -> dict[str, Any] | None:
    taskframe_path = frame_dir / "taskframe.json"
    summary_path = frame_dir / "summary.json"
    if not taskframe_path.is_file() and not summary_path.is_file():
        return None

    taskframe = _safe_read_dict(taskframe_path)
    summary = _safe_read_dict(summary_path)

    if summary is None and taskframe is not None:
        summary = {
            "frame_id": frame_dir.name,
            "manifest_id": taskframe.get("manifest_id", ""),
            "state": taskframe.get("state", ""),
            "created_at": taskframe.get("created_at", ""),
            "updated_at": taskframe.get("updated_at", ""),
            "error_count": len(taskframe.get("errors", [])) if isinstance(taskframe.get("errors", []), list) else 0,
        }
    if summary is None:
        summary = {}

    pending_actions = taskframe.get("pending_actions", []) if isinstance(taskframe, dict) else []
    executed_actions = taskframe.get("executed_actions", []) if isinstance(taskframe, dict) else []
    outputs = taskframe.get("outputs", {}) if isinstance(taskframe, dict) else {}
    manifest_id = taskframe.get("manifest_id", "") if isinstance(taskframe, dict) else ""
    state = taskframe.get("state", "") if isinstance(taskframe, dict) else str(summary.get("state", ""))
    created_at = taskframe.get("created_at", "") if isinstance(taskframe, dict) else str(summary.get("created_at", ""))
    updated_at = taskframe.get("updated_at", "") if isinstance(taskframe, dict) else str(summary.get("updated_at", ""))

    reports_dir = frame_dir / "reports"
    approval_dir = frame_dir / "approval_packs"

    has_reports = reports_dir.is_dir() and any(item.is_file() for item in reports_dir.iterdir())
    has_approval_packs = approval_dir.is_dir() and any(item.is_file() for item in approval_dir.iterdir())
    has_errors = bool(taskframe.get("errors")) if isinstance(taskframe, dict) else int(summary.get("error_count", 0) or 0) > 0
    has_pending_actions = len(pending_actions) > 0
    has_live_execution = len(executed_actions) > 0

    return json_safe(
        {
            "frame_id": frame_dir.name,
            "manifest_id": manifest_id,
            "state": state,
            "created_at": created_at,
            "updated_at": updated_at,
            "pending_action_count": len(pending_actions),
            "executed_action_count": len(executed_actions),
            "error_count": int(summary.get("error_count", 0) or 0),
            "output_keys": sorted(outputs.keys()) if isinstance(outputs, dict) else [],
            "has_errors": has_errors,
            "has_pending_actions": has_pending_actions,
            "has_approval_packs": has_approval_packs,
            "has_reports": has_reports,
            "has_live_execution": has_live_execution,
            "artifact_dir": str(frame_dir),
        }
    )


def _safe_read_dict(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = read_json(path)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
