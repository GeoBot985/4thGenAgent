from __future__ import annotations

from runtime.persistence_backends.backend_factory import get_persistence_backend


def test_factory_defaults_to_filesystem(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("TASKFRAME_PERSISTENCE_BACKEND", raising=False)
    backend = get_persistence_backend(tmp_path)
    assert backend.backend_name == "filesystem"


def test_factory_selects_sqlite(monkeypatch, tmp_path) -> None:
    db = tmp_path / "custom.db"
    monkeypatch.setenv("TASKFRAME_PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("TASKFRAME_SQLITE_DB_PATH", str(db))
    backend = get_persistence_backend(tmp_path)
    assert backend.backend_name == "sqlite"
    assert str(db) in backend.health()["sqlite_path"]
