"""Spec 148 — Backend security headers, CORS, and token hardening tests."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend_security import (
    AuthSecurityConfig,
    BackendSecurityConfig,
    CORSConfig,
    SecurityHeadersConfig,
    get_security_status,
    hash_token,
    load_security_config,
    parse_token_metadata,
    redact_token,
    verify_token,
)
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client(runtime_dir: Path, *, role: str = "admin", **kwargs) -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir), **kwargs)
    return TestClient(app, headers=auth_headers(role), raise_server_exceptions=False)


def _app(runtime_dir: Path, **kwargs):
    return create_app(runtime_data_dir=str(runtime_dir), **kwargs)


def _default_config() -> BackendSecurityConfig:
    return load_security_config(None)


# ---------------------------------------------------------------------------
# hash_token unit tests
# ---------------------------------------------------------------------------

def test_hash_token_returns_sha256_prefix():
    result = hash_token("my-secret-token")
    assert result.startswith("sha256:")


def test_hash_token_is_deterministic():
    assert hash_token("abc") == hash_token("abc")


def test_hash_token_differs_for_different_tokens():
    assert hash_token("token-a") != hash_token("token-b")


def test_hash_token_expected_value():
    token = "hello"
    expected_hex = hashlib.sha256(b"hello").hexdigest()
    assert hash_token(token) == f"sha256:{expected_hex}"


# ---------------------------------------------------------------------------
# verify_token unit tests
# ---------------------------------------------------------------------------

def test_verify_token_returns_true_when_hash_matches():
    token = "my-token"
    h = hash_token(token)
    assert verify_token(token, [h]) is True


def test_verify_token_returns_false_for_wrong_token():
    token = "my-token"
    h = hash_token("other-token")
    assert verify_token(token, [h]) is False


def test_verify_token_returns_false_for_empty_token():
    h = hash_token("token")
    assert verify_token("", [h]) is False


def test_verify_token_returns_false_for_empty_hashes():
    assert verify_token("token", []) is False


def test_verify_token_checks_multiple_hashes():
    token = "token-b"
    hashes = [hash_token("token-a"), hash_token("token-b"), hash_token("token-c")]
    assert verify_token(token, hashes) is True


# ---------------------------------------------------------------------------
# redact_token unit tests
# ---------------------------------------------------------------------------

def test_redact_token_short_returns_stars():
    assert redact_token("short") == "***"
    assert redact_token("") == "***"


def test_redact_token_long_shows_first_and_last_four():
    result = redact_token("abcdefghijklmnop")
    assert result.startswith("abcd")
    assert result.endswith("mnop")
    assert "..." in result


def test_redact_token_exactly_8_chars_returns_stars():
    assert redact_token("12345678") == "***"


def test_redact_token_nine_chars_is_redacted():
    result = redact_token("123456789")
    assert result.startswith("1234")
    assert result.endswith("6789")


# ---------------------------------------------------------------------------
# parse_token_metadata unit tests
# ---------------------------------------------------------------------------

def test_parse_token_metadata_not_expired():
    record = {
        "token_hash": "sha256:abc",
        "label": "test-token",
        "created_at": "2024-01-01T00:00:00Z",
        "expires_at": "2099-12-31T23:59:59Z",
        "scopes": ["read"],
    }
    meta = parse_token_metadata(record)
    assert meta["is_expired"] is False
    assert meta["label"] == "test-token"
    assert meta["scopes"] == ["read"]


def test_parse_token_metadata_expired():
    record = {
        "token_hash": "sha256:abc",
        "label": "old-token",
        "expires_at": "2000-01-01T00:00:00Z",
    }
    meta = parse_token_metadata(record)
    assert meta["is_expired"] is True


def test_parse_token_metadata_no_expiry_not_expired():
    record = {"token_hash": "sha256:abc", "label": "no-expiry"}
    meta = parse_token_metadata(record)
    assert meta["is_expired"] is False


# ---------------------------------------------------------------------------
# load_security_config
# ---------------------------------------------------------------------------

def test_load_security_config_returns_defaults_when_no_path():
    config = load_security_config(None)
    assert isinstance(config, BackendSecurityConfig)
    assert config.enabled is True
    assert config.security_headers.enabled is True
    assert config.cors.enabled is True


def test_load_security_config_fails_closed_on_invalid_json(tmp_path: Path):
    bad_cfg = tmp_path / "bad.json"
    bad_cfg.write_text("not json{{{", encoding="utf-8")
    config = load_security_config(bad_cfg)
    assert config.cors.allowed_origins == []


def test_load_security_config_fails_closed_on_non_dict_json(tmp_path: Path):
    bad_cfg = tmp_path / "bad.json"
    bad_cfg.write_text("[1, 2, 3]", encoding="utf-8")
    config = load_security_config(bad_cfg)
    assert config.cors.allowed_origins == []


def test_load_security_config_loads_valid_json(tmp_path: Path):
    cfg_data = {
        "backend_security": {
            "enabled": True,
            "cors": {
                "enabled": True,
                "allowed_origins": ["http://myapp.example"],
            },
            "auth": {
                "token_required": False,
            },
        }
    }
    cfg_file = tmp_path / "security.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")
    config = load_security_config(cfg_file)
    assert "http://myapp.example" in config.cors.allowed_origins
    assert config.auth.token_required is False


def test_load_security_config_nonexistent_path_returns_defaults():
    config = load_security_config("/nonexistent/path/security.json")
    assert config.enabled is True


# ---------------------------------------------------------------------------
# Security headers on responses
# ---------------------------------------------------------------------------

def test_security_headers_present_on_successful_response(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.get("/api/runs")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert "Cache-Control" in resp.headers
    assert "Content-Security-Policy" in resp.headers


def test_security_headers_present_on_auth_failure(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/runs")
    assert resp.status_code == 401
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_security_headers_present_on_404(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.get("/api/does-not-exist")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ---------------------------------------------------------------------------
# CORS — no origin header passes through
# ---------------------------------------------------------------------------

def test_no_origin_header_passes_through(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.get("/api/runs")
    assert resp.status_code in (200, 404)
    assert "CORS_ORIGIN_BLOCKED" not in resp.text


# ---------------------------------------------------------------------------
# CORS — allowlisted origin gets CORS headers
# ---------------------------------------------------------------------------

def test_allowlisted_origin_gets_cors_headers(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.get("/api/runs", headers={"Origin": "http://127.0.0.1:7860"})
    assert resp.status_code != 403
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:7860"


# ---------------------------------------------------------------------------
# CORS — non-allowlisted origin is blocked
# ---------------------------------------------------------------------------

def test_non_allowlisted_origin_is_blocked(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.get("/api/runs", headers={"Origin": "http://evil.example.com"})
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("error_code") == "CORS_ORIGIN_BLOCKED"


def test_non_allowlisted_origin_blocked_without_auth_header(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/runs", headers={"Origin": "http://attacker.example"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# CORS — OPTIONS preflight for allowlisted origin returns 200
# ---------------------------------------------------------------------------

def test_options_preflight_allowlisted_origin(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.options(
        "/api/runs",
        headers={
            "Origin": "http://127.0.0.1:7860",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:7860"


def test_options_preflight_non_allowlisted_origin(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.options(
        "/api/runs",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# CORS — wildcard blocked outside dev/test
# ---------------------------------------------------------------------------

def test_wildcard_cors_blocked_outside_dev(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TASKFRAME_ENV", "demo")
    cfg_data = {
        "backend_security": {
            "cors": {"allowed_origins": ["*"]},
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, headers=auth_headers("admin"), raise_server_exceptions=False)

    # With wildcard stripped, any explicit origin should be blocked
    resp = client.get("/api/runs", headers={"Origin": "http://anything.example"})
    assert resp.status_code == 403


def test_wildcard_cors_allowed_in_dev(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TASKFRAME_ENV", "dev")
    cfg_data = {
        "backend_security": {
            "cors": {"allowed_origins": ["*"]},
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, headers=auth_headers("admin"), raise_server_exceptions=False)

    resp = client.get("/api/runs", headers={"Origin": "http://anything.example"})
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Token expiry enforcement
# ---------------------------------------------------------------------------

def test_expired_token_rejected_with_401(tmp_path: Path):
    token = "expired-test-token-abcdef"
    token_hash = hash_token(token)
    cfg_data = {
        "backend_security": {
            "token_records": [
                {
                    "token_hash": token_hash,
                    "label": "expired-token",
                    "expires_at": "2000-01-01T00:00:00Z",
                }
            ]
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("error_code") == "AUTH_TOKEN_EXPIRED"


def test_expired_token_response_contains_redacted_preview(tmp_path: Path):
    token = "expired-test-token-abcdef"
    token_hash = hash_token(token)
    cfg_data = {
        "backend_security": {
            "token_records": [
                {"token_hash": token_hash, "expires_at": "2000-01-01T00:00:00Z"}
            ]
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    body = resp.json()
    preview = body.get("token_preview", "")
    # Preview must not contain the full token
    assert token not in preview
    assert "..." in preview


def test_valid_token_record_not_rejected(tmp_path: Path):
    token = "valid-test-token-abcdef"
    token_hash = hash_token(token)
    cfg_data = {
        "backend_security": {
            "token_records": [
                {"token_hash": token_hash, "expires_at": "2099-12-31T23:59:59Z"}
            ]
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, headers=auth_headers("admin"), raise_server_exceptions=False)
    resp = client.get("/api/runs")
    # Should not be rejected as expired (auth may fail for other reasons, but not expiry)
    assert resp.status_code != 401 or resp.json().get("error_code") != "AUTH_TOKEN_EXPIRED"


def test_token_not_in_records_falls_through_to_auth(tmp_path: Path):
    cfg_data = {
        "backend_security": {
            "token_records": [
                {"token_hash": hash_token("some-other-token"), "expires_at": "2000-01-01T00:00:00Z"}
            ]
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, raise_server_exceptions=False)
    # Token not in records → fall through to auth middleware → 401 AUTH_REQUIRED or AUTH_INVALID
    resp = client.get("/api/runs", headers={"Authorization": "Bearer unknown-token"})
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("error_code") != "AUTH_TOKEN_EXPIRED"


# ---------------------------------------------------------------------------
# Token value not in audit records
# ---------------------------------------------------------------------------

def test_token_value_not_in_audit_records_on_expired_rejection(tmp_path: Path):
    from src.backend.audit import read_backend_audit_records

    token = "super-secret-token-12345678"
    token_hash = hash_token(token)
    cfg_data = {
        "backend_security": {
            "token_records": [
                {"token_hash": token_hash, "expires_at": "2000-01-01T00:00:00Z"}
            ]
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, raise_server_exceptions=False)
    client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})

    records = read_backend_audit_records(str(tmp_path), limit=100)
    for record in records:
        record_str = json.dumps(record)
        assert token not in record_str, f"Raw token found in audit record: {record_str}"


# ---------------------------------------------------------------------------
# /api/security/status endpoint
# ---------------------------------------------------------------------------

def test_security_status_endpoint_returns_ok(tmp_path: Path):
    client = _client(tmp_path, role="viewer")
    resp = client.get("/api/security/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "ok" in body
    assert "security_headers_enabled" in body
    assert "cors_enabled" in body
    assert "auth_required" in body


def test_security_status_endpoint_does_not_expose_token_hashes(tmp_path: Path):
    token = "my-secret-api-key-1234567890"
    token_hash = hash_token(token)
    cfg_data = {
        "backend_security": {
            "auth": {"token_hashes": [token_hash]},
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, headers=auth_headers("viewer"), raise_server_exceptions=False)
    resp = client.get("/api/security/status")
    assert resp.status_code == 200
    body_str = resp.text
    # Raw token and its hash must not appear in the response body
    assert token not in body_str
    assert token_hash not in body_str


def test_security_status_endpoint_requires_auth(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/security/status")
    assert resp.status_code == 401


def test_security_status_shows_expired_token_count(tmp_path: Path):
    cfg_data = {
        "backend_security": {
            "token_records": [
                {"token_hash": hash_token("t1"), "expires_at": "2000-01-01T00:00:00Z"},
                {"token_hash": hash_token("t2"), "expires_at": "2099-12-31T23:59:59Z"},
            ]
        }
    }
    cfg_file = tmp_path / "sec.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    app = create_app(runtime_data_dir=str(tmp_path), backend_security_config_path=str(cfg_file))
    client = TestClient(app, headers=auth_headers("viewer"), raise_server_exceptions=False)
    resp = client.get("/api/security/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["expired_token_count"] == 1
    assert body["token_record_count"] == 2


# ---------------------------------------------------------------------------
# get_security_status — unit tests
# ---------------------------------------------------------------------------

def test_get_security_status_ok_with_defaults():
    config = _default_config()
    status = get_security_status(config)
    assert "ok" in status
    assert "warnings" in status
    assert "errors" in status
    assert isinstance(status["warnings"], list)
    assert isinstance(status["errors"], list)


def test_get_security_status_warns_when_headers_disabled():
    config = _default_config()
    config.security_headers.enabled = False
    status = get_security_status(config)
    assert any("headers" in w.lower() for w in status["warnings"])


def test_get_security_status_warns_when_cors_disabled():
    config = _default_config()
    config.cors.enabled = False
    status = get_security_status(config)
    assert any("cors" in w.lower() for w in status["warnings"])


def test_get_security_status_warns_when_auth_not_required():
    config = _default_config()
    config.auth.token_required = False
    status = get_security_status(config)
    assert any("token" in w.lower() or "auth" in w.lower() for w in status["warnings"])


def test_get_security_status_errors_on_wildcard_outside_dev(monkeypatch):
    monkeypatch.setenv("TASKFRAME_ENV", "demo")
    config = _default_config()
    config.cors.allowed_origins = ["*"]
    status = get_security_status(config)
    assert any("wildcard" in e.lower() or "*" in e for e in status["errors"])
    assert status["ok"] is False


def test_get_security_status_no_error_on_wildcard_in_dev(monkeypatch):
    monkeypatch.setenv("TASKFRAME_ENV", "dev")
    config = _default_config()
    config.cors.allowed_origins = ["*"]
    status = get_security_status(config)
    # No wildcard error in dev
    assert not any("wildcard" in e.lower() or "*" in e for e in status["errors"])


def test_get_security_status_warns_on_expired_tokens():
    config = _default_config()
    config.token_records = [
        {"token_hash": hash_token("t1"), "expires_at": "2000-01-01T00:00:00Z"},
    ]
    status = get_security_status(config)
    assert any("expired" in w.lower() for w in status["warnings"])


# ---------------------------------------------------------------------------
# Invalid config fails closed
# ---------------------------------------------------------------------------

def test_invalid_config_fails_closed_and_app_still_starts(tmp_path: Path):
    bad_cfg = tmp_path / "bad_security.json"
    bad_cfg.write_text("{invalid json", encoding="utf-8")
    # Should not raise; config fails closed (no cross-origin)
    config = load_security_config(bad_cfg)
    assert config.cors.allowed_origins == []


# ---------------------------------------------------------------------------
# CLI backend-security command
# ---------------------------------------------------------------------------

def test_cli_backend_security_returns_status():
    from src.taskframe_cli import main

    buf = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(["backend-security"])
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    assert "Backend Security Status" in output
    assert isinstance(rc, int)


def test_cli_backend_security_json_flag():
    from src.taskframe_cli import main

    buf = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(["backend-security", "--json"])
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    parsed = json.loads(output)
    assert "ok" in parsed
    assert isinstance(rc, int)
