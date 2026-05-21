from __future__ import annotations

from typing import get_type_hints

from runtime.persistence_backends.contracts import PersistenceBackend
from runtime.persistence_backends.filesystem_backend import FilesystemPersistenceBackend
from runtime.persistence_backends.sqlite_backend import SQLitePersistenceBackend


def test_contract_exposes_required_methods() -> None:
    required = {
        "save_taskframe",
        "load_taskframe",
        "list_taskframes",
        "append_event",
        "get_event",
        "list_events",
        "save_queue_record",
        "get_queue_record",
        "append_run_ledger_record",
        "list_run_ledger_records",
        "health",
    }
    for name in required:
        assert hasattr(PersistenceBackend, name)


def test_concrete_backends_implement_contract_surface(tmp_path) -> None:
    for backend in (FilesystemPersistenceBackend(tmp_path / "fs"), SQLitePersistenceBackend(tmp_path / "runtime.db")):
        for name in ("save_taskframe", "load_taskframe", "append_event", "save_queue_record", "append_run_ledger_record", "health"):
            assert callable(getattr(backend, name))
