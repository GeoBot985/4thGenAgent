from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .backend_factory import get_persistence_backend
from .sqlite_backend import SCHEMA_VERSION, SQLitePersistenceBackend


def persistence_status(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    backend = get_persistence_backend(runtime_data_dir)
    health = backend.health()
    return {
        "active_backend": getattr(backend, "backend_name", "filesystem"),
        **health,
        "ok": True,
    }


def init_persistence(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    backend = get_persistence_backend(runtime_data_dir)
    if getattr(backend, "backend_name", "") != "sqlite":
        return {"ok": True, "active_backend": "filesystem", "message": "Filesystem backend requires no schema initialization."}
    assert isinstance(backend, SQLitePersistenceBackend)
    backend.init_schema()
    verify = backend.verify_schema()
    return {"ok": bool(verify.get("ok")), "active_backend": "sqlite", "sqlite_path": str(backend.db_path), **verify}


def migrate_json_to_sqlite(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    backend = get_persistence_backend(runtime_root)
    if getattr(backend, "backend_name", "") != "sqlite":
        return {
            "ok": True,
            "active_backend": getattr(backend, "backend_name", "filesystem"),
            "message": "Filesystem backend is active; no SQLite migration was performed.",
            "migrated": {"taskframes": 0, "events": 0, "event_queue": 0, "run_ledger": 0},
            "warnings": [],
        }
    assert isinstance(backend, SQLitePersistenceBackend)
    backend.init_schema()

    warnings: list[str] = []
    migrated = {"taskframes": 0, "events": 0, "event_queue": 0, "run_ledger": 0}
    for path in (runtime_root / "runs").glob("*/taskframe.json"):
        data = _read_json_object(path, warnings)
        if data is None:
            continue
        backend.save_taskframe(data)
        migrated["taskframes"] += 1

    for record in _read_jsonl(runtime_root / "events" / "events.jsonl", warnings):
        backend.append_event(record)
        migrated["events"] += 1

    queue_index = _read_json_object(runtime_root / "events" / "event_queue_index.json", warnings)
    if isinstance(queue_index, dict):
        for item in queue_index.values():
            if isinstance(item, dict):
                backend.save_queue_record(item)
                migrated["event_queue"] += 1
            else:
                warnings.append("Malformed queue index record skipped.")

    for line_no, record in enumerate(_read_jsonl(runtime_root / "runs" / "index.jsonl", warnings), start=1):
        key_source = json.dumps(record, sort_keys=True, ensure_ascii=False)
        migration_key = hashlib.sha256(f"runs/index.jsonl:{line_no}:{key_source}".encode("utf-8")).hexdigest()
        with backend._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO run_ledger(migration_key, frame_id, manifest_id, state, created_at, updated_at, recorded_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                """,
                (
                    migration_key,
                    str(record.get("frame_id", "") or ""),
                    str(record.get("manifest_id", "") or ""),
                    str(record.get("state", "") or ""),
                    str(record.get("created_at", "") or ""),
                    str(record.get("updated_at", "") or ""),
                    json.dumps(record, ensure_ascii=False, sort_keys=True),
                ),
            )
        if cursor.rowcount:
            migrated["run_ledger"] += 1

    health = backend.health()
    return {
        "ok": True,
        "active_backend": "sqlite",
        "sqlite_path": str(backend.db_path),
        "migrated": migrated,
        "warnings": warnings,
        "taskframe_count": health.get("taskframe_count", 0),
        "event_count": health.get("event_count", 0),
        "run_ledger_count": health.get("run_ledger_count", 0),
    }


def verify_persistence(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    backend = get_persistence_backend(runtime_root)
    if getattr(backend, "backend_name", "") == "filesystem":
        return {
            "ok": True,
            "active_backend": "filesystem",
            "schema_version": None,
            "required_tables_exist": True,
            "required_indexes_exist": True,
            "json_frame_count": sum(1 for _ in (runtime_root / "runs").glob("*/taskframe.json")) if (runtime_root / "runs").is_dir() else 0,
            "migrated_frame_count": 0,
            "warnings": [],
        }
    assert isinstance(backend, SQLitePersistenceBackend)
    backend.init_schema()
    schema = backend.verify_schema()
    health = backend.health()
    json_count = _count_readable_taskframes(runtime_root)
    migrated_count = int(health.get("taskframe_count", 0) or 0)
    count_ok = migrated_count >= json_count
    return {
        "ok": bool(schema.get("ok")) and count_ok,
        "active_backend": "sqlite",
        "sqlite_path": str(backend.db_path),
        "db_opens": True,
        "schema_version": schema.get("schema_version"),
        "required_schema_version": SCHEMA_VERSION,
        "required_tables_exist": not schema.get("missing_tables"),
        "required_indexes_exist": not schema.get("missing_indexes"),
        "missing_tables": schema.get("missing_tables", []),
        "missing_indexes": schema.get("missing_indexes", []),
        "json_frame_count": json_count,
        "migrated_frame_count": migrated_count,
        "malformed_record_count": schema.get("malformed_record_count", 0),
    }


def _read_json_object(path: Path, warnings: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"Malformed JSON skipped: {path} ({exc})")
        return None
    if not isinstance(raw, dict):
        warnings.append(f"Malformed JSON skipped: {path} (root is not object)")
        return None
    return raw


def _read_jsonl(path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"Malformed JSONL skipped: {path}:{line_no} ({exc})")
            continue
        if isinstance(raw, dict):
            rows.append(raw)
        else:
            warnings.append(f"Malformed JSONL skipped: {path}:{line_no} (row is not object)")
    return rows


def _count_readable_taskframes(runtime_root: Path) -> int:
    warnings: list[str] = []
    return sum(1 for path in (runtime_root / "runs").glob("*/taskframe.json") if _read_json_object(path, warnings) is not None)


def with_sqlite_env(db_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["TASKFRAME_PERSISTENCE_BACKEND"] = "sqlite"
    env["TASKFRAME_SQLITE_DB_PATH"] = str(db_path)
    return env
