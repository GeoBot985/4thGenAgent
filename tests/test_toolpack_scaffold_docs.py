"""Tests for tool pack scaffold and contract testing documentation."""
from __future__ import annotations

from pathlib import Path

DOCS = Path("docs")


def test_scaffold_wizard_docs_exist():
    assert (DOCS / "toolpack_scaffold_wizard.md").is_file()


def test_contract_testing_docs_exist():
    assert (DOCS / "toolpack_contract_testing.md").is_file()


def test_cli_reference_documents_scaffold():
    text = (DOCS / "cli_reference.md").read_text(encoding="utf-8")
    assert "scaffold" in text


def test_cli_reference_documents_tools_test():
    text = (DOCS / "cli_reference.md").read_text(encoding="utf-8")
    assert "tools test" in text or ("tools" in text and "test" in text)


def test_cli_reference_documents_tools_examples():
    text = (DOCS / "cli_reference.md").read_text(encoding="utf-8")
    assert "examples" in text


def test_readme_mentions_scaffold_workflow():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "scaffold" in text.lower()


def test_tool_checklist_mentions_generated_contract_tests():
    checklist = DOCS / "tool_contract_checklist.md"
    if checklist.is_file():
        text = checklist.read_text(encoding="utf-8")
        assert "contract" in text.lower() or "test" in text.lower()
