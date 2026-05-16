"""Tests for build_governance_report and validate_governance_for_release."""
from __future__ import annotations

import pytest

import src.toolpack_governance as gov


@pytest.fixture(autouse=True)
def isolated_governance(tmp_path, monkeypatch):
    tmp_gov = tmp_path / "toolpack_governance.json"
    monkeypatch.setattr(gov, "GOVERNANCE_PATH", tmp_gov)
    yield tmp_gov


def _seed_core_packs():
    gov.enable_pack("core_business", classification="core", environments=["demo", "dev", "test", "release", "live"])
    gov.enable_pack("core_memory", classification="core", environments=["demo", "dev", "test", "release", "live"])


def test_report_shape():
    _seed_core_packs()
    report = gov.build_governance_report()
    assert "ok" in report
    assert "by_classification" in report
    assert "by_environment" in report
    assert "violations" in report
    assert "total_entries" in report


def test_report_core_packs_no_violations():
    _seed_core_packs()
    report = gov.build_governance_report()
    assert report["ok"] is True
    assert report["violations"] == []


def test_report_high_risk_in_demo_is_violation():
    gov.enable_pack("risky_pack", classification="high_risk", environments=["demo", "dev"])
    report = gov.build_governance_report()
    assert report["ok"] is False
    assert any("risky_pack" in v for v in report["violations"])


def test_report_experimental_in_release_is_violation():
    gov.enable_pack("exp_pack", classification="experimental", environments=["dev", "release"])
    report = gov.build_governance_report()
    assert report["ok"] is False
    assert any("exp_pack" in v for v in report["violations"])


def test_report_blocked_with_envs_is_violation():
    # Manually write a bad entry
    import json
    bad = {
        "schema_version": 1,
        "entries": [
            {
                "toolpack_id": "bad_blocked",
                "classification": "blocked",
                "enabled_environments": ["dev"],
                "enabled_by": "system",
                "enabled_at": "2026-01-01T00:00:00+00:00",
                "reason": "",
            }
        ],
    }
    gov.GOVERNANCE_PATH.write_text(json.dumps(bad), encoding="utf-8")
    report = gov.build_governance_report()
    assert report["ok"] is False
    assert any("bad_blocked" in v for v in report["violations"])


def test_report_by_environment_counts():
    gov.enable_pack("pack_a", classification="core", environments=["demo", "dev"])
    gov.enable_pack("pack_b", classification="optional", environments=["dev"])
    report = gov.build_governance_report()
    assert "pack_a" in report["by_environment"]["demo"]
    assert "pack_b" not in report["by_environment"]["demo"]
    assert "pack_b" in report["by_environment"]["dev"]


def test_release_validation_config_missing(monkeypatch, tmp_path):
    absent = tmp_path / "absent.json"
    monkeypatch.setattr(gov, "GOVERNANCE_PATH", absent)
    result = gov.validate_governance_for_release()
    assert result["ok"] is False
    assert any(c["id"] == "governance_config_exists" and c["status"] == "FAIL" for c in result["checks"])


def test_release_validation_passes_with_safe_packs():
    _seed_core_packs()
    result = gov.validate_governance_for_release()
    assert result["ok"] is True
    assert result["status"] == "PASS"
    assert all(c["status"] == "PASS" for c in result["checks"])


def test_release_validation_fails_with_high_risk_in_demo():
    gov.enable_pack("risky", classification="high_risk", environments=["demo"])
    result = gov.validate_governance_for_release()
    assert result["ok"] is False
    assert any(c["id"] == "demo_env_safe" and c["status"] == "FAIL" for c in result["checks"])


def test_release_validation_fails_with_experimental_in_release():
    gov.enable_pack("exp", classification="experimental", environments=["release"])
    result = gov.validate_governance_for_release()
    assert result["ok"] is False
    assert any(c["id"] == "release_env_safe" and c["status"] == "FAIL" for c in result["checks"])


def test_render_governance_markdown_contains_classifications():
    _seed_core_packs()
    report = gov.build_governance_report()
    md = gov.render_governance_markdown(report)
    assert "## By Classification" in md
    assert "## By Environment" in md
    assert "core" in md


def test_render_governance_markdown_shows_violations():
    gov.enable_pack("risky_pack", classification="high_risk", environments=["demo"])
    report = gov.build_governance_report()
    md = gov.render_governance_markdown(report)
    assert "Policy Violations" in md
    assert "risky_pack" in md
