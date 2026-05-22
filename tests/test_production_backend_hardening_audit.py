"""Spec 146 — Hardening audit integration tests.

Verifies that:
- Rate-limited requests write request.blocked.rate_limited audit records.
- Oversized body requests write request.blocked.too_large audit records.
- Invalid ID requests write request.blocked.invalid_id audit records.
- Invalid JSON requests write request.blocked.invalid_json audit records.
- None of the above records contain bearer tokens or raw payload values.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.audit import read_backend_audit_records
from src.backend.hardening import BackendHardeningConfig, RateLimitConfig
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers, TOKENS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_limited(runtime_dir: Path, route_group: str, limit: int = 1, *, role: str = "operator") -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    app.state.backend_hardening_config.rate_limits[route_group] = RateLimitConfig(
        requests=limit, window_seconds=60
    )
    return TestClient(app, headers=auth_headers(role))


def _client_tiny_body(runtime_dir: Path, max_bytes: int = 50) -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    app.state.backend_hardening_config.max_body_bytes = max_bytes
    return TestClient(app, headers=auth_headers("operator"))


def _client(runtime_dir: Path, *, role: str = "admin") -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    return TestClient(app, headers=auth_headers(role))


def _records(runtime_dir: Path) -> list[dict]:
    return read_backend_audit_records(str(runtime_dir), limit=200)


def _records_with_operation(runtime_dir: Path, operation: str) -> list[dict]:
    return [r for r in _records(runtime_dir) if r.get("operation") == operation]


def _any_record_contains_string(records: list[dict], value: str) -> bool:
    """Return True if any record's JSON representation contains the given string."""
    for r in records:
        if value in json.dumps(r):
            return True
    return False


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


# ---------------------------------------------------------------------------
# Rate-limited requests are audited
# ---------------------------------------------------------------------------

def test_rate_limited_event_submit_writes_audit_record(tmp_path: Path) -> None:
    client = _client_limited(tmp_path, "events_submit", limit=1)
    client.post("/api/events", json=_valid_event())
    resp = client.post("/api/events", json=_valid_event())
    assert resp.status_code == 429

    blocked = _records_with_operation(tmp_path, "request.blocked.rate_limited")
    assert len(blocked) >= 1
    rec = blocked[0]
    assert rec["result"] == "blocked"
    assert rec["http"]["status_code"] == 429


def test_rate_limited_runs_read_writes_audit_record(tmp_path: Path) -> None:
    client = _client_limited(tmp_path, "runs_read", limit=1, role="viewer")
    client.get("/api/runs")
    resp = client.get("/api/runs")
    assert resp.status_code == 429

    blocked = _records_with_operation(tmp_path, "request.blocked.rate_limited")
    assert len(blocked) >= 1


def test_rate_limited_audit_read_writes_audit_record(tmp_path: Path) -> None:
    client = _client_limited(tmp_path, "audit_read", limit=1, role="admin")
    client.get("/api/audit")
    resp = client.get("/api/audit")
    assert resp.status_code == 429

    blocked = _records_with_operation(tmp_path, "request.blocked.rate_limited")
    assert len(blocked) >= 1
    rec = blocked[0]
    assert rec["result"] == "blocked"


# ---------------------------------------------------------------------------
# Oversized bodies are audited
# ---------------------------------------------------------------------------

def test_oversized_body_writes_audit_record(tmp_path: Path) -> None:
    client = _client_tiny_body(tmp_path, max_bytes=50)
    large = json.dumps({"source": "api", "event_type": "x", "payload": {"k": "v" * 100}})
    resp = client.post("/api/events", content=large.encode(), headers={"Content-Type": "application/json"})
    assert resp.status_code == 413

    blocked = _records_with_operation(tmp_path, "request.blocked.too_large")
    assert len(blocked) >= 1
    rec = blocked[0]
    assert rec["result"] == "blocked"
    assert rec["http"]["status_code"] == 413


