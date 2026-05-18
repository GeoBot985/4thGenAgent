from __future__ import annotations

import json
from pathlib import Path

import tools.run_release_candidate_verification as verifier


def test_release_verifier_includes_runtime_governance_check() -> None:
    text = Path("tools/run_release_candidate_verification.py").read_text(encoding="utf-8")
    assert "runtime_tool_governance" in text
    assert "_check_runtime_tool_governance" in text


def test_release_verifier_has_toolpack_lifecycle_check() -> None:
    result = verifier._check_runtime_tool_governance()
    assert result["name"] == "runtime_tool_governance"
    assert result["status"] == "PASS"


def test_release_verifier_blocks_high_risk_demo_policy(monkeypatch, tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "runtime_profile.json").write_text(
        json.dumps(
            {
                "environment": "demo",
                "governance_enforced": False,
                "allow_unknown_toolpack_in_dev": False,
                "allow_high_risk_live_override": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "ROOT", root)
    result = verifier._check_runtime_tool_governance()
    assert result["status"] == "FAIL"
    assert "governance_enforcement_disabled" in result["missing"]


def test_release_verifier_confirms_optional_rpa_live_probe_excluded() -> None:
    result = verifier._check_runtime_tool_governance()
    assert result["status"] == "PASS"
    assert result["rpa_health"]["status"] == "disabled_optional"
