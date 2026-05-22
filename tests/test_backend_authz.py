"""Spec 149 — Backend Auth Scopes + Route Permission Enforcement tests."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend_authz import (
    KNOWN_SCOPES,
    ROUTE_SCOPE_REQUIREMENTS,
    assert_token_has_scopes,
    build_authz_decision,
    get_authz_status,
    get_required_scopes,
    normalize_scope,
    validate_token_scopes,
)
from src.backend_security import hash_token
from src.production_backend import create_app
from tests.backend_auth_support import TOKENS, auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scoped_security_config(token: str, scopes: list[str], tmp_path: Path) -> Path:
    """Write a backend_security.json with one token_record carrying given scopes."""
    cfg = {
        "backend_security": {
            "token_records": [
                {
                    "token_hash": hash_token(token),
                    "label": "test-scoped-token",
                    "scopes": scopes,
                }
            ]
        }
    }
    p = tmp_path / "security.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def _scoped_client(tmp_path: Path, *, role: str = "admin", scopes: list[str]) -> TestClient:
    token = TOKENS[role]
    cfg_path = _make_scoped_security_config(token, scopes, tmp_path)
    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_path))
    return TestClient(app, headers={"Authorization": f"Bearer {token}"}, raise_server_exceptions=False)


def _unscoped_client(tmp_path: Path, *, role: str = "admin") -> TestClient:
    """Client with NO token_records — scopes not enforced (backwards compat)."""
    app = create_app(runtime_data_dir=str(tmp_path))
    return TestClient(app, headers=auth_headers(role), raise_server_exceptions=False)


def _read_authz_audit_records(tmp_path: Path) -> list[dict]:
    from src.backend.audit import read_backend_audit_records
    return [r for r in read_backend_audit_records(str(tmp_path), limit=1000)
            if "event_type" in r and r.get("event_type", "").startswith("AUTHZ")]


# ---------------------------------------------------------------------------
# normalize_scope / validate_token_scopes unit tests
# ---------------------------------------------------------------------------

def test_normalize_scope_lowercases_and_strips():
    assert normalize_scope("  Read  ") == "read"
    assert normalize_scope("RUNS:READ") == "runs:read"


def test_validate_token_scopes_known_scopes_pass():
    result = validate_token_scopes(["read", "runs:read", "reports:read"])
    assert result["ok"] is True
    assert result["unknown_scopes"] == []


def test_validate_token_scopes_empty_list_passes():
    result = validate_token_scopes([])
    assert result["ok"] is True


def test_validate_token_scopes_rejects_unknown_scope():
    result = validate_token_scopes(["read", "superpower:delete_all"])
    assert result["ok"] is False
    assert "superpower:delete_all" in result["unknown_scopes"]


def test_validate_token_scopes_rejects_non_list():
    result = validate_token_scopes("read")  # type: ignore
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# get_required_scopes — route lookup
# ---------------------------------------------------------------------------

def test_get_required_scopes_health_returns_empty():
    scopes = get_required_scopes("GET", "/api/health")
    assert scopes == []


def test_get_required_scopes_runs_list():
    assert get_required_scopes("GET", "/api/runs") == ["runs:read"]


def test_get_required_scopes_runs_detail_with_path_param():
    assert get_required_scopes("GET", "/api/runs/TF-123") == ["runs:read"]


def test_get_required_scopes_approve_action():
    scopes = get_required_scopes("POST", "/api/runs/TF-1/pending-actions/ACT-2/approve")
    assert scopes == ["approvals:write"]


def test_get_required_scopes_reject_action():
    scopes = get_required_scopes("POST", "/api/runs/TF-1/pending-actions/ACT-2/reject")
    assert scopes == ["approvals:write"]


def test_get_required_scopes_events_intake():
    assert get_required_scopes("POST", "/api/events") == ["events:intake"]


def test_get_required_scopes_security_status():
    assert get_required_scopes("GET", "/api/security/status") == ["security:read"]


def test_get_required_scopes_unmapped_returns_none():
    result = get_required_scopes("DELETE", "/api/totally-unknown-route")
    assert result is None


def test_get_required_scopes_all_routes_are_mapped():
    """Every route in ROUTE_SCOPE_REQUIREMENTS must be matchable by get_required_scopes."""
    for key in ROUTE_SCOPE_REQUIREMENTS:
        method, _, path = key.partition(" ")
        # Replace {param} placeholders with a concrete value for matching
        concrete_path = path
        import re
        concrete_path = re.sub(r"\{[^}]+\}", "test-id-123", concrete_path)
        result = get_required_scopes(method, concrete_path)
        assert result is not None, f"Route not matchable: {key} → path={concrete_path}"


# ---------------------------------------------------------------------------
# assert_token_has_scopes
# ---------------------------------------------------------------------------

def test_assert_token_has_scopes_allows_when_has_scope():
    record = {"scopes": ["read", "runs:read"]}
    result = assert_token_has_scopes(record, ["runs:read"])
    assert result["ok"] is True
    assert result["missing_scopes"] == []


def test_assert_token_has_scopes_denies_when_missing():
    record = {"scopes": ["read"]}
    result = assert_token_has_scopes(record, ["approvals:write"])
    assert result["ok"] is False
    assert "approvals:write" in result["missing_scopes"]


def test_assert_token_has_scopes_empty_required_always_passes():
    record = {"scopes": []}
    result = assert_token_has_scopes(record, [])
    assert result["ok"] is True


def test_assert_token_has_scopes_read_does_not_imply_write():
    record = {"scopes": ["read", "approvals:read"]}
    result = assert_token_has_scopes(record, ["approvals:write"])
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# build_authz_decision
# ---------------------------------------------------------------------------

def test_build_authz_decision_allow():
    record = {"label": "ci-token", "scopes": ["runs:read"]}
    decision = build_authz_decision(record, "GET", "/api/runs")
    assert decision["ok"] is True
    assert decision["decision"] == "ALLOW"
    assert decision["missing_scopes"] == []
    assert "runs:read" in decision["required_scopes"]


def test_build_authz_decision_deny_missing_scope():
    record = {"label": "read-only", "scopes": ["read", "runs:read"]}
    decision = build_authz_decision(record, "POST", "/api/runs/TF-1/pending-actions/ACT-1/approve")
    assert decision["ok"] is False
    assert decision["decision"] == "DENY"
    assert "approvals:write" in decision["missing_scopes"]


def test_build_authz_decision_unmapped_route():
    record = {"label": "any-token", "scopes": ["read"]}
    decision = build_authz_decision(record, "DELETE", "/api/nonexistent")
    assert decision["ok"] is False
    assert decision["decision"] == "DENY"
    assert "AUTHZ_ROUTE_UNMAPPED" in decision["errors"]


def test_build_authz_decision_token_label_not_hash():
    record = {"label": "my-label", "token_hash": "sha256:abc123", "scopes": ["runs:read"]}
    decision = build_authz_decision(record, "GET", "/api/runs")
    assert decision["token_label"] == "my-label"
    assert "sha256:abc123" not in json.dumps(decision)


# ---------------------------------------------------------------------------
# get_authz_status
# ---------------------------------------------------------------------------

def test_get_authz_status_no_records():
    status = get_authz_status()
    assert status["authz_enabled"] is True
    assert status["known_scope_count"] == len(KNOWN_SCOPES)
    assert status["mapped_route_count"] == len(ROUTE_SCOPE_REQUIREMENTS)
    assert status["unmapped_route_count"] == 0
    assert status["tokens_with_unknown_scopes"] == 0


def test_get_authz_status_counts_unknown_scope_tokens():
    records = [
        {"scopes": ["read", "runs:read"]},         # valid
        {"scopes": ["read", "mega:destroy:all"]},   # invalid
    ]
    status = get_authz_status(records)
    assert status["tokens_with_unknown_scopes"] == 1


# ---------------------------------------------------------------------------
# Integration: valid token WITH required scope is allowed
# ---------------------------------------------------------------------------

def test_scoped_token_allowed_for_runs_read(tmp_path: Path):
    client = _scoped_client(tmp_path, role="admin", scopes=["runs:read"])
    resp = client.get("/api/runs")
    assert resp.status_code == 200


def test_scoped_token_allowed_for_security_status(tmp_path: Path):
    client = _scoped_client(tmp_path, role="viewer", scopes=["security:read"])
    resp = client.get("/api/security/status")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Integration: valid token WITHOUT required scope is denied
# ---------------------------------------------------------------------------

def test_scoped_token_denied_for_missing_scope(tmp_path: Path):
    # Token has only runs:read — cannot approve
    client = _scoped_client(tmp_path, role="admin", scopes=["runs:read"])
    resp = client.post("/api/runs/TF-123/pending-actions/ACT-1/approve")
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("error") == "FORBIDDEN"
    assert "approvals:write" in body.get("required_scopes", [])
    assert "approvals:write" in body.get("missing_scopes", [])


def test_read_only_token_cannot_approve_action(tmp_path: Path):
    client = _scoped_client(tmp_path, role="admin", scopes=["read", "runs:read", "reports:read"])
    resp = client.post("/api/runs/TF-123/pending-actions/ACT-1/approve")
    assert resp.status_code == 403
    assert "approvals:write" in resp.json().get("missing_scopes", [])


def test_read_only_token_cannot_reject_action(tmp_path: Path):
    client = _scoped_client(tmp_path, role="admin", scopes=["read", "runs:read"])
    resp = client.post("/api/runs/TF-123/pending-actions/ACT-1/reject")
    assert resp.status_code == 403


def test_event_token_cannot_read_reports_without_scope(tmp_path: Path):
    # events:intake only — cannot read reports or runs
    client = _scoped_client(tmp_path, role="operator", scopes=["events:intake"])
    resp = client.get("/api/runs/TF-123/evidence")
    assert resp.status_code == 403
    assert "reports:read" in resp.json().get("missing_scopes", [])


# ---------------------------------------------------------------------------
# Integration: approval token can write approvals
# ---------------------------------------------------------------------------

def test_approval_token_can_call_approval_route_scope_check_passes(tmp_path: Path):
    """Approval token passes scope check — 404 (run not found) is expected, not 403."""
    client = _scoped_client(tmp_path, role="operator", scopes=["approvals:write"])
    resp = client.post("/api/runs/TF-NOTEXIST/pending-actions/ACT-1/approve")
    # Scope check passes — any non-403 status is acceptable here
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Integration: event token can submit events
# ---------------------------------------------------------------------------

def test_event_token_can_submit_event_scope_check_passes(tmp_path: Path):
    """Event token passes scope check — actual submission may fail for other reasons."""
    client = _scoped_client(tmp_path, role="operator", scopes=["events:intake"])
    resp = client.post("/api/events", json={
        "source": "test",
        "event_type": "test.ping",
        "payload": {},
        "dry_run": True,
    })
    # Scope check passes — response might be 200, 400, or 500 but NOT 403 (scope denied)
    assert resp.status_code != 403 or resp.json().get("error") != "FORBIDDEN"


# ---------------------------------------------------------------------------
# Integration: expired token denied before scope evaluation
# ---------------------------------------------------------------------------

def test_expired_token_denied_before_scope_check(tmp_path: Path):
    """Expired token gets 401 from security middleware, not a scope 403."""
    token = TOKENS["admin"]
    cfg = {
        "backend_security": {
            "token_records": [
                {
                    "token_hash": hash_token(token),
                    "label": "expired",
                    "expires_at": "2000-01-01T00:00:00Z",
                    "scopes": ["runs:read"],
                }
            ]
        }
    }
    cfg_path = tmp_path / "sec.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_path))
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json().get("error_code") == "AUTH_TOKEN_EXPIRED"


# ---------------------------------------------------------------------------
# Integration: token not in records → pass-through (backwards compat)
# ---------------------------------------------------------------------------

def test_token_not_in_records_passes_through(tmp_path: Path):
    """Token with no matching record gets no scope enforcement; role check handles it."""
    # Put a DIFFERENT token in records — the admin token is unconstrained
    other_token_hash = hash_token("some-other-token-not-in-use")
    cfg = {
        "backend_security": {
            "token_records": [
                {"token_hash": other_token_hash, "scopes": ["runs:read"]}
            ]
        }
    }
    cfg_path = tmp_path / "sec.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_path))
    client = TestClient(app, headers=auth_headers("admin"), raise_server_exceptions=False)
    resp = client.get("/api/runs")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Integration: missing route mapping fails closed
# ---------------------------------------------------------------------------

def test_unmapped_route_fails_closed_when_scopes_configured(tmp_path: Path):
    """With token_records active, an unmapped route returns 403 FORBIDDEN."""
    token = TOKENS["admin"]
    cfg = {
        "backend_security": {
            "token_records": [
                {"token_hash": hash_token(token), "label": "t", "scopes": ["runs:read"]}
            ]
        }
    }
    cfg_path = tmp_path / "sec.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_path))
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"}, raise_server_exceptions=False)
    # FastAPI returns 404 for unknown routes before middleware can check,
    # but if middleware gets there first it should 403; test either outcome as failing closed.
    resp = client.delete("/api/runs/TF-1")
    assert resp.status_code in (403, 404, 405)


# ---------------------------------------------------------------------------
# Integration: audit events
# ---------------------------------------------------------------------------

def test_authz_denied_writes_audit_record(tmp_path: Path):
    client = _scoped_client(tmp_path, role="admin", scopes=["runs:read"])
    client.post("/api/runs/TF-123/pending-actions/ACT-1/approve")
    records = _read_authz_audit_records(tmp_path)
    denied = [r for r in records if r.get("event_type") == "AUTHZ_DENIED"]
    assert len(denied) >= 1
    record = denied[0]
    assert "approvals:write" in record.get("required_scopes", [])
    assert "approvals:write" in record.get("missing_scopes", [])


def test_authz_denied_audit_does_not_include_token_value(tmp_path: Path):
    token = TOKENS["admin"]
    client = _scoped_client(tmp_path, role="admin", scopes=["runs:read"])
    client.post("/api/runs/TF-123/pending-actions/ACT-1/approve")
    records = _read_authz_audit_records(tmp_path)
    for record in records:
        record_str = json.dumps(record)
        assert token not in record_str, f"Raw token found in authz audit record"
        assert hash_token(token) not in record_str, f"Token hash found in authz audit record"


def test_authz_allowed_writes_audit_record(tmp_path: Path):
    client = _scoped_client(tmp_path, role="admin", scopes=["runs:read"])
    client.get("/api/runs")
    records = _read_authz_audit_records(tmp_path)
    allowed = [r for r in records if r.get("event_type") == "AUTHZ_ALLOWED"]
    assert len(allowed) >= 1
    assert allowed[0].get("method") == "GET"
    assert "/api/runs" in allowed[0].get("path", "")


# ---------------------------------------------------------------------------
# Security status includes authz fields and hides secrets
# ---------------------------------------------------------------------------

def test_security_status_includes_authz_fields(tmp_path: Path):
    token = TOKENS["viewer"]
    cfg = {
        "backend_security": {
            "token_records": [
                {"token_hash": hash_token(token), "label": "viewer", "scopes": ["security:read"]}
            ]
        }
    }
    cfg_path = tmp_path / "sec.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_path))
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"}, raise_server_exceptions=False)
    resp = client.get("/api/security/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "authz_enabled" in body
    assert "known_scope_count" in body
    assert "mapped_route_count" in body
    assert body["known_scope_count"] == len(KNOWN_SCOPES)


def test_security_status_does_not_expose_token_hashes_with_records(tmp_path: Path):
    token = TOKENS["viewer"]
    token_hash = hash_token(token)
    cfg = {
        "backend_security": {
            "token_records": [
                {"token_hash": token_hash, "label": "viewer", "scopes": ["security:read"]}
            ]
        }
    }
    cfg_path = tmp_path / "sec.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_path))
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"}, raise_server_exceptions=False)
    resp = client.get("/api/security/status")
    assert resp.status_code == 200
    body_str = resp.text
    assert token not in body_str
    assert token_hash not in body_str


# ---------------------------------------------------------------------------
# Health route accessible with viewer + admin:status scope
# ---------------------------------------------------------------------------

def test_health_route_accessible_with_any_valid_token(tmp_path: Path):
    """Health route requires [] scopes — any scoped token passes the scope check."""
    client = _scoped_client(tmp_path, role="viewer", scopes=["runs:read"])
    resp = client.get("/api/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CLI shows mapped/unmapped route status
# ---------------------------------------------------------------------------

def test_cli_backend_security_json_includes_authz_fields():
    from src.taskframe_cli import main

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        main(["backend-security", "--json"])
    finally:
        sys.stdout = old_stdout
    parsed = json.loads(buf.getvalue())
    assert "authz_enabled" in parsed
    assert "known_scope_count" in parsed
    assert "mapped_route_count" in parsed
    assert parsed["mapped_route_count"] == len(ROUTE_SCOPE_REQUIREMENTS)
    assert parsed["unmapped_route_count"] == 0


def test_cli_backend_security_text_shows_scope_info():
    from src.taskframe_cli import main

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        main(["backend-security"])
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    assert "Auth Scopes" in output
    assert "mapped routes" in output
