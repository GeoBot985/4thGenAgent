from __future__ import annotations

from pathlib import Path

import pytest

import tools.run_release_candidate_verification as verifier

pytestmark = pytest.mark.release


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_service_release_verifier_includes_service_runtime_checks() -> None:
    result = verifier._check_service_runtime_profile()

    assert result["status"] == "PASS"
    assert result["missing"] == []
    assert result["failures"] == []
    assert result["profile"]["profile"] == "service"
    assert "preflight" in (verifier.SERVICE_RUNTIME_PROFILE_MD.read_text(encoding="utf-8").lower())


def test_service_release_verifier_fails_when_example_config_is_missing(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs_dir = repo / "docs"
    _write_doc(
        docs_dir / "service_runtime_profile.md",
        "service runtime profile worker identity preflight status run-once not full production readiness",
    )
    _write_doc(
        docs_dir / "production_readiness_roadmap.md",
        "service worker identity hardening not a production deployment guarantee",
    )

    monkeypatch.setattr(verifier, "ROOT", repo)

    result = verifier._check_service_runtime_profile()

    assert result["status"] == "FAIL"
    assert any("taskframe.service.example.json" in missing for missing in result["missing"])
