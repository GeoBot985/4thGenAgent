"""Tests for live-blocked evidence: six checks, all PASS in default state."""
from __future__ import annotations

import pytest

from src.safety_verification_pack import (
    build_live_blocked_evidence,
    render_live_blocked_markdown,
)

_EXPECTED_CHECK_IDS = [
    "runtime_live_disabled",
    "manifest_live_disabled",
    "tool_live_blocked",
    "pending_action_not_approved",
    "wrong_confirmation_blocked",
    "optional_rpa_excluded",
]


@pytest.fixture(scope="module")
def evidence():
    return build_live_blocked_evidence(runtime_data_dir="runtime_data", manifest_dir="manifests")


def test_evidence_has_required_keys(evidence):
    required = {"report_type", "generated_at", "ok", "checks"}
    assert required.issubset(evidence.keys())


def test_evidence_contains_all_six_checks(evidence):
    ids = [c["id"] for c in evidence["checks"]]
    for expected in _EXPECTED_CHECK_IDS:
        assert expected in ids, f"Missing check: {expected}"


def test_all_checks_pass_in_default_state(evidence):
    failed = [c for c in evidence["checks"] if c.get("status") != "PASS"]
    assert failed == [], f"Checks failed: {[c['id'] for c in failed]}"


def test_evidence_ok_is_true(evidence):
    assert evidence["ok"] is True


def test_each_check_has_required_fields(evidence):
    required = {"id", "status", "expected", "actual"}
    for check in evidence["checks"]:
        missing = required - check.keys()
        assert not missing, f"Check {check.get('id')} missing fields: {missing}"


def test_markdown_contains_evidence_table(evidence):
    md = render_live_blocked_markdown(evidence)
    assert "| Check |" in md or "|Check|" in md or "Check" in md
    assert "PASS" in md


def test_markdown_states_no_live_side_effects(evidence):
    md = render_live_blocked_markdown(evidence)
    assert "live side effect" in md.lower() or "no live" in md.lower()
