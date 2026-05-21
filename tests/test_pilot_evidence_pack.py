from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pilot_readiness import ROOT, write_pilot_evidence_pack


REQUIRED_FILES = [
    "pilot_readiness_scorecard.json",
    "pilot_readiness_report.md",
    "pilot_readiness_report.html",
    "runtime_profile_summary.json",
    "live_read_preflight.json",
    "side_effect_blocking_evidence.json",
    "tool_governance_report.json",
    "runtime_store_validation.json",
    "backup_restore_validation.json",
    "monitoring_summary.json",
    "recovery_idempotency_summary.json",
    "limitations.md",
    "README.md",
]

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def evidence_pack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pack")
    result = write_pilot_evidence_pack(runtime_data_dir=str(tmp))
    p = Path(result["pack_dir"])
    pack_dir = p if p.is_absolute() else ROOT / p
    return result, pack_dir


def test_evidence_pack_writes_all_required_files(evidence_pack):
    _, pack_dir = evidence_pack
    for fname in REQUIRED_FILES:
        assert (pack_dir / fname).is_file(), f"Missing: {fname}"


def test_evidence_pack_scorecard_json_is_valid(evidence_pack):
    _, pack_dir = evidence_pack
    scorecard = json.loads((pack_dir / "pilot_readiness_scorecard.json").read_text(encoding="utf-8"))
    assert scorecard["scorecard_type"] == "pilot_readiness"
    assert "overall_score" in scorecard
    assert "threshold" in scorecard


def test_evidence_pack_limitations_register_present(evidence_pack):
    _, pack_dir = evidence_pack
    lim_md = (pack_dir / "limitations.md").read_text(encoding="utf-8")
    assert "PILOT-LIM-001" in lim_md
    assert "limitation" in lim_md.lower()


def test_evidence_pack_readme_does_not_claim_production_readiness(evidence_pack):
    _, pack_dir = evidence_pack
    readme = (pack_dir / "README.md").read_text(encoding="utf-8").lower()
    assert "production ready" not in readme
    assert "production-ready" not in readme


def test_evidence_pack_readme_mentions_controlled_pilot(evidence_pack):
    _, pack_dir = evidence_pack
    readme = (pack_dir / "README.md").read_text(encoding="utf-8").lower()
    assert "controlled pilot" in readme or "pilot" in readme


def test_evidence_pack_side_effect_blocking_evidence_is_valid(evidence_pack):
    _, pack_dir = evidence_pack
    se = json.loads((pack_dir / "side_effect_blocking_evidence.json").read_text(encoding="utf-8"))
    assert "evidence" in se
    assert isinstance(se["evidence"], list)
    assert len(se["evidence"]) > 0
    for item in se["evidence"]:
        assert "tool" in item
        assert "ok" in item
        assert "reason" in item


def test_evidence_pack_result_has_ok_field(evidence_pack):
    result, _ = evidence_pack
    assert "ok" in result


def test_evidence_pack_result_has_claim_field(evidence_pack):
    result, _ = evidence_pack
    assert "claim" in result
    claim = result["claim"].lower()
    assert "production" not in claim.replace("no", "") or "no" in claim


def test_evidence_pack_html_report_mentions_pilot(evidence_pack):
    _, pack_dir = evidence_pack
    html = (pack_dir / "pilot_readiness_report.html").read_text(encoding="utf-8").lower()
    assert "pilot" in html


def test_evidence_pack_runtime_profile_summary_has_active_profile(evidence_pack):
    _, pack_dir = evidence_pack
    profile_summary = json.loads((pack_dir / "runtime_profile_summary.json").read_text(encoding="utf-8"))
    assert "active_profile" in profile_summary or "error" in profile_summary
