"""Tests for docs/safety_verification.md and related documentation."""
from __future__ import annotations

from pathlib import Path

DOCS = Path("docs")


def test_safety_verification_md_exists():
    assert (DOCS / "safety_verification.md").is_file()


def test_safety_verification_md_mentions_nine_claims():
    text = (DOCS / "safety_verification.md").read_text(encoding="utf-8")
    assert "9" in text or "nine" in text.lower()


def test_safety_verification_md_mentions_taskframe_safety_pack():
    text = (DOCS / "safety_verification.md").read_text(encoding="utf-8")
    assert "taskframe safety-pack" in text


def test_safety_verification_md_mentions_live_blocked():
    text = (DOCS / "safety_verification.md").read_text(encoding="utf-8")
    assert "live" in text.lower() and "blocked" in text.lower()


def test_safety_verification_md_mentions_dry_run():
    text = (DOCS / "safety_verification.md").read_text(encoding="utf-8")
    assert "dry-run" in text or "dry_run" in text


def test_cli_reference_mentions_safety_pack():
    text = (DOCS / "cli_reference.md").read_text(encoding="utf-8")
    assert "safety-pack" in text
