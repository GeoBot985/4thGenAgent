from __future__ import annotations

import json

import pytest

from src.pilot_readiness import (
    PILOT_PASS_THRESHOLD,
    PILOT_SCORECARD_AREAS,
    build_pilot_readiness_scorecard,
)


@pytest.fixture(scope="module")
def scorecard():
    return build_pilot_readiness_scorecard()


def test_pilot_scorecard_returns_valid_json(scorecard):
    assert isinstance(scorecard, dict)
    serialized = json.dumps(scorecard, default=str)
    parsed = json.loads(serialized)
    assert parsed["scorecard_type"] == "pilot_readiness"


def test_pilot_scorecard_has_required_fields(scorecard):
    assert "scorecard_type" in scorecard
    assert "version" in scorecard
    assert "generated_at" in scorecard
    assert "ok" in scorecard
    assert "status" in scorecard
    assert "overall_score" in scorecard
    assert "threshold" in scorecard
    assert "mandatory_failures" in scorecard
    assert "areas" in scorecard
    assert "claim" in scorecard


def test_pilot_scorecard_threshold_is_80(scorecard):
    assert scorecard["threshold"] == PILOT_PASS_THRESHOLD
    assert scorecard["threshold"] == 80


def test_pilot_scorecard_has_all_nine_areas(scorecard):
    areas = scorecard["areas"]
    expected = {a for a, _ in PILOT_SCORECARD_AREAS}
    assert expected == set(areas.keys())


def test_pilot_scorecard_area_weights_sum_to_100():
    total = sum(w for _, w in PILOT_SCORECARD_AREAS)
    assert total == 100


def test_pilot_scorecard_claim_does_not_include_production_readiness(scorecard):
    claim = scorecard.get("claim", "").lower()
    assert "production ready" not in claim
    assert "production-ready" not in claim


def test_pilot_scorecard_claim_mentions_pilot(scorecard):
    claim = scorecard.get("claim", "").lower()
    assert "pilot" in claim


def test_safe_pilot_profile_passes_profile_checks():
    from runtime.runtime_environment import load_runtime_profile
    from src.pilot_readiness import _is_pilot_profile_safe

    pilot = load_runtime_profile(profile_name="pilot")
    ok, issues = _is_pilot_profile_safe(pilot)
    assert ok, f"Pilot profile safety issues: {issues}"
    assert issues == []


def test_pilot_profile_fails_if_live_side_effects_enabled():
    from src.pilot_readiness import _is_pilot_profile_safe

    bad_profile = {
        "allow_live_side_effects": True,
        "allow_live_reads": True,
        "fixture_mode": False,
        "require_tool_governance": True,
        "name": "pilot",
    }
    ok, issues = _is_pilot_profile_safe(bad_profile)
    assert not ok
    assert any("side effect" in i for i in issues)


def test_pilot_scorecard_status_is_pass_or_fail(scorecard):
    assert scorecard["status"] in ("PASS", "FAIL")


def test_pilot_scorecard_mandatory_failures_is_list(scorecard):
    assert isinstance(scorecard["mandatory_failures"], list)


def test_runtime_store_failure_lowers_score(monkeypatch, tmp_path):
    import runtime.runtime_store as rs

    # Simulate a pre-existing index that reports failure so we exercise the failure path
    # without triggering a full store scan.
    fake_index_path = tmp_path / "indexes" / "runtime_store_index.json"
    fake_index_path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json
    fake_index_path.write_text(_json.dumps({"ok": False, "issues": [{"category": "invalid_json", "message": "boom"}]}), encoding="utf-8")

    result = build_pilot_readiness_scorecard(runtime_data_dir=str(tmp_path))
    store_area = result["areas"].get("runtime_store_integrity", {})
    assert store_area.get("pct", 100) < 100


def test_monitoring_failure_lowers_score(monkeypatch, tmp_path):
    import runtime.operational_monitoring as om

    # Simulate get_run_health_index_path raising so the monitoring check errors out.
    monkeypatch.setattr(om, "get_run_health_index_path", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    result = build_pilot_readiness_scorecard(runtime_data_dir=str(tmp_path))
    mon_area = result["areas"].get("monitoring_visibility", {})
    assert mon_area.get("pct", 100) < 100


def test_recovery_idempotency_failure_lowers_score(monkeypatch, tmp_path):
    import runtime.recovery as rec

    monkeypatch.setattr(rec, "build_recovery_assessment_stub", lambda: {"ok": False})
    result = build_pilot_readiness_scorecard(runtime_data_dir=str(tmp_path))
    rec_area = result["areas"].get("recovery_idempotency_controls", {})
    assert rec_area.get("pct", 100) < 100


def test_unknown_toolpack_fails_pilot_gate(monkeypatch):
    import runtime.runtime_environment as renv

    original = renv.load_runtime_profile

    def patched_load(profile_name=None, path=None):
        profile = original(profile_name=profile_name, path=path)
        if profile_name == "pilot":
            profile = dict(profile)
            profile["allowed_toolpacks"] = ["some_unknown_pack_xyz"]
        return profile

    monkeypatch.setattr(renv, "load_runtime_profile", patched_load)
    result = build_pilot_readiness_scorecard()
    assert not result["ok"] or any("unknown toolpack" in f for f in result["mandatory_failures"])
