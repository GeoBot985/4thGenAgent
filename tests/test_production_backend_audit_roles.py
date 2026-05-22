"""Spec 145 — Audit role enforcement tests.

Proves that:
- Forbidden role (viewer on operator route) writes auth.forbidden.
- Viewer cannot read /api/audit.
- Operator cannot read /api/audit.
- Admin can read /api/audit.
- Audit read attempts are themselves audited.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.audit import read_backend_audit_records
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app(runtime_dir: Path) -> object:
    return create_app(runtime_data_dir=str(runtime_dir))


def _client(runtime_dir: Path, role: str) -> TestClient:
    return TestClient(_app(runtime_dir), headers=auth_headers(role))


def _records(runtime_dir: Path) -> list[dict]:
    return read_backend_audit_records(str(runtime_dir), limit=10_000)


def _ops(runtime_dir: Path) -> list[str]:
    return [r.get("operation", "") for r in _records(runtime_dir)]


# ---------------------------------------------------------------------------
# auth.forbidden
# ---------------------------------------------------------------------------

def test_viewer_on_operator_route_writes_auth_forbidden(tmp_path: Path) -> None:
    client = _client(tmp_path, "viewer")
    resp = client.post("/api/events", json={
        "source": "api",
        "event_type": "customer.message.received",
        "payload": {"customer_id": "x", "message": "y", "channel": "z"},
    })
    assert resp.status_code == 403

    ops = _ops(tmp_path)
    assert "auth.forbidden" in ops


def test_auth_forbidden_record_shape(tmp_path: Path) -> None:
    client = _client(tmp_path, "viewer")
    client.post("/api/events", json={
        "source": "api",
        "event_type": "customer.message.received",
        "payload": {"customer_id": "x", "message": "y", "channel": "z"},
    })

    records = [r for r in _records(tmp_path) if r.get("operation") == "auth.forbidden"]
    assert records
    rec = records[0]
    assert rec["result"] == "failure"
    assert rec["security"]["auth_result"] == "forbidden"
    assert rec["http"]["status_code"] == 403
    assert rec["actor"]["role"] == "viewer"
    assert rec["request_id"]


# ---------------------------------------------------------------------------
# /api/audit access control
# ---------------------------------------------------------------------------

def test_viewer_cannot_read_audit(tmp_path: Path) -> None:
    client = _client(tmp_path, "viewer")
    resp = client.get("/api/audit")
    assert resp.status_code == 403


def test_operator_cannot_read_audit(tmp_path: Path) -> None:
    client = _client(tmp_path, "operator")
    resp = client.get("/api/audit")
    assert resp.status_code == 403


def test_admin_can_read_audit(tmp_path: Path) -> None:
    # First generate some records
    _client(tmp_path, "admin").get("/api/runs")

    client = _client(tmp_path, "admin")
    resp = client.get("/api/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["records"], list)
    assert data["count"] >= 1


def test_viewer_audit_attempt_is_forbidden_and_audited(tmp_path: Path) -> None:
    client = _client(tmp_path, "viewer")
    client.get("/api/audit")

    # The forbidden attempt itself should be in the audit log
    ops = _ops(tmp_path)
    assert "auth.forbidden" in ops


def test_operator_audit_attempt_is_forbidden_and_audited(tmp_path: Path) -> None:
    client = _client(tmp_path, "operator")
    client.get("/api/audit")

    ops = _ops(tmp_path)
    assert "auth.forbidden" in ops


# ---------------------------------------------------------------------------
# audit.list is itself audited
# ---------------------------------------------------------------------------

def test_admin_audit_list_is_itself_audited(tmp_path: Path) -> None:
    _client(tmp_path, "admin").get("/api/runs")

    client = _client(tmp_path, "admin")
    client.get("/api/audit")

    ops = _ops(tmp_path)
    assert "audit.list" in ops


def test_admin_audit_list_record_shape(tmp_path: Path) -> None:
    _client(tmp_path, "admin").get("/api/runs")

    client = _client(tmp_path, "admin")
    client.get("/api/audit")

    records = [r for r in _records(tmp_path) if r.get("operation") == "audit.list"]
    assert records
    rec = records[0]
    assert rec["result"] == "success"
    assert rec["actor"]["role"] == "admin"
    assert rec["request_id"]


# ---------------------------------------------------------------------------
# /api/audit/{id} — single record read
# ---------------------------------------------------------------------------

def test_admin_can_read_single_audit_record(tmp_path: Path) -> None:
    # Seed a record
    _client(tmp_path, "admin").get("/api/runs")

    # Fetch all records to get an audit_id
    client = _client(tmp_path, "admin")
    resp = client.get("/api/audit")
    assert resp.status_code == 200
    records = resp.json()["records"]
    assert records

    audit_id = records[0]["audit_id"]
    resp2 = client.get(f"/api/audit/{audit_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["ok"] is True
    assert data["record"]["audit_id"] == audit_id


def test_audit_read_single_record_is_itself_audited(tmp_path: Path) -> None:
    _client(tmp_path, "admin").get("/api/runs")

    client = _client(tmp_path, "admin")
    resp = client.get("/api/audit")
    audit_id = resp.json()["records"][0]["audit_id"]
    client.get(f"/api/audit/{audit_id}")

    ops = _ops(tmp_path)
    assert "audit.read" in ops


def test_viewer_cannot_read_single_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, "viewer")
    resp = client.get("/api/audit/aud-some-id")
    assert resp.status_code == 403


def test_operator_cannot_read_single_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, "operator")
    resp = client.get("/api/audit/aud-some-id")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /api/audit filter query parameters
# ---------------------------------------------------------------------------

def test_audit_list_filter_by_operation(tmp_path: Path) -> None:
    _client(tmp_path, "admin").get("/api/runs")
    _client(tmp_path, "admin").get("/api/health")

    client = _client(tmp_path, "admin")
    resp = client.get("/api/audit?operation=runs.list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    for rec in data["records"]:
        assert rec["operation"] == "runs.list"


def test_audit_list_filter_by_role(tmp_path: Path) -> None:
    _client(tmp_path, "viewer").get("/api/runs")
    _client(tmp_path, "admin").get("/api/runs")

    client = _client(tmp_path, "admin")
    resp = client.get("/api/audit?role=viewer")
    assert resp.status_code == 200
    data = resp.json()
    for rec in data["records"]:
        assert rec["actor"]["role"] == "viewer"


def test_audit_list_filter_by_result(tmp_path: Path) -> None:
    _unauthenticated = TestClient(create_app(runtime_data_dir=str(tmp_path)))
    _unauthenticated.get("/api/runs")
    _client(tmp_path, "admin").get("/api/runs")

    client = _client(tmp_path, "admin")
    resp = client.get("/api/audit?result=failure")
    assert resp.status_code == 200
    data = resp.json()
    for rec in data["records"]:
        assert rec["result"] == "failure"
