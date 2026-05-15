from __future__ import annotations

from pathlib import Path


def test_toolpack_docs_exist() -> None:
    for path in (
        Path("docs/toolpack_contract.md"),
        Path("docs/toolpack_authoring_guide.md"),
        Path("docs/toolpack_examples.md"),
    ):
        assert path.is_file(), path


def test_readme_mentions_external_tool_packs() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "external tool packs" in text


def test_cli_reference_documents_taskframe_tools() -> None:
    text = Path("docs/cli_reference.md").read_text(encoding="utf-8").lower()
    assert "taskframe tools discover" in text
    assert "taskframe tools validate" in text


def test_tool_contract_checklist_mentions_toolpack_json() -> None:
    text = Path("docs/tool_contract_checklist.md").read_text(encoding="utf-8").lower()
    assert "toolpack.json" in text
