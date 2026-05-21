from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import RunLedgerError
from .models import TaskFrame
from .persistence import DEFAULT_RUNTIME_DATA_DIR, RUNS_DIR_NAME, ensure_dir
from .taskframe import build_taskframe_summary, json_safe


def get_ledger_path(runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR) -> Path:
    return Path(runtime_data_dir) / RUNS_DIR_NAME / "index.jsonl"


def build_ledger_record(frame: TaskFrame) -> dict[str, Any]:
    summary = build_taskframe_summary(frame)
    trigger = dict(frame.trigger or {})
    return {
        "frame_id": frame.frame_id,
        "manifest_id": frame.manifest_id,
        "state": frame.state,
        "created_at": frame.created_at,
        "updated_at": frame.updated_at,
        "trigger_source": str(trigger.get("source", "")),
        "trigger_event_type": str(trigger.get("event_type", "")),
        "step_count": summary["step_count"],
        "completed_steps": summary["completed_steps"],
        "failed_steps": summary["failed_steps"],
        "skipped_steps": summary["skipped_steps"],
        "pending_action_count": summary["pending_action_count"],
        "executed_action_count": summary["executed_action_count"],
        "error_count": summary["error_count"],
        "validation_failed_count": summary["validation_failed_count"],
        "output_keys": list(summary["output_keys"]),
        "artifact_dir": str(Path(DEFAULT_RUNTIME_DATA_DIR) / RUNS_DIR_NAME / frame.frame_id),
    }


def append_ledger_record(
    frame: TaskFrame,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> None:
    ledger_path = get_ledger_path(runtime_data_dir)
    ensure_dir(ledger_path.parent)
    record = json_safe(build_ledger_record(frame))
    record["artifact_dir"] = str(Path(runtime_data_dir) / RUNS_DIR_NAME / frame.frame_id)
    try:
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        from .persistence_backends.backend_factory import get_persistence_backend

        backend = get_persistence_backend(runtime_data_dir)
        if getattr(backend, "backend_name", "filesystem") != "filesystem":
            backend.append_run_ledger_record(record)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise RunLedgerError(f"Unable to append ledger record: {ledger_path}") from exc


def read_ledger_records(
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> list[dict[str, Any]]:
    from .persistence_backends.backend_factory import get_persistence_backend

    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "filesystem") != "filesystem":
        records = backend.list_run_ledger_records(limit=10_000_000)
        if records:
            return records
    ledger_path = get_ledger_path(runtime_data_dir)
    if not ledger_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with ledger_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise RunLedgerError(f"Unable to read ledger records: {ledger_path}") from exc
    return records


def find_ledger_record(
    frame_id: str,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
) -> dict[str, Any] | None:
    for record in reversed(read_ledger_records(runtime_data_dir)):
        if record.get("frame_id") == frame_id:
            return record
    return None
