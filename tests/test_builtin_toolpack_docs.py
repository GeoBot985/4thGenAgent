from __future__ import annotations

from pathlib import Path


def test_migration_docs_exist() -> None:
    assert Path("docs/builtin_toolpack_migration.md").is_file()


def test_inventory_docs_exist() -> None:
    assert Path("docs/tool_inventory.md").is_file()


def test_readme_mentions_compatibility_registry() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "compatibility registry" in text


def test_cli_reference_documents_tools_inventory_and_compat_check() -> None:
    text = Path("docs/cli_reference.md").read_text(encoding="utf-8").lower()
    assert "taskframe tools inventory" in text
    assert "taskframe tools compat-check" in text


def test_tool_contract_checklist_mentions_toolpack_json() -> None:
    text = Path("docs/tool_contract_checklist.md").read_text(encoding="utf-8").lower()
    assert "toolpack.json" in text

