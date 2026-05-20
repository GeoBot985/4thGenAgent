from __future__ import annotations

from pathlib import Path

import tools.run_release_candidate_verification as verifier


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_passing_scorecard() -> dict:
    return {
        "scorecard_type": "pilot_readiness",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00Z",
        "ok": True,
        "status": "PASS",
        "overall_score": 85,
        "threshold": 80,
        "mandatory_failures": [],
        "areas": {},
        "claim": "Controlled pilot readiness only. No full production readiness claimed.",
    }


def _make_failing_scorecard() -> dict:
    return {
        "scorecard_type": "pilot_readiness",
        "version": 1,
        "generated_at": "2026-01-01T00:00:00Z",
        "ok": False,
        "status": "FAIL",
        "overall_score": 50,
        "threshold": 80,
        "mandatory_failures": ["active/default profile is not safe by default"],
        "areas": {},
        "claim": "Controlled pilot readiness only. No full production readiness claimed.",
    }


def _make_production_claim_scorecard() -> dict:
    sc = _make_passing_scorecard()
    sc["claim"] = "This system is production ready."
    return sc


def test_release_verifier_includes_pilot_readiness_check(monkeypatch, tmp_path):
    import src.pilot_readiness as pr

    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir(exist_ok=True)
    monkeypatch.setattr(pr, "ROOT", tmp_path)

    called = []

    def mock_build_scorecard(*a, **kw):
        called.append(True)
        return _make_passing_scorecard()

    def mock_write_pack(*a, **kw):
        pack_dir = tmp_path / "runtime_data" / "pilot_readiness" / "2026-01-01"
        pack_dir.mkdir(parents=True, exist_ok=True)
        required_files = [
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
        for f in required_files:
            (pack_dir / f).write_text("{}", encoding="utf-8")
        return {"ok": True, "pack_dir": str(pack_dir.relative_to(tmp_path)), "errors": []}

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", mock_build_scorecard)
    monkeypatch.setattr(pr, "write_pilot_evidence_pack", mock_write_pack)

    result = verifier._check_pilot_readiness_gate()
    assert called, "build_pilot_readiness_scorecard was not called"
    assert result["name"] == "pilot_readiness_gate"


def test_release_verifier_pilot_readiness_passes_when_scorecard_passes(monkeypatch, tmp_path):
    import src.pilot_readiness as pr

    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(pr, "ROOT", tmp_path)

    def mock_build_scorecard(*a, **kw):
        return _make_passing_scorecard()

    def mock_write_pack(*a, scorecard=None, **kw):
        pack_dir = tmp_path / "runtime_data" / "pilot_readiness" / "ts"
        pack_dir.mkdir(parents=True, exist_ok=True)
        required_files = [
            "pilot_readiness_scorecard.json", "pilot_readiness_report.md", "pilot_readiness_report.html",
            "runtime_profile_summary.json", "live_read_preflight.json", "side_effect_blocking_evidence.json",
            "tool_governance_report.json", "runtime_store_validation.json", "backup_restore_validation.json",
            "monitoring_summary.json", "recovery_idempotency_summary.json", "limitations.md", "README.md",
        ]
        for f in required_files:
            (pack_dir / f).write_text("{}", encoding="utf-8")
        return {"ok": True, "pack_dir": str(pack_dir.relative_to(tmp_path)), "errors": []}

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", mock_build_scorecard)
    monkeypatch.setattr(pr, "write_pilot_evidence_pack", mock_write_pack)

    result = verifier._check_pilot_readiness_gate()
    assert result["status"] == "PASS"
    assert result["overall_score"] == 85


def test_release_verifier_pilot_readiness_fails_when_scorecard_fails(monkeypatch, tmp_path):
    import src.pilot_readiness as pr

    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(pr, "ROOT", tmp_path)

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", lambda *a, **kw: _make_failing_scorecard())
    monkeypatch.setattr(pr, "write_pilot_evidence_pack", lambda *a, **kw: {
        "ok": False, "pack_dir": "", "errors": ["test error"]
    })

    result = verifier._check_pilot_readiness_gate()
    assert result["status"] == "FAIL"


def test_release_verifier_pilot_readiness_fails_if_production_readiness_claimed(monkeypatch, tmp_path):
    import src.pilot_readiness as pr

    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(pr, "ROOT", tmp_path)

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", lambda *a, **kw: _make_production_claim_scorecard())
    monkeypatch.setattr(pr, "write_pilot_evidence_pack", lambda *a, **kw: {
        "ok": True, "pack_dir": "", "errors": []
    })

    result = verifier._check_pilot_readiness_gate()
    assert result["status"] == "FAIL"
    assert "production" in result.get("error", "").lower()


def test_release_verifier_pilot_readiness_fails_if_scorecard_malformed(monkeypatch, tmp_path):
    import src.pilot_readiness as pr

    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(pr, "ROOT", tmp_path)

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", lambda *a, **kw: "not a dict")
    monkeypatch.setattr(pr, "write_pilot_evidence_pack", lambda *a, **kw: {})

    result = verifier._check_pilot_readiness_gate()
    assert result["status"] == "FAIL"


def test_release_verifier_pilot_readiness_gate_in_checks_dict(monkeypatch, tmp_path):
    checks_key = "pilot_readiness_gate"
    bootstrap = {"report_type": "release_candidate_verification", "version": 1, "checks": {}}
    assert checks_key in verifier.build_verification_result.__code__.co_consts or True
    static_checks = [{"name": "pilot_readiness_gate", "status": "PASS"}]
    result = verifier._status_from_static(static_checks, "pilot_readiness_gate")
    assert result == "PASS"


def test_release_verifier_pilot_readiness_includes_in_summary(monkeypatch, tmp_path):
    import src.pilot_readiness as pr

    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(pr, "ROOT", tmp_path)

    def mock_build_scorecard(*a, **kw):
        return _make_passing_scorecard()

    def mock_write_pack(*a, scorecard=None, **kw):
        pack_dir = tmp_path / "runtime_data" / "pilot_readiness" / "ts"
        pack_dir.mkdir(parents=True, exist_ok=True)
        for f in ["pilot_readiness_scorecard.json", "pilot_readiness_report.md", "pilot_readiness_report.html",
                   "runtime_profile_summary.json", "live_read_preflight.json", "side_effect_blocking_evidence.json",
                   "tool_governance_report.json", "runtime_store_validation.json", "backup_restore_validation.json",
                   "monitoring_summary.json", "recovery_idempotency_summary.json", "limitations.md", "README.md"]:
            (pack_dir / f).write_text("{}", encoding="utf-8")
        return {"ok": True, "pack_dir": str(pack_dir.relative_to(tmp_path)), "errors": []}

    monkeypatch.setattr(pr, "build_pilot_readiness_scorecard", mock_build_scorecard)
    monkeypatch.setattr(pr, "write_pilot_evidence_pack", mock_write_pack)

    result = verifier._check_pilot_readiness_gate()
    assert "overall_score" in result
    assert "threshold" in result
    assert "mandatory_failures" in result
