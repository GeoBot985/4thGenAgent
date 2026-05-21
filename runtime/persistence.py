from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .errors import TaskFrameNotFoundError, TaskFramePersistenceError
from .models import TaskFrame
from .taskframe import build_taskframe_summary, json_safe, to_dict


DEFAULT_RUNTIME_DATA_DIR = "runtime_data"
RUNS_DIR_NAME = "runs"
TASKFRAME_FILE = "taskframe.json"
AUDIT_FILE = "audit.json"
OUTPUTS_FILE = "outputs.json"
SUMMARY_FILE = "summary.json"


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_runs_dir(runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR) -> Path:
    return Path(runtime_data_dir) / RUNS_DIR_NAME


def get_frame_dir(
    frame_id: str,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> Path:
    return get_runs_dir(runtime_data_dir) / frame_id


def get_taskframe_path(
    frame_id: str,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> Path:
    return get_frame_dir(frame_id, runtime_data_dir) / TASKFRAME_FILE


def get_audit_path(frame_id: str, runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR) -> Path:
    return get_frame_dir(frame_id, runtime_data_dir) / AUDIT_FILE


def get_outputs_path(frame_id: str, runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR) -> Path:
    return get_frame_dir(frame_id, runtime_data_dir) / OUTPUTS_FILE


def get_summary_path(frame_id: str, runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR) -> Path:
    return get_frame_dir(frame_id, runtime_data_dir) / SUMMARY_FILE


def write_json_atomic(path: str | Path, data: Any) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    temp_path = target.with_name(f"{target.name}.tmp")
    safe_data = json_safe(data)
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(safe_data, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, target)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise TaskFramePersistenceError(f"Unable to write JSON atomically: {target}") from exc
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def read_json(path: str | Path) -> Any:
    target = Path(path)
    if not target.is_file():
        raise TaskFrameNotFoundError(f"JSON file not found: {target}")
    try:
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise TaskFramePersistenceError(f"Unable to read JSON file: {target}") from exc


def save_taskframe(
    frame: TaskFrame,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> Path:
    from .persistence_backends.backend_factory import get_persistence_backend

    frame_data = to_dict(frame)
    frame_dir = ensure_dir(get_frame_dir(frame.frame_id, runtime_data_dir))
    write_json_atomic(get_taskframe_path(frame.frame_id, runtime_data_dir), frame_data)
    write_json_atomic(get_audit_path(frame.frame_id, runtime_data_dir), [json_safe(item) for item in frame.audit])
    write_json_atomic(get_outputs_path(frame.frame_id, runtime_data_dir), frame.outputs)
    write_json_atomic(get_summary_path(frame.frame_id, runtime_data_dir), build_taskframe_summary(frame))
    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        backend.save_taskframe(frame_data)
    return frame_dir


def persist_frame_update(
    frame: TaskFrame,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> Path:
    frame_dir = save_taskframe(frame, runtime_data_dir)
    from .run_ledger import append_ledger_record

    append_ledger_record(frame, runtime_data_dir)
    return frame_dir


def load_taskframe_dict(
    frame_id: str,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> dict[str, Any]:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        data = backend.load_taskframe(frame_id)
        if isinstance(data, dict):
            return data
    data = read_json(get_taskframe_path(frame_id, runtime_data_dir))
    if not isinstance(data, dict):
        raise TaskFramePersistenceError("TaskFrame artifact must be a JSON object.")
    return data


def taskframe_exists(
    frame_id: str,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> bool:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem" and backend.load_taskframe(frame_id) is not None:
        return True
    return get_taskframe_path(frame_id, runtime_data_dir).is_file()


class PersistenceManager:
    def __init__(self, runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR):
        self.runtime_data_dir = Path(runtime_data_dir)

    def save_snapshot(self, frame: TaskFrame, append_ledger: bool = True) -> Path:
        if append_ledger:
            return persist_frame_update(frame, self.runtime_data_dir)
        return save_taskframe(frame, self.runtime_data_dir)

    def load_frame_dict(self, frame_id: str) -> dict[str, Any]:
        return load_taskframe_dict(frame_id, self.runtime_data_dir)

    def list_runs(self) -> list[dict[str, Any]]:
        from .run_ledger import read_ledger_records

        return read_ledger_records(self.runtime_data_dir)
