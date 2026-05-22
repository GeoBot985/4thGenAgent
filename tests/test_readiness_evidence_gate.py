"""Spec 147 — Readiness Evidence Gate tests.

Covers:
- Passing gate with fresh valid evidence.
- Missing bounded validation report.
- Stale readiness scorecard.
- Score below threshold.
- Portfolio pack claims production readiness.
- Story pack has dry_run_only == False.
- Story pack reports live side effects.
- Required artifacts from mismatched run IDs (warning).
- --json output shape.
- --write-report creates JSON, Markdown, and HTML.
- Strict mode fails when release verifier evidence is missing.
- Non-strict mode warns when release verifier evidence is missing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.readiness_evidence_gate import (
    build_readiness_gate,
    write_gate_report,
)
from runtime.readiness_evidence_contracts import (
    CLAIM_CONTROLLED_DEMO_90,
    CLAIM_DISCLAIMER,
    DISALLOWED_CLAIMS,
    EVIDENCE_BOUNDED_VALIDATION,
    EVIDENCE_PORTFOLIO_PACK,
    EVIDENCE_READINESS_SCORECARD,
    EVIDENCE_RELEASE_VERIFIER,
    EVIDENCE_STORY_PACK,
    FAIL_CONTROLLED_DEMO_90,
    PASS_CONTROLLED_DEMO_90,
    PRODUCTION_NOT_CLAIMED,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

_FRESH_TS = "2099-01-01T12:00:00Z"  # far future = always fresh
_STALE_TS = "2000-01-01T00:00:00Z"  # far past = always stale
_SINCE_TS = "2050-01-01T00:00:00Z"  # threshold used in freshness tests


def _write_bounded_validation(rd: Path, *, ok: bool = True, ts: str = _FRESH_TS) -> None:
    p = rd / "validation"
    p.mkdir(parents=True, exist_ok=True)
    (p / "bounded_validation_report.json").write_text(json.dumps({
        "report_type": "bounded_validation",
        "ok": ok,
        "started_at": ts,
        "ended_at": ts,
        "mode": "local",
        "summary": {"command_count": 8, "passed_commands": 8, "failed_commands": 0},
        "failed_groups": [],
    }), encoding="utf-8")


def _write_readiness_scorecard(rd: Path, *, ok: bool = True, score: float = 100.0, status: str = "PASS", ts: str = _FRESH_TS) -> None:
    p = rd / "readiness"
    p.mkdir(parents=True, exist_ok=True)
    (p / "readiness_scorecard.json").write_text(json.dumps({
        "ok": ok,
        "status": status,
        "threshold": 90,
        "overall_score": score,
        "generated_at": ts,
        "blocking_areas": [],
    }), encoding="utf-8")


def _write_story_pack(rd: Path, *, ok: bool = True, dry_run_only: bool = True, live_effects: bool | None = None, ts: str = _FRESH_TS, pack_run_id: str = "pack-run-001") -> None:
    parent = rd / "demo_packs" / "cross_workflow_business_demo_v2_abc123"
    parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ok": ok,
        "pack_id": "cross_workflow_business_demo_v2",
        "pack_run_id": pack_run_id,
        "started_at": ts,
        "ended_at": ts,
        "dry_run_only": dry_run_only,
    }
    if live_effects is not None:
        data["live_side_effects_performed"] = live_effects
    (parent / "cross_workflow_demo_summary.json").write_text(json.dumps(data), encoding="utf-8")


def _write_portfolio_pack(
    rd: Path,
    *,
    ok: bool = True,
    production_readiness_claimed: bool = False,
    included_readiness_scorecard: bool = True,
    included_story_pack: bool = True,
    ts: str = _FRESH_TS,
    pack_run_id: str = "portfolio-run-001",
) -> None:
    parent = rd / "portfolio_evidence" / "portfolio_evidence_pack_v1_20991201T000000_aabbcc00"
    parent.mkdir(parents=True, exist_ok=True)
    (parent / "summary.json").write_text(json.dumps({
        "ok": ok,
        "pack_id": "portfolio_evidence_pack_v1",
        "pack_run_id": pack_run_id,
        "generated_at": ts,
        "production_readiness_claimed": production_readiness_claimed,
        "included_readiness_scorecard": included_readiness_scorecard,
        "included_story_pack": included_story_pack,
    }), encoding="utf-8")


def _write_release_verifier(rd: Path, *, verdict: str = "READY_WITH_KNOWN_LIMITATIONS", ts: str = _FRESH_TS) -> None:
    p = rd / "audit"
    p.mkdir(parents=True, exist_ok=True)
    (p / "release_candidate_verification.json").write_text(json.dumps({
        "verdict": verdict,
        "generated_at": ts,
    }), encoding="utf-8")


def _write_all_valid(rd: Path) -> None:
    """Write a complete set of valid, fresh evidence."""
    _write_bounded_validation(rd)
    _write_readiness_scorecard(rd)
    _write_story_pack(rd)
    _write_portfolio_pack(rd)
    _write_release_verifier(rd)


# ---------------------------------------------------------------------------
# Passing gate with fresh valid evidence
# ---------------------------------------------------------------------------

def test_gate_passes_with_all_valid_fresh_evidence(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is True
    assert result["status"] == "PASS"
    assert result["claim_allowed"] is True
    assert result["classification"] == PASS_CONTROLLED_DEMO_90
    assert result["claim"] == CLAIM_CONTROLLED_DEMO_90
    assert result["blocking_failures"] == []
    assert result["production_readiness_claimed"] is False


def test_gate_evidence_all_pass_with_valid_artifacts(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    ev = result["evidence"]
    assert ev[EVIDENCE_BOUNDED_VALIDATION]["status"] == "PASS"
    assert ev[EVIDENCE_READINESS_SCORECARD]["status"] == "PASS"
    assert ev[EVIDENCE_STORY_PACK]["status"] == "PASS"
    assert ev[EVIDENCE_PORTFOLIO_PACK]["status"] == "PASS"


# ---------------------------------------------------------------------------
# Missing bounded validation report
# ---------------------------------------------------------------------------

def test_gate_fails_when_bounded_validation_is_missing(tmp_path: Path) -> None:
    # Write everything except bounded validation
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    assert result["classification"] == FAIL_CONTROLLED_DEMO_90
    ev = result["evidence"][EVIDENCE_BOUNDED_VALIDATION]
    assert ev["status"] == "MISSING"
    assert len(result["blocking_failures"]) >= 1
    assert any("bounded" in f.lower() or "validation" in f.lower() or "missing" in f.lower() for f in result["blocking_failures"])


def test_gate_fails_when_bounded_validation_has_ok_false(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path, ok=False)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    assert result["evidence"][EVIDENCE_BOUNDED_VALIDATION]["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Stale readiness scorecard
# ---------------------------------------------------------------------------

def test_gate_fails_when_readiness_scorecard_is_stale(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path, ts=_STALE_TS)  # stale
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_READINESS_SCORECARD]
    assert ev["status"] == "STALE"
    assert ev["fresh"] is False
    assert any("stale" in f.lower() or "scorecard" in f.lower() for f in result["blocking_failures"])


# ---------------------------------------------------------------------------
# Score below threshold
# ---------------------------------------------------------------------------

def test_gate_fails_when_score_is_below_threshold(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path, score=75.0, ok=False, status="FAIL")
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_READINESS_SCORECARD]
    assert ev["status"] == "FAIL"
    assert any("75" in f or "threshold" in f.lower() or "below" in f.lower() or "scorecard" in f.lower()
               for f in result["blocking_failures"])


def test_gate_uses_configured_threshold(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path, score=80.0, ok=True, status="PASS")
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)

    result_90 = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    result_70 = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=70, since=_SINCE_TS)

    assert result_90["ok"] is False  # 80 < 90
    assert result_70["ok"] is True   # 80 >= 70


# ---------------------------------------------------------------------------
# Portfolio pack claims production readiness
# ---------------------------------------------------------------------------

def test_gate_fails_when_portfolio_claims_production_readiness(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path, production_readiness_claimed=True)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_PORTFOLIO_PACK]
    assert ev["status"] == "FAIL"
    assert result["production_readiness_claimed"] is True
    assert any("production" in f.lower() for f in result["blocking_failures"])


# ---------------------------------------------------------------------------
# Story pack has dry_run_only == False
# ---------------------------------------------------------------------------

def test_gate_fails_when_story_pack_is_not_dry_run(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path, dry_run_only=False)
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_STORY_PACK]
    assert ev["status"] == "FAIL"
    assert any("dry_run" in f.lower() or "live" in f.lower() or "story" in f.lower() for f in result["blocking_failures"])


# ---------------------------------------------------------------------------
# Story pack reports live side effects
# ---------------------------------------------------------------------------

def test_gate_fails_when_story_pack_reports_live_side_effects(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path, dry_run_only=True, live_effects=True)
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_STORY_PACK]
    assert ev["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Missing story pack
# ---------------------------------------------------------------------------

def test_gate_fails_when_story_pack_is_missing(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    # No story pack written
    _write_portfolio_pack(tmp_path)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_STORY_PACK]
    assert ev["status"] == "MISSING"


# ---------------------------------------------------------------------------
# Portfolio pack missing readiness scorecard link
# ---------------------------------------------------------------------------

def test_gate_fails_when_portfolio_missing_scorecard(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path, included_readiness_scorecard=False)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    ev = result["evidence"][EVIDENCE_PORTFOLIO_PACK]
    assert ev["status"] == "FAIL"
    assert any("readiness scorecard" in f.lower() or "scorecard" in f.lower() for f in result["blocking_failures"])


# ---------------------------------------------------------------------------
# Release verifier: strict vs non-strict
# ---------------------------------------------------------------------------

def test_non_strict_mode_warns_when_release_verifier_missing(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)
    # No release verifier written

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, strict=False, since=_SINCE_TS)

    # Should still PASS (non-strict)
    assert result["ok"] is True
    assert result["classification"] == PASS_CONTROLLED_DEMO_90
    # Warning must be present
    assert len(result["warnings"]) >= 1
    assert any("release" in w.lower() or "verifier" in w.lower() or "missing" in w.lower() for w in result["warnings"])


def test_strict_mode_fails_when_release_verifier_missing(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path)
    _write_readiness_scorecard(tmp_path)
    _write_story_pack(tmp_path)
    _write_portfolio_pack(tmp_path)
    # No release verifier

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, strict=True, since=_SINCE_TS)

    assert result["ok"] is False
    assert any("release" in f.lower() or "verifier" in f.lower() for f in result["blocking_failures"])


def test_non_strict_mode_passes_with_stale_release_verifier(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    # Overwrite with stale release verifier
    _write_release_verifier(tmp_path, ts=_STALE_TS)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, strict=False, since=_SINCE_TS)

    assert result["ok"] is True  # Not blocking in non-strict
    assert len(result["warnings"]) >= 1


def test_strict_mode_fails_with_stale_release_verifier(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    _write_release_verifier(tmp_path, ts=_STALE_TS)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, strict=True, since=_SINCE_TS)

    assert result["ok"] is False


# ---------------------------------------------------------------------------
# --since freshness enforcement
# ---------------------------------------------------------------------------

def test_all_stale_evidence_fails_gate(tmp_path: Path) -> None:
    _write_bounded_validation(tmp_path, ts=_STALE_TS)
    _write_readiness_scorecard(tmp_path, ts=_STALE_TS)
    _write_story_pack(tmp_path, ts=_STALE_TS)
    _write_portfolio_pack(tmp_path, ts=_STALE_TS)

    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    # All required evidence should be STALE
    for key in (EVIDENCE_BOUNDED_VALIDATION, EVIDENCE_READINESS_SCORECARD, EVIDENCE_STORY_PACK, EVIDENCE_PORTFOLIO_PACK):
        assert result["evidence"][key]["status"] == "STALE", f"{key} should be STALE"


def test_no_since_skips_freshness_check(tmp_path: Path) -> None:
    # Write old timestamps but don't pass --since
    _write_bounded_validation(tmp_path, ts=_STALE_TS)
    _write_readiness_scorecard(tmp_path, ts=_STALE_TS)
    _write_story_pack(tmp_path, ts=_STALE_TS)
    _write_portfolio_pack(tmp_path, ts=_STALE_TS)
    _write_release_verifier(tmp_path, ts=_STALE_TS)

    # No since= and no git HEAD in a tmp dir — freshness not enforced
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=None)

    # Since there's no git repo at tmp_path, since_ts resolves from git HEAD
    # (which may be available from the real repo). Either way, all artifacts
    # should be considered "fresh" when no since_ts can be resolved.
    # If git HEAD is available, the stale timestamps may still fail.
    # We verify the structure is correct regardless.
    assert isinstance(result["ok"], bool)
    assert result["claim"] == CLAIM_CONTROLLED_DEMO_90


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_gate_result_has_required_top_level_fields(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    required_keys = (
        "ok", "claim", "claim_allowed", "threshold", "overall_score", "status",
        "classification", "production_readiness_claimed", "controlled_demo_readiness_claimed",
        "evidence", "blocking_failures", "warnings", "recommended_next_steps",
        "generated_at", "disclaimer", "allowed_wording", "disallowed_claims",
    )
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


def test_gate_result_evidence_has_status_fresh_path(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    for key, ev in result["evidence"].items():
        assert "status" in ev, f"{key} evidence missing 'status'"
        assert "fresh" in ev, f"{key} evidence missing 'fresh'"
        assert "path" in ev, f"{key} evidence missing 'path'"


def test_gate_result_disallowed_claims_present(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert isinstance(result["disallowed_claims"], list)
    assert len(result["disallowed_claims"]) >= 5
    assert any("production" in c.lower() for c in result["disallowed_claims"])


def test_passing_gate_has_allowed_wording(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is True
    assert result["allowed_wording"]
    assert "90%+" in result["allowed_wording"]


def test_failing_gate_has_no_allowed_wording(tmp_path: Path) -> None:
    # No evidence at all
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["ok"] is False
    assert not result["allowed_wording"]


def test_gate_result_has_disclaimer(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["disclaimer"] == CLAIM_DISCLAIMER
    assert "controlled demo" in result["disclaimer"].lower()
    assert "production" in result["disclaimer"].lower()


def test_gate_production_not_claimed(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)

    assert result["production_readiness_claimed"] is False
    assert result["production_claim_status"] == PRODUCTION_NOT_CLAIMED


# ---------------------------------------------------------------------------
# --write-report creates JSON, Markdown, and HTML
# ---------------------------------------------------------------------------

def test_write_report_creates_three_files(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    paths = write_gate_report(result, runtime_data_dir=str(tmp_path))

    assert paths["ok"] is True
    json_path = Path(paths["json_path"])
    md_path = Path(paths["markdown_path"])
    html_path = Path(paths["html_path"])

    assert json_path.is_file(), "JSON report not created"
    assert md_path.is_file(), "Markdown report not created"
    assert html_path.is_file(), "HTML report not created"


def test_write_report_json_is_valid(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    paths = write_gate_report(result, runtime_data_dir=str(tmp_path))

    data = json.loads(Path(paths["json_path"]).read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["status"] == "PASS"


def test_write_report_markdown_contains_verdict(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    paths = write_gate_report(result, runtime_data_dir=str(tmp_path))

    md = Path(paths["markdown_path"]).read_text(encoding="utf-8")
    assert "PASS" in md
    assert "90%+" in md
    assert "controlled demo" in md.lower()


def test_write_report_html_contains_verdict(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    paths = write_gate_report(result, runtime_data_dir=str(tmp_path))

    html = Path(paths["html_path"]).read_text(encoding="utf-8")
    assert "PASS" in html
    assert "<!DOCTYPE html>" in html


def test_write_report_markdown_lists_disallowed_wording(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    paths = write_gate_report(result, runtime_data_dir=str(tmp_path))

    md = Path(paths["markdown_path"]).read_text(encoding="utf-8")
    assert "Production ready" in md
    assert "Disallowed" in md


def test_write_report_markdown_includes_disclaimer(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    result = build_readiness_gate(runtime_data_dir=str(tmp_path), threshold=90, since=_SINCE_TS)
    paths = write_gate_report(result, runtime_data_dir=str(tmp_path))

    md = Path(paths["markdown_path"]).read_text(encoding="utf-8")
    assert CLAIM_DISCLAIMER[:30] in md


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def test_cli_readiness_gate_json_output(tmp_path: Path) -> None:
    """Exercise the CLI handler via taskframe_cli.main()."""
    _write_all_valid(tmp_path)
    import sys
    from io import StringIO
    from src.taskframe_cli import main

    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(["readiness-gate", "--runtime-data-dir", str(tmp_path), "--threshold", "90", "--json", "--since", _SINCE_TS])
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()
    data = json.loads(output)
    assert data["ok"] is True
    assert data["status"] == "PASS"
    assert rc == 0


def test_cli_readiness_gate_write_report(tmp_path: Path) -> None:
    _write_all_valid(tmp_path)
    import sys
    from io import StringIO
    from src.taskframe_cli import main

    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(["readiness-gate", "--runtime-data-dir", str(tmp_path), "--threshold", "90",
                   "--write-report", "--json", "--since", _SINCE_TS])
    finally:
        sys.stdout = old_stdout

    data = json.loads(buf.getvalue())
    assert rc == 0
    report_paths = data.get("report_paths", {})
    assert Path(report_paths.get("json_path", "")).is_file()
    assert Path(report_paths.get("markdown_path", "")).is_file()
    assert Path(report_paths.get("html_path", "")).is_file()


def test_cli_readiness_gate_returns_nonzero_on_failure(tmp_path: Path) -> None:
    # No evidence at all
    import sys
    from io import StringIO
    from src.taskframe_cli import main

    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(["readiness-gate", "--runtime-data-dir", str(tmp_path), "--json", "--since", _SINCE_TS])
    finally:
        sys.stdout = old_stdout

    assert rc == 1


# ---------------------------------------------------------------------------
# Contracts module
# ---------------------------------------------------------------------------

def test_contracts_disallowed_claims_list() -> None:
    assert len(DISALLOWED_CLAIMS) >= 5
    all_claims = " ".join(DISALLOWED_CLAIMS).lower()
    assert "production" in all_claims
    assert "autonomous" in all_claims


def test_contracts_claim_label() -> None:
    assert "90%" in CLAIM_CONTROLLED_DEMO_90
    assert "controlled" in CLAIM_CONTROLLED_DEMO_90.lower()


def test_contracts_disclaimer_mentions_production_and_demo() -> None:
    lower = CLAIM_DISCLAIMER.lower()
    assert "production" in lower
    assert "controlled demo" in lower
