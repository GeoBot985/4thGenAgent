from __future__ import annotations

import json

from runtime.manifest_loader import load_manifest
from runtime.persistence import save_taskframe
from runtime.persistence_backends.migration import migrate_json_to_sqlite
from runtime.taskframe import create_taskframe


def test_migration_is_idempotent_and_skips_malformed_json(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime_data"
    frame = create_taskframe(load_manifest("manifests/smoke_gmail_check.manifest.json"))
    save_taskframe(frame, runtime_root)
    bad_dir = runtime_root / "runs" / "bad"
    bad_dir.mkdir(parents=True)
    (bad_dir / "taskframe.json").write_text("{bad json", encoding="utf-8")
    (runtime_root / "events").mkdir(parents=True, exist_ok=True)
    (runtime_root / "events" / "events.jsonl").write_text(json.dumps({"event_id": "evt_1", "source": "test", "event_type": "x", "payload": {}, "received_at": "now"}) + "\n{bad\n", encoding="utf-8")

    monkeypatch.setenv("TASKFRAME_PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("TASKFRAME_SQLITE_DB_PATH", str(runtime_root / "taskframe_runtime.db"))
    first = migrate_json_to_sqlite(runtime_root)
    second = migrate_json_to_sqlite(runtime_root)

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["taskframe_count"] == second["taskframe_count"] == 1
    assert any("Malformed" in warning for warning in first["warnings"])
