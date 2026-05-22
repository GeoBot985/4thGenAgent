"""Spec 145 — Backend audit trail tests.

Covers:
- Protected requests write audit records.
- Auth failures (missing/invalid token) write correct operation names.
- runs.list, events.submit, events.list, events.read written for matching operations.
- pending_action.approve / pending_action.reject.
- Duplicate event submission records duplicate outcome.
- Audit records include request_id.
- X-Request-ID accepted when safe; unsafe values are replaced.
- Health endpoint reports audit status.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.audit import get_audit_ledger_path, read_backend_audit_records
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client(runtime_dir: Path, *, role: str = "admin") -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    return TestClient(app, headers=auth_headers(role))


def _unauthenticated_client(runtime_dir: Path) -> TestClient:
    return TestClient(create_app(runtime_data_dir=str(runtime_dir)))


def _records(runtime_dir: Path) -> list[dict]:
    return read_backend_audit_records(str(runtime_dir), limit=1000)


def _ops(runtime_dir: Path) -> list[str]:
    return [r.get("operation", "") for r in _records(runtime_dir)]


def _seed_pending_action(runtime_root: Path) -> tuple[str, str]:
    from runtime.manifest_loader import load_manifest
    from runtime.persistence import PersistenceManager
    from runtime.run_ledger import append_ledger_record
    from runtime.taskframe import create_taskframe

    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "PENDING_APPROVAL"
    action_id = "action-001"
    frame.pending_actions.append(
        {
            "action_id": action_id,
            "tool": "write_sheet",
            "output_alias": "report",
            "args": {"sheet_id": "abc123"},
            "status": "PENDING_APPROVAL",
            "requested_at": "2026-01-01T00:00:00Z",
        }
    )
    PersistenceManager(runtime_root).save_snapshot(frame)
    append_ledger_record(frame, runtime_data_dir=runtime_root)
    return frame.frame_id, action_id


# ---------------------------------------------------------------------------
# Auth failure auditing
# ---------------------------------------------------------------------------

def test_missing_token_writes_auth_missing_token(tmp_path: Path) -> None:
    client = _unauthenticated_client(tmp_path)
    client.get("/api/runs")

    ops = _ops(tmp_path)
    assert "auth.missing_token" in ops


def test_invalid_token_writes_auth_invalid_token(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers={"Authorization": "Bearer totally-wrong-token"})
    client.get("/api/runs")

    ops = _ops(tmp_path)
    assert "auth.invalid_token" in ops


def test_auth_missing_token_record_shape(tmp_path: Path) -> None:
    _unauthenticated_client(tmp_path).get("/api/health")
    records = _records(tmp_path)
    # health requires viewer; unauthenticated → AUTH_REQUIRED
    auth_records = [r for r in records if r.get("operation") == "auth.missing_token"]
    assert auth_records, "Expected at least one auth.missing_token record"
    rec = auth_records[0]
    assert rec["result"] == "failure"
    assert rec["security"]["auth_result"] == "missing"
    assert rec["http"]["status_code"] == 401
    assert rec["request_id"]


def test_invalid_token_record_shape(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers={"Authorization": "Bearer bad-token"})
    client.get("/api/runs")
    records = [r for r in _records(tmp_path) if r.get("operation") == "auth.invalid_token"]
    assert records
    rec = records[0]
    assert rec["security"]["auth_result"] == "invalid"
    assert rec["http"]["status_code"] == 401


# ---------------------------------------------------------------------------
# runs.list
# ---------------------------------------------------------------------------

def test_viewer_run_list_writes_runs_list(tmp_path: Path) -> None:
    client = _client(tmp_path, role="viewer")
    client.get("/api/runs")
    assert "runs.list" in _ops(tmp_path)


def test_runs_list_audit_record_shape(tmp_path: Path) -> None:
    client = _client(tmp_path, role="viewer")
    client.get("/api/runs")
    records = [r for r in _records(tmp_path) if r.get("operation") == "runs.list"]
    assert records
    rec = records[0]
    assert rec["result"] == "success"
    assert rec["actor"]["role"] == "viewer"
    assert rec["request_id"]


# ---------------------------------------------------------------------------
# events.submit
# ---------------------------------------------------------------------------

def _valid_event() -> dict:
    return {
        "source": "api",
        "event_type": "customer.message.received",
        "payload": {
            "customer_id": "CUST-1001",
            "message": "Where is my order ORD-10042?",
            "channel": "callcenter",
        },
    }


def test_operator_event_submission_writes_events_submit(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    client.post("/api/events", json=_valid_event())
    assert "events.submit" in _ops(tmp_path)


def test_events_submit_record_links_event_id(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post("/api/events", json=_valid_event())
    event_id = resp.json().get("event_id", "")
    records = [r for r in _records(tmp_path) if r.get("operation") == "events.submit"]
    assert records
    rec = records[0]
    assert rec["target"]["event_id"] == event_id
    assert rec["result"] == "success"


def test_duplicate_event_submission_writes_duplicate_result(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    payload = {**_valid_event(), "idempotency_key": "dup-test-key"}
    client.post("/api/events", json=payload)
    client.post("/api/events", json=payload)
    records = [r for r in _records(tmp_path) if r.get("operation") == "events.submit"]
    results = [r["result"] for r in records]
    assert "duplicate" in results


# ---------------------------------------------------------------------------
# pending_action.approve / reject
# ---------------------------------------------------------------------------

def test_approve_pending_action_writes_audit(tmp_path: Path) -> None:
    frame_id, action_id = _seed_pending_action(tmp_path)
    client = _client(tmp_path, role="operator")
    client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/approve")
    assert "pending_action.approve" in _ops(tmp_path)


def test_approve_audit_record_links_frame_and_action(tmp_path: Path) -> None:
    frame_id, action_id = _seed_pending_action(tmp_path)
    client = _client(tmp_path, role="operator")
    client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/approve")
    records = [r for r in _records(tmp_path) if r.get("operation") == "pending_action.approve"]
    assert records
    rec = records[0]
    assert rec["target"]["frame_id"] == frame_id
    assert rec["target"]["action_id"] == action_id
    assert rec["result"] == "success"


def test_reject_pending_action_writes_audit(tmp_path: Path) -> None:
    frame_id, action_id = _seed_pending_action(tmp_path)
    client = _client(tmp_path, role="operator")
    client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/reject")
    assert "pending_action.reject" in _ops(tmp_path)


def test_reject_audit_record_links_frame_and_action(tmp_path: Path) -> None:
    frame_id, action_id = _seed_pending_action(tmp_path)
    client = _client(tmp_path, role="operator")
    client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/reject")
    records = [r for r in _records(tmp_path) if r.get("operation") == "pending_action.reject"]
    assert records
    rec = records[0]
    assert rec["target"]["frame_id"] == frame_id
    assert rec["target"]["action_id"] == action_id
    assert rec["result"] == "success"


# ---------------------------------------------------------------------------
# request_id
# ---------------------------------------------------------------------------

def test_audit_records_include_request_id(tmp_path: Path) -> None:
    _client(tmp_path).get("/api/runs")
    records = _records(tmp_path)
    assert records
    for rec in records:
        assert rec.get("request_id"), f"Record missing request_id: {rec}"


def test_x_request_id_header_accepted_when_safe(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers={**auth_headers("admin"), "X-Request-ID": "safe-id-abc123"})
    client.get("/api/runs")
    records = [r for r in _records(tmp_path) if r.get("operation") == "runs.list"]
    assert records
    assert records[0]["request_id"] == "safe-id-abc123"


def test_unsafe_request_id_is_replaced(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    unsafe_ids = ["../traversal", "id with spaces", "id\nwith\nnewlines", "a" * 200]
    for unsafe_id in unsafe_ids:
        client = TestClient(app, headers={**auth_headers("admin"), "X-Request-ID": unsafe_id})
        client.get("/api/runs")
    records = [r for r in _records(tmp_path) if r.get("operation") == "runs.list"]
    for rec in records:
        rid = rec["request_id"]
        assert "../" not in rid
        assert "\n" not in rid
        assert len(rid) <= 128


def test_x_request_id_returned_in_response_header(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers={**auth_headers("admin"), "X-Request-ID": "echo-me-123"})
    resp = client.get("/api/runs")
    assert resp.headers.get("x-request-id") == "echo-me-123"


# ---------------------------------------------------------------------------
# Health endpoint audit status
# ---------------------------------------------------------------------------

def test_health_reports_audit_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "audit" in data
    audit = data["audit"]
    assert audit["enabled"] is True
    assert "ledger_path" in audit
    assert "record_count_available" in audit


def test_health_audit_record_count_available_after_first_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # First request writes an audit record; health check shows it's available.
    client.get("/api/runs")
    resp = client.get("/api/health")
    assert resp.json()["audit"]["record_count_available"] is True


# ---------------------------------------------------------------------------
# Audit JSONL file integrity
# ---------------------------------------------------------------------------

def test_audit_jsonl_is_valid_per_line(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.get("/api/runs")
    client.get("/api/health")

    ledger = get_audit_ledger_path(str(tmp_path))
    assert ledger.is_file()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            record = json.loads(line)  # must not raise
            assert "audit_id" in record
            assert "timestamp" in record
            assert "operation" in record
