from __future__ import annotations

from runtime.manifest_loader import load_manifest
from runtime.persistence import load_taskframe_dict, save_taskframe
from runtime.persistence_backends.backend_factory import get_persistence_backend
from runtime.taskframe import create_taskframe


def test_sqlite_backend_preserves_json_artifacts(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime_data"
    monkeypatch.setenv("TASKFRAME_PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("TASKFRAME_SQLITE_DB_PATH", str(runtime_root / "taskframe_runtime.db"))
    frame = create_taskframe(load_manifest("manifests/smoke_gmail_check.manifest.json"))

    save_taskframe(frame, runtime_root)

    assert (runtime_root / "runs" / frame.frame_id / "taskframe.json").is_file()
    assert load_taskframe_dict(frame.frame_id, runtime_root)["frame_id"] == frame.frame_id
    assert get_persistence_backend(runtime_root).load_taskframe(frame.frame_id)["frame_id"] == frame.frame_id
