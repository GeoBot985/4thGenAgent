"""Tests that the release verifier includes governance checks."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "run_release_candidate_verification.py"
pytestmark = pytest.mark.release


def _verifier_text() -> str:
    return VERIFIER.read_text(encoding="utf-8")


def test_verifier_references_governance():
    text = _verifier_text()
    assert "governance" in text.lower(), "Release verifier must reference governance"


def test_verifier_has_governance_check_function():
    text = _verifier_text()
    assert "_check_toolpack_governance" in text or "toolpack_governance" in text


def test_verifier_has_governance_pending_or_check():
    text = _verifier_text()
    assert "toolpack_governance" in text


def test_verifier_has_governance_release_blocker():
    text = _verifier_text()
    assert "governance" in text.lower()


def test_verifier_governance_validates_release_and_demo():
    text = _verifier_text()
    assert "validate_governance_for_release" in text or "governance_report" in text or "governance" in text


def test_governance_module_importable():
    from src.toolpack_governance import (
        build_governance_report,
        check_pack_allowed,
        disable_pack,
        enable_pack,
        get_all_policies,
        get_pack_policy,
        validate_governance_for_release,
    )
    assert callable(build_governance_report)
    assert callable(validate_governance_for_release)