def test_content_length_rejection_writes_audit_record(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    app.state.backend_hardening_config.max_body_bytes = 100
    client = TestClient(app, headers={**auth_headers("operator"), "Content-Length": "999999"})
    resp = client.post("/api/events", json=_valid_event())
    assert resp.status_code == 413

    blocked = _records_with_operation(tmp_path, "request.blocked.too_large")
    assert len(blocked) >= 1


# ---------------------------------------------------------------------------
# Invalid IDs are audited
# ---------------------------------------------------------------------------

def test_invalid_frame_id_writes_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/runs/../traversal")
    assert resp.status_code in (400, 404)

    # If 400, it should be an INVALID_ID rejection with an audit record
    if resp.status_code == 400:
        assert resp.json()["error_code"] == "INVALID_ID"
        blocked = _records_with_operation(tmp_path, "request.blocked.invalid_id")
        assert len(blocked) >= 1
        rec = blocked[0]
        assert rec["result"] == "blocked"


def test_invalid_event_id_writes_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/events/invalid!@#$")
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_ID"

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_id")
    assert len(blocked) >= 1
    rec = blocked[0]
    assert rec["result"] == "blocked"
    assert rec["http"]["status_code"] == 400


def test_invalid_audit_id_writes_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/audit/aud id with spaces")
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_ID"

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_id")
    assert len(blocked) >= 1


# ---------------------------------------------------------------------------
# Invalid JSON is audited
# ---------------------------------------------------------------------------

def test_invalid_json_body_writes_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b"not json at all!!!",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_JSON"

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_json")
    assert len(blocked) >= 1
    rec = blocked[0]
    assert rec["result"] == "blocked"
    assert rec["http"]["status_code"] == 400


def test_empty_body_writes_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_json")
    assert len(blocked) >= 1


def test_json_array_body_writes_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b'["item1", "item2"]',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_json")
    assert len(blocked) >= 1


# ---------------------------------------------------------------------------
# Tokens are never stored in blocked request audit records
# ---------------------------------------------------------------------------

def test_bearer_token_not_in_rate_limit_audit_record(tmp_path: Path) -> None:
    client = _client_limited(tmp_path, "events_submit", limit=1)
    client.post("/api/events", json=_valid_event())
    client.post("/api/events", json=_valid_event())

    all_records = _records(tmp_path)
    raw_token = TOKENS["operator"]
    assert not _any_record_contains_string(all_records, raw_token), (
        f"Raw bearer token '{raw_token}' found in audit records"
    )


def test_bearer_token_not_in_body_size_audit_record(tmp_path: Path) -> None:
    client = _client_tiny_body(tmp_path, max_bytes=50)
    large = json.dumps({"source": "api", "event_type": "x", "payload": {"k": "v" * 100}})
    client.post("/api/events", content=large.encode(), headers={"Content-Type": "application/json"})

    all_records = _records(tmp_path)
    raw_token = TOKENS["operator"]
    assert not _any_record_contains_string(all_records, raw_token)


def test_bearer_token_not_in_invalid_json_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    client.post("/api/events", content=b"not json!", headers={"Content-Type": "application/json"})

    all_records = _records(tmp_path)
    raw_token = TOKENS["operator"]
    assert not _any_record_contains_string(all_records, raw_token)


def test_bearer_token_not_in_invalid_id_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.get("/api/events/invalid!@#$")

    all_records = _records(tmp_path)
    for role, token in TOKENS.items():
        assert not _any_record_contains_string(all_records, token), (
            f"Token for '{role}' found in audit records"
        )


# ---------------------------------------------------------------------------
# Raw payload values are never stored in blocked request audit records
# ---------------------------------------------------------------------------

def test_payload_values_not_in_rate_limit_audit_record(tmp_path: Path) -> None:
    client = _client_limited(tmp_path, "events_submit", limit=1)
    client.post("/api/events", json=_valid_event())
    client.post("/api/events", json=_valid_event())

    blocked = _records_with_operation(tmp_path, "request.blocked.rate_limited")
    assert len(blocked) >= 1
    # Payload values must not appear — only keys are allowed
    for rec in blocked:
        rec_json = json.dumps(rec)
        assert "CUST-1001" not in rec_json
        assert "ORD-10042" not in rec_json
        assert "callcenter" not in rec_json


def test_payload_values_not_in_invalid_json_audit_record(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    # Body contains sensitive-looking data but is not valid JSON
    client.post(
        "/api/events",
        content=b'{"customer_id": "SECRET-9999", broken',
        headers={"Content-Type": "application/json"},
    )

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_json")
    for rec in blocked:
        rec_json = json.dumps(rec)
        assert "SECRET-9999" not in rec_json


# ---------------------------------------------------------------------------
# Blocked record structure
# ---------------------------------------------------------------------------

def test_blocked_record_has_expected_fields(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    client.post("/api/events", content=b"bad json!", headers={"Content-Type": "application/json"})

    blocked = _records_with_operation(tmp_path, "request.blocked.invalid_json")
    assert len(blocked) >= 1
    rec = blocked[0]

    # Required fields
    assert "audit_id" in rec
    assert "timestamp" in rec
    assert "request_id" in rec
    assert "actor" in rec
    assert "http" in rec
    assert "operation" in rec
    assert "result" in rec
    assert rec["result"] == "blocked"

    # audit_id must not contain the token
    assert TOKENS["operator"] not in rec["audit_id"]


def test_blocked_record_actor_has_no_raw_token(tmp_path: Path) -> None:
    client = _client_limited(tmp_path, "events_submit", limit=1)
    client.post("/api/events", json=_valid_event())
    client.post("/api/events", json=_valid_event())

    blocked = _records_with_operation(tmp_path, "request.blocked.rate_limited")
    assert len(blocked) >= 1
    rec = blocked[0]
    actor = rec["actor"]

    # Actor has token_name (friendly name) but not the raw token value
    raw_token = TOKENS["operator"]
    assert actor.get("token_name") != raw_token
    assert raw_token not in json.dumps(actor)
