"""Spec 146 — Rate limit tests.

Covers:
- Event submission is rate-limited.
- Report generation is rate-limited.
- Pending-action approval/rejection is rate-limited.
- Audit reads are rate-limited.
- Rate-limited requests return 429 with structured error.
- Rate-limit response includes Retry-After and X-RateLimit-Limit headers.
- Hardening disabled means no rate limiting.
- Different auth identities have independent rate limit buckets.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.hardening import BackendHardeningConfig, RateLimitConfig
from src.backend.rate_limit import FixedWindowRateLimiter
from src.production_backend import create_app
from tests.backend_auth_support import auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app_with_limit(runtime_dir: Path, route_group: str, limit: int = 2, *, role: str = "operator") -> TestClient:
    """Create an app + client with an overridden low rate limit for one group."""
    app = create_app(runtime_data_dir=str(runtime_dir))
    # Patch just the one group
    app.state.backend_hardening_config.rate_limits[route_group] = RateLimitConfig(
        requests=limit, window_seconds=60
    )
    return TestClient(app, headers=auth_headers(role))


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


def _seed_pending_action(runtime_root: Path) -> tuple[str, str]:
    from runtime.manifest_loader import load_manifest
    from runtime.persistence import PersistenceManager
    from runtime.run_ledger import append_ledger_record
    from runtime.taskframe import create_taskframe

    manifest = load_manifest("manifests/smoke_gmail_check.manifest.json")
    frame = create_taskframe(manifest)
    frame.state = "PENDING_APPROVAL"
    action_id = "action-001"
    frame.pending_actions.append({
        "action_id": action_id,
        "tool": "write_sheet",
        "output_alias": "report",
        "args": {"sheet_id": "abc123"},
        "status": "PENDING_APPROVAL",
        "requested_at": "2026-01-01T00:00:00Z",
    })
    PersistenceManager(runtime_root).save_snapshot(frame)
    append_ledger_record(frame, runtime_data_dir=runtime_root)
    return frame.frame_id, action_id


# ---------------------------------------------------------------------------
# events_submit rate limiting
# ---------------------------------------------------------------------------

def test_event_submission_is_rate_limited(tmp_path: Path) -> None:
    client = _app_with_limit(tmp_path, "events_submit", limit=2)
    # First two succeed (or fail for event reasons, but not 429)
    r1 = client.post("/api/events", json=_valid_event())
    r2 = client.post("/api/events", json=_valid_event())
    assert r1.status_code != 429
    assert r2.status_code != 429
    # Third is rate limited
    r3 = client.post("/api/events", json=_valid_event())
    assert r3.status_code == 429
    data = r3.json()
    assert data["ok"] is False
    assert data["error_code"] == "RATE_LIMITED"


def test_rate_limited_response_has_retry_after_header(tmp_path: Path) -> None:
    client = _app_with_limit(tmp_path, "events_submit", limit=1)
    client.post("/api/events", json=_valid_event())
    resp = client.post("/api/events", json=_valid_event())
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


def test_rate_limited_response_has_rate_limit_headers(tmp_path: Path) -> None:
    client = _app_with_limit(tmp_path, "events_submit", limit=1)
    client.post("/api/events", json=_valid_event())
    resp = client.post("/api/events", json=_valid_event())
    assert resp.status_code == 429
    assert "x-ratelimit-limit" in resp.headers
    assert "x-ratelimit-remaining" in resp.headers
    assert resp.headers["x-ratelimit-remaining"] == "0"


# ---------------------------------------------------------------------------
# report_generate rate limiting
# ---------------------------------------------------------------------------

def test_report_generation_is_rate_limited(tmp_path: Path) -> None:
    client = _app_with_limit(tmp_path, "report_generate", limit=1)
    # First attempt (404 since frame doesn't exist, but not 429)
    r1 = client.post("/api/runs/frame-abc/report", json={"rebuild": False})
    assert r1.status_code != 429
    # Second attempt hits rate limit
    r2 = client.post("/api/runs/frame-abc/report", json={"rebuild": False})
    assert r2.status_code == 429
    assert r2.json()["error_code"] == "RATE_LIMITED"


# ---------------------------------------------------------------------------
# pending_action_write rate limiting
# ---------------------------------------------------------------------------

def test_pending_action_approval_is_rate_limited(tmp_path: Path) -> None:
    frame_id, action_id = _seed_pending_action(tmp_path)
    client = _app_with_limit(tmp_path, "pending_action_write", limit=1)
    # First attempt
    r1 = client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/approve")
    assert r1.status_code != 429
    # Second attempt hits rate limit (rate limit key is reused across approve/reject)
    r2 = client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/approve")
    assert r2.status_code == 429
    assert r2.json()["error_code"] == "RATE_LIMITED"


def test_pending_action_rejection_is_rate_limited(tmp_path: Path) -> None:
    frame_id, action_id = _seed_pending_action(tmp_path)
    client = _app_with_limit(tmp_path, "pending_action_write", limit=1)
    r1 = client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/reject")
    assert r1.status_code != 429
    r2 = client.post(f"/api/runs/{frame_id}/pending-actions/{action_id}/reject")
    assert r2.status_code == 429


# ---------------------------------------------------------------------------
# audit_read rate limiting
# ---------------------------------------------------------------------------

def test_audit_reads_are_rate_limited(tmp_path: Path) -> None:
    client = _app_with_limit(tmp_path, "audit_read", limit=2, role="admin")
    r1 = client.get("/api/audit")
    r2 = client.get("/api/audit")
    assert r1.status_code != 429
    assert r2.status_code != 429
    r3 = client.get("/api/audit")
    assert r3.status_code == 429
    assert r3.json()["error_code"] == "RATE_LIMITED"


# ---------------------------------------------------------------------------
# runs_read rate limiting
# ---------------------------------------------------------------------------

def test_runs_read_is_rate_limited(tmp_path: Path) -> None:
    client = _app_with_limit(tmp_path, "runs_read", limit=1, role="viewer")
    r1 = client.get("/api/runs")
    assert r1.status_code != 429
    r2 = client.get("/api/runs")
    assert r2.status_code == 429


# ---------------------------------------------------------------------------
# Hardening disabled → no rate limiting
# ---------------------------------------------------------------------------

def test_disabled_hardening_allows_unlimited_requests(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    # Disable hardening entirely
    app.state.backend_hardening_config.enabled = False
    client = TestClient(app, headers=auth_headers("operator"))
    for _ in range(10):
        resp = client.post("/api/events", json=_valid_event())
        assert resp.status_code != 429


# ---------------------------------------------------------------------------
# Isolated rate limit buckets per identity
# ---------------------------------------------------------------------------

def test_different_auth_identities_have_separate_buckets(tmp_path: Path) -> None:
    app = create_app(runtime_data_dir=str(tmp_path))
    app.state.backend_hardening_config.rate_limits["runs_read"] = RateLimitConfig(requests=1, window_seconds=60)
    admin_client = TestClient(app, headers=auth_headers("admin"))
    viewer_client = TestClient(app, headers=auth_headers("viewer"))

    # Admin uses their bucket
    r1 = admin_client.get("/api/runs")
    assert r1.status_code != 429
    r2 = admin_client.get("/api/runs")
    assert r2.status_code == 429

    # Viewer should still have their own bucket intact
    r3 = viewer_client.get("/api/runs")
    assert r3.status_code != 429


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------

def test_rate_limiter_allows_up_to_limit() -> None:
    rl = FixedWindowRateLimiter()
    for _ in range(5):
        allowed, remaining, _ = rl.check("key", limit=5, window_seconds=60)
        assert allowed is True
    allowed, remaining, retry = rl.check("key", limit=5, window_seconds=60)
    assert allowed is False
    assert remaining == 0
    assert retry > 0


def test_rate_limiter_reset_clears_state() -> None:
    rl = FixedWindowRateLimiter()
    for _ in range(3):
        rl.check("k", limit=3, window_seconds=60)
    # Should be exhausted
    allowed, _, _ = rl.check("k", limit=3, window_seconds=60)
    assert allowed is False
    rl.reset("k")
    allowed, _, _ = rl.check("k", limit=3, window_seconds=60)
    assert allowed is True


def test_rate_limiter_different_keys_are_independent() -> None:
    rl = FixedWindowRateLimiter()
    for _ in range(2):
        rl.check("key-a", limit=2, window_seconds=60)
    # key-a is exhausted
    ok_a, _, _ = rl.check("key-a", limit=2, window_seconds=60)
    assert ok_a is False
    # key-b is fresh
    ok_b, _, _ = rl.check("key-b", limit=2, window_seconds=60)
    assert ok_b is True
