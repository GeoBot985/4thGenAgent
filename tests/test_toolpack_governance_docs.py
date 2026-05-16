"""Tests that governance documentation exists and covers required topics."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GOV_DOC = DOCS / "toolpack_governance.md"
CLI_REF = DOCS / "cli_reference.md"


def test_governance_doc_exists():
    assert GOV_DOC.is_file(), f"Missing: {GOV_DOC}"


def test_governance_doc_mentions_classifications():
    text = GOV_DOC.read_text(encoding="utf-8")
    for cls in ("core", "optional", "experimental", "high_risk", "blocked"):
        assert cls in text, f"Missing classification '{cls}' in governance doc"


def test_governance_doc_mentions_environments():
    text = GOV_DOC.read_text(encoding="utf-8")
    for env in ("demo", "dev", "test", "release", "live"):
        assert env in text, f"Missing environment '{env}' in governance doc"


def test_governance_doc_mentions_cli_commands():
    text = GOV_DOC.read_text(encoding="utf-8")
    for cmd in ("tools policy", "tools enable", "tools disable", "tools governance-report"):
        assert cmd in text, f"Missing CLI command '{cmd}' in governance doc"


def test_governance_doc_mentions_restricted_envs():
    text = GOV_DOC.read_text(encoding="utf-8")
    assert "demo" in text
    assert "release" in text
    assert "high_risk" in text or "high-risk" in text


def test_cli_reference_mentions_governance_commands():
    text = CLI_REF.read_text(encoding="utf-8")
    for cmd in ("tools policy", "tools enable", "tools disable", "tools governance-report"):
        assert cmd in text, f"Missing '{cmd}' in cli_reference.md"


def test_governance_config_exists():
    config_path = ROOT / "config" / "toolpack_governance.json"
    assert config_path.is_file(), f"Missing: {config_path}"


def test_governance_config_has_core_packs():
    import json
    config_path = ROOT / "config" / "toolpack_governance.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    core_ids = [e["toolpack_id"] for e in data["entries"] if e.get("classification") == "core"]
    assert len(core_ids) >= 1, "Governance config must have at least one core pack entry"
