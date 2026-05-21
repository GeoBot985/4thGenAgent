from __future__ import annotations

import sqlite3

from runtime.event_queue import build_queue_record
from runtime.events import create_event, event_to_dict
from runtime.manifest_loader import load_manifest
from runtime.persistence_backends.sqlite_backend import REQUIRED_TABLES, SQLitePersistenceBackend
from runtime.run_ledger import build_ledger_record
from runtime.taskframe import create_taskframe, to_dict


def _frame_dict() -> dict:
    frame = create_taskframe(load_manifest("manifests/smoke_gmail_check.manifest.json"))
    frame.pending_actions.append({"action_id": "pa_1", "tool": "gmail/send", "status": "PENDING_APPROVAL", "token": "secret-token"})
    frame.validations.append({"validation_id": "val_1", "validation_type": "field", "ok": True})
    return to_dict(frame)


def test_sqlite_schema_initializes(tmp_path) -> None:
    backend = SQLitePersistenceBackend(tmp_path / "runtime.db")
    backend.init_schema()
    with sqlite3.connect(tmp_path / "runtime.db") as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(REQUIRED_TABLES).issubset(tables)
    assert backend.verify_schema()["ok"] is True


def test_taskframe_event_queue_and_ledger_roundtrip(tmp_path) -> None:
    backend = SQLitePersistenceBackend(tmp_path / "runtime.db")
    frame = _frame_dict()
    backend.save_taskframe(frame)
    assert backend.load_taskframe(frame["frame_id"])["frame_id"] == frame["frame_id"]
    assert backend.list_taskframes()[0]["frame_id"] == frame["frame_id"]

    event = event_to_dict(create_event("manual.test", "operator", payload={"x": 1}))
    backend.append_event(event)
    assert backend.get_event(event["event_id"])["payload"]["x"] == 1

    queue = build_queue_record(event, status="COMPLETED", linked_frame_id=frame["frame_id"])
    backend.save_queue_record(queue)
    assert backend.get_queue_record(event["event_id"])["linked_frame_id"] == frame["frame_id"]

    ledger = {"frame_id": frame["frame_id"], "manifest_id": frame["manifest_id"], "state": frame["state"], "created_at": frame["created_at"], "updated_at": frame["updated_at"]}
    backend.append_run_ledger_record(ledger)
    assert backend.list_run_ledger_records()[-1]["frame_id"] == frame["frame_id"]


def test_pending_action_fields_queryable_and_secrets_redacted(tmp_path) -> None:
    backend = SQLitePersistenceBackend(tmp_path / "runtime.db")
    frame = _frame_dict()
    backend.save_taskframe(frame)
    with sqlite3.connect(tmp_path / "runtime.db") as conn:
        row = conn.execute("SELECT action_id, status, payload_json FROM pending_actions WHERE action_id='pa_1'").fetchone()
    assert row[0] == "pa_1"
    assert row[1] == "PENDING_APPROVAL"
    assert "secret-token" not in row[2]
    assert "[REDACTED]" in row[2]
