"""Tests for release verifier safety pack checks — structure only, no full run."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "run_release_candidate_verification.py"
pytestmark = pytest.mark.release


def _verifier_text() -> str:
    return VERIFIER.read_text(encoding="utf-8")


def test_verifier_declares_safety_verification_pack_check():
    text = _verifier_text()
    assert '"safety_verification_pack": "PENDING"' in text, \
        "Expected safety_verification_pack in bootstrap checks dict"


def test_verifier_declares_live_blocked_evidence_check():
    text = _verifier_text()
    assert '"live_blocked_evidence_report": "PENDING"' in text


def test_verifier_declares_default_no_live_side_effects_check():
    text = _verifier_text()
    assert '"default_no_live_side_effects": "PENDING"' in text


def test_verifier_has_check_safety_verification_pack_function():
    text = _verifier_text()
    assert "_check_safety_verification_pack" in text


def test_verifier_adds_safety_pack_check_to_static_checks():
    text = _verifier_text()
    assert "_check_safety_verification_pack()" in text


def test_verifier_adds_safety_pack_release_blocker():
    text = _verifier_text()
    assert "safety verification pack failed" in text
