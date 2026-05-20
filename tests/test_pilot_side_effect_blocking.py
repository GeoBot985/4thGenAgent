from __future__ import annotations

import pytest

from src.pilot_readiness import SIDE_EFFECT_TOOLS, check_side_effect_blocking


@pytest.fixture(scope="module")
def blocking_evidence():
    return check_side_effect_blocking()


def test_side_effect_blocking_returns_list(blocking_evidence):
    assert isinstance(blocking_evidence, list)


def test_side_effect_blocking_covers_all_tools(blocking_evidence):
    assert len(blocking_evidence) == len(SIDE_EFFECT_TOOLS)


def test_side_effect_tools_are_blocked_in_pilot_mode(blocking_evidence):
    for item in blocking_evidence:
        assert item["ok"] is True, f"Tool {item['tool']} is not blocked: {item}"


def test_side_effect_evidence_has_required_fields(blocking_evidence):
    for item in blocking_evidence:
        assert "tool" in item
        assert "attempted_mode" in item
        assert "expected" in item
        assert "actual" in item
        assert "ok" in item
        assert "reason" in item


def test_side_effect_attempted_mode_is_pilot(blocking_evidence):
    for item in blocking_evidence:
        assert item["attempted_mode"] == "pilot"


def test_gmail_send_is_blocked(blocking_evidence):
    gmail = next((e for e in blocking_evidence if e["tool"] == "gmail/send"), None)
    assert gmail is not None
    assert gmail["ok"] is True
    assert gmail["actual"] == "blocked"


def test_sheet_write_is_blocked(blocking_evidence):
    sheet = next((e for e in blocking_evidence if e["tool"] == "google_sheets/write_range"), None)
    assert sheet is not None
    assert sheet["ok"] is True
    assert sheet["actual"] == "blocked"


def test_calendar_delete_is_blocked(blocking_evidence):
    cal = next((e for e in blocking_evidence if e["tool"] == "google_calendar/delete_event"), None)
    assert cal is not None
    assert cal["ok"] is True
    assert cal["actual"] == "blocked"


def test_rpa_live_mutation_is_blocked(blocking_evidence):
    rpa = next((e for e in blocking_evidence if e["tool"] == "rpa/live_mutation"), None)
    assert rpa is not None
    assert rpa["ok"] is True
    assert rpa["actual"] == "blocked"


def test_unknown_side_effect_tool_is_blocked(blocking_evidence):
    unknown = next((e for e in blocking_evidence if e["tool"] == "unknown_side_effect_tool"), None)
    assert unknown is not None
    assert unknown["ok"] is True
    assert unknown["actual"] == "blocked"


def test_side_effect_blocking_fails_when_profile_allows_side_effects(monkeypatch):
    import runtime.runtime_environment as renv

    original = renv.load_runtime_profile

    def patched(profile_name=None, path=None):
        profile = dict(original(profile_name=profile_name, path=path))
        if profile_name == "pilot":
            profile["allow_live_side_effects"] = True
        return profile

    monkeypatch.setattr(renv, "load_runtime_profile", patched)
    evidence = check_side_effect_blocking()
    assert any(not e["ok"] for e in evidence)


def test_side_effect_expected_is_blocked():
    evidence = check_side_effect_blocking()
    for item in evidence:
        assert item["expected"] == "blocked"
