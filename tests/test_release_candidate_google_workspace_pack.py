from __future__ import annotations

from pathlib import Path

import pytest

import tools.run_release_candidate_verification as verifier

pytestmark = pytest.mark.release


def test_release_verifier_references_google_workspace_readonly_pack() -> None:
    text = Path("tools/run_release_candidate_verification.py").read_text(encoding="utf-8")
    assert "google_workspace_readonly_pack" in text
    assert "_check_google_workspace_readonly_pack" in text


def test_release_verifier_has_google_workspace_readonly_pack_check() -> None:
    result = verifier._check_google_workspace_readonly_pack()
    assert result["name"] == "google_workspace_readonly_pack"
    assert result["status"] == "PASS"


def test_release_verifier_google_workspace_pack_does_not_require_live_side_effects() -> None:
    result = verifier._check_google_workspace_readonly_pack()
    assert result["status"] == "PASS"
    assert result["descriptor_ok"] is True
    assert result["validation"]["ok"] is True
    assert result["health"]["status"] in {"ready", "needs_auth", "missing_dependency", "live_verified", "failing"}
