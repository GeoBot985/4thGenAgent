from __future__ import annotations

import pytest

from src.pilot_readiness import run_pilot_live_read_preflight


@pytest.fixture(scope="module")
def preflight():
    return run_pilot_live_read_preflight()


def test_preflight_returns_dict(preflight):
    assert isinstance(preflight, dict)


def test_preflight_has_required_fields(preflight):
    assert "preflight_type" in preflight
    assert "generated_at" in preflight
    assert "status" in preflight
    assert "ok" in preflight
    assert "checks" in preflight
    assert "issues" in preflight
    assert "warnings" in preflight
    assert "claim" in preflight


def test_preflight_type_is_correct(preflight):
    assert preflight["preflight_type"] == "pilot_live_read_preflight"


def test_preflight_claim_does_not_claim_production_readiness(preflight):
    claim = preflight.get("claim", "").lower()
    assert "production" not in claim or "no" in claim


def test_preflight_status_values_are_valid(preflight):
    valid_statuses = {"ready", "blocked", "needs_auth", "missing_config"}
    assert preflight["status"] in valid_statuses


def test_preflight_checks_is_list(preflight):
    assert isinstance(preflight["checks"], list)
    assert len(preflight["checks"]) > 0


def test_preflight_includes_profile_check(preflight):
    check_ids = {c.get("check") for c in preflight["checks"]}
    assert "profile_is_pilot" in check_ids


def test_preflight_includes_live_reads_check(preflight):
    check_ids = {c.get("check") for c in preflight["checks"]}
    assert "live_reads_explicitly_enabled" in check_ids


def test_preflight_includes_side_effects_check(preflight):
    check_ids = {c.get("check") for c in preflight["checks"]}
    assert "live_side_effects_disabled" in check_ids


def test_preflight_pilot_profile_has_live_reads_enabled(preflight):
    live_reads_check = next((c for c in preflight["checks"] if c.get("check") == "live_reads_explicitly_enabled"), None)
    assert live_reads_check is not None
    assert live_reads_check["ok"] is True


def test_preflight_pilot_profile_has_side_effects_disabled(preflight):
    se_check = next((c for c in preflight["checks"] if c.get("check") == "live_side_effects_disabled"), None)
    assert se_check is not None
    assert se_check["ok"] is True


def test_preflight_needs_auth_is_not_full_failure(preflight):
    if preflight["status"] == "needs_auth":
        assert preflight["ok"] is False
        assert len(preflight["issues"]) == 0 or any("credential" in w or "auth" in w for w in preflight["warnings"] + preflight["issues"])


def test_preflight_issues_is_list(preflight):
    assert isinstance(preflight["issues"], list)


def test_preflight_warnings_is_list(preflight):
    assert isinstance(preflight["warnings"], list)
