from __future__ import annotations

import os
from pathlib import Path

from .contracts import PersistenceBackend
from .filesystem_backend import FilesystemPersistenceBackend
from .sqlite_backend import DEFAULT_SQLITE_DB_PATH, SQLitePersistenceBackend


def get_persistence_backend(runtime_data_dir: str | Path = "runtime_data") -> PersistenceBackend:
    backend = os.environ.get("TASKFRAME_PERSISTENCE_BACKEND", "filesystem").strip().lower() or "filesystem"
    if backend == "sqlite":
        db_path = os.environ.get("TASKFRAME_SQLITE_DB_PATH", "").strip()
        resolved = Path(db_path) if db_path else Path(runtime_data_dir) / DEFAULT_SQLITE_DB_PATH.name
        return SQLitePersistenceBackend(resolved)
    if backend == "filesystem":
        return FilesystemPersistenceBackend(runtime_data_dir)
    raise ValueError(f"Unsupported TaskFrame persistence backend: {backend}")
