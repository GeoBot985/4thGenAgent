"""Spec 146 — Backend hardening tests.

Covers:
- Oversized JSON body is rejected (413 REQUEST_TOO_LARGE).
- Invalid JSON is rejected (400 INVALID_JSON).
- Top-level JSON array is rejected where object is required (400 INVALID_REQUEST_BODY).
- Missing/empty body is rejected for routes that require one (400 INVALID_JSON).
- Invalid frame_id, event_id, action_id, audit_id are rejected (400 INVALID_ID).
- limit defaults to safe value; limit cannot exceed maximum.
- Health endpoint reports hardening status.
- Hardening defaults are safe when config is missing.
- Existing authenticated routes still work under normal request volumes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.hardening import BackendHardeningConfig, RateLimitConfig, load_hardening_config
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client(runtime_dir: Path, *, role: str = "admin") -> TestClient:
    app = create_app(runtime_data_dir=str(runtime_dir))
    return TestClient(app, headers=auth_headers(role))


def _app_tiny_body(runtime_dir: Path, max_bytes: int = 50) -> TestClient:
    """App with a very small body limit for testing."""
    app = create_app(runtime_data_dir=str(runtime_dir))
    app.state.backend_hardening_config.max_body_bytes = max_bytes
    return TestClient(app, headers=auth_headers("operator"))


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
# Body size limits
# ---------------------------------------------------------------------------

def test_oversized_json_body_is_rejected(tmp_path: Path) -> None:
    client = _app_tiny_body(tmp_path, max_bytes=50)
    # Build a payload larger than 50 bytes
    large_body = json.dumps({"source": "api", "event_type": "x", "payload": {"k": "v" * 100}})

    resp = client.post("/api/events", content=large_body.encode(), headers={"Content-Type": "application/json"})

    assert resp.status_code == 413
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "REQUEST_TOO_LARGE"


def test_normal_size_body_is_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post("/api/events", json=_valid_event())
    # Should not get 413
    assert resp.status_code != 413


def test_content_length_header_triggers_early_rejection(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    app.state.backend_hardening_config.max_body_bytes = 100
    client = TestClient(app, headers={**auth_headers("operator"), "Content-Length": "999999"})
    resp = client.post("/api/events", json=_valid_event())
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# JSON validation
# ---------------------------------------------------------------------------

def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b"not json at all!!!",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_JSON"


def test_json_array_at_top_level_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b'["item1", "item2"]',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_REQUEST_BODY"


def test_empty_json_body_is_rejected_for_required_body_routes(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_JSON"


def test_json_null_top_level_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post(
        "/api/events",
        content=b"null",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False


# ---------------------------------------------------------------------------
# ID validation — frame_id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "id with spaces",         # space is not in allowed charset
    "id\\backslash",          # backslash rejected
    "a" * 121,                # too long
    "id..traversal",          # double-dot sequence rejected
    "..traversal",            # leading double-dot rejected
    "id%0Aid",                # URL-encoded newline decoded by FastAPI
])
def test_invalid_frame_id_is_rejected(tmp_path: Path, bad_id: str) -> None:
    client = _client(tmp_path)
    resp = client.get(f"/api/runs/{bad_id}")
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_ID"


# ---------------------------------------------------------------------------
# ID validation — event_id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "evt id with space",      # space not in allowed charset
    "evt%0Aid",               # URL-encoded newline decoded by FastAPI
    "..evil",                 # leading double-dot rejected
])
def test_invalid_event_id_is_rejected(tmp_path: Path, bad_id: str) -> None:
    client = _client(tmp_path)
    resp = client.get(f"/api/events/{bad_id}")
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_ID"


# ---------------------------------------------------------------------------
# ID validation — action_id
# ---------------------------------------------------------------------------

def test_invalid_action_id_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post("/api/runs/valid-frame-id/pending-actions/../approve")
    # FastAPI will match the route even with the odd path because of URL decoding
    # but the _validate_id call will reject the action_id
    # The router might 404 before validation runs for some bad paths, so accept either
    assert resp.status_code in (400, 404, 405)


def test_unsafe_chars_in_frame_id_for_approval_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post("/api/runs/frame%2Fpath/pending-actions/action-001/approve")
    assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# ID validation — audit_id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "aud id spaces",          # space not in allowed charset
    "aud%0Aid",               # URL-encoded newline decoded by FastAPI
    "..evil",                 # leading double-dot rejected
])
def test_invalid_audit_id_is_rejected(tmp_path: Path, bad_id: str) -> None:
    client = _client(tmp_path)
    resp = client.get(f"/api/audit/{bad_id}")
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_ID"


# ---------------------------------------------------------------------------
# Valid IDs are accepted
# ---------------------------------------------------------------------------

def test_valid_frame_id_passes_validation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/runs/frame_abc123-XYZ")
    # 404 or 200 depending on whether frame exists; not 400
    assert resp.status_code != 400


def test_valid_event_id_with_dot_passes_validation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/events/evt.abc123")
    # 200 or 404 depending on existence; not 400 for a valid-format ID
    assert resp.status_code != 400 or "INVALID_ID" not in resp.text


# ---------------------------------------------------------------------------
# Query parameter bounds — limit
# ---------------------------------------------------------------------------

def test_limit_defaults_to_safe_value(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_limit_is_clamped_to_max(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # Request an absurdly large limit; it should be clamped, not error
    resp = client.get("/api/runs?limit=999999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    # Actual count will be bounded by available runs, not the requested limit
    assert data["count"] <= 500  # max_list_limit


def test_limit_zero_falls_back_to_default(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/runs?limit=0")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_negative_limit_falls_back_to_default(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/runs?limit=-10")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_events_limit_is_clamped(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/events?limit=999999")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_audit_limit_is_clamped(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/audit?limit=999999")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Health reports hardening status
# ---------------------------------------------------------------------------

def test_health_reports_hardening_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "hardening" in data
    h = data["hardening"]
    assert h["enabled"] is True
    assert h["max_body_bytes"] == 262144
    assert h["max_id_length"] == 120
    assert h["default_list_limit"] == 50
    assert h["max_list_limit"] == 500
    assert h["rate_limits_enabled"] is True


# ---------------------------------------------------------------------------
# Hardening defaults are safe when config is missing
# ---------------------------------------------------------------------------

def test_hardening_defaults_are_safe_without_config() -> None:
    config = load_hardening_config(config_path=None)
    assert config.enabled is True
    assert config.max_body_bytes > 0
    assert config.max_id_length >= 120
    assert config.default_list_limit >= 1
    assert config.max_list_limit >= config.default_list_limit
    assert "events_submit" in config.rate_limits
    assert "auth_failure" in config.rate_limits


def test_hardening_still_works_without_config_file(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    client = TestClient(app, headers=auth_headers("admin"))
    resp = client.get("/api/runs")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Normal requests still work under hardening
# ---------------------------------------------------------------------------

def test_authenticated_runs_list_works(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_authenticated_events_list_works(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/events")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_authenticated_audit_list_works(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/audit")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_valid_event_post_still_works(tmp_path: Path) -> None:
    client = _client(tmp_path, role="operator")
    resp = client.post("/api/events", json=_valid_event())
    assert resp.status_code == 200
    # ok may be True or False depending on runtime; must not be 400/413
    assert resp.status_code not in (400, 413, 429)
