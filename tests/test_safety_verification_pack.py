"""Tests for src/safety_verification_pack.py — JSON shape, claim checks, and PASS status."""
from __future__ import annotations

import pytest

from src.safety_verification_pack import (
    build_safety_verification_pack,
    build_live_blocked_evidence,
    build_dry_run_evidence,
    render_safety_verification_markdown,
    render_live_blocked_markdown,
)

_EXPECTED_CLAIM_IDS = [
    "default_demo_no_live_side_effects",
    "side_effects_stage_pending_actions",
    "approval_required_before_execution",
    "dry_run_execution_auditable",
    "live_execution_blocked_by_default",
    "manifest_policy_blocks_live_execution",
    "tool_policy_blocks_live_side_effects",
    "cli_live_guardrails_enforced",
    "optional_rpa_excluded_from_default_path",
]


@pytest.fixture(scope="module")
def pack():
    return build_safety_verification_pack(
        runtime_data_dir="runtime_data",
        manifest_dir="manifests",
        run_demo=False,
    )


def test_pack_has_required_top_level_keys(pack):
    required = {"report_type", "version", "generated_at", "ok", "status", "summary", "claims"}
    assert required.issubset(pack.keys()), f"Missing keys: {required - pack.keys()}"


def test_pack_contains_all_nine_claims(pack):
    ids = [c["id"] for c in pack["claims"]]
    for expected in _EXPECTED_CLAIM_IDS:
        assert expected in ids, f"Missing claim: {expected}"


def test_all_claims_pass_in_default_state(pack):
    failed = [c for c in pack["claims"] if c.get("status") != "PASS"]
    assert failed == [], f"Claims failed: {[c['id'] for c in failed]}"


def test_pack_ok_is_true_in_default_state(pack):
    assert pack["ok"] is True


def test_pack_status_is_pass_in_default_state(pack):
    assert pack["status"] == "PASS"


def test_summary_counts_are_consistent(pack):
    summary = pack["summary"]
    assert isinstance(summary, dict)
    assert int(summary["claims_checked"]) == 9
    assert int(summary["claims_passed"]) == 9
    assert int(summary["claims_failed"]) == 0


def test_each_claim_has_required_fields(pack):
    required = {"id", "status", "evidence"}
    for claim in pack["claims"]:
        missing = required - claim.keys()
        assert not missing, f"Claim {claim.get('id')} missing fields: {missing}"


def test_render_safety_verification_markdown_returns_string(pack):
    md = render_safety_verification_markdown(pack)
    assert isinstance(md, str)
    assert "Safety Verification" in md
    assert "PASS" in md


def test_live_blocked_evidence_has_six_checks():
    evidence = build_live_blocked_evidence(runtime_data_dir="runtime_data", manifest_dir="manifests")
    assert isinstance(evidence, dict)
    checks = evidence.get("checks", [])
    assert len(checks) == 6, f"Expected 6 checks, got {len(checks)}"


def test_render_live_blocked_markdown_contains_verdict():
    evidence = build_live_blocked_evidence(runtime_data_dir="runtime_data", manifest_dir="manifests")
    md = render_live_blocked_markdown(evidence)
    assert isinstance(md, str)
    assert "Live-Blocked" in md or "live" in md.lower()
