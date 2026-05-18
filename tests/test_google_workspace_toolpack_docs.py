from __future__ import annotations

from pathlib import Path


def test_google_workspace_docs_exist() -> None:
    assert Path("docs/google_workspace_readonly_toolpack.md").is_file()
    assert Path("docs/google_workspace_setup.md").is_file()
    assert Path("docs/google_workspace_integration_tests.md").is_file()


def test_readme_mentions_google_workspace_tool_pack() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Google Workspace tool pack" in text
    assert "does not send, create, update, delete, move, or write anything" in text


def test_cli_reference_documents_taskframe_tools_google_workspace_commands() -> None:
    text = Path("docs/cli_reference.md").read_text(encoding="utf-8")
    assert "taskframe tools inspect gmail/list_unread" in text
    assert "taskframe tools health google_workspace" in text


def test_tool_contract_checklist_mentions_toolpack_json() -> None:
    text = Path("docs/tool_contract_checklist.md").read_text(encoding="utf-8")
    assert "toolpack.json" in text


def test_google_workspace_docs_warn_read_only_only() -> None:
    text = Path("docs/google_workspace_readonly_toolpack.md").read_text(encoding="utf-8").lower()
    assert "read-only" in text
    assert "no send, create, update, delete, move, archive, or write operations" in text


def test_google_workspace_docs_explain_credentials_are_optional() -> None:
    text = Path("docs/google_workspace_setup.md").read_text(encoding="utf-8").lower()
    assert "clean clone" in text or "clean-clone" in text
    assert "optional" in text


def test_google_workspace_docs_explain_live_probe_is_manual() -> None:
    text = Path("docs/google_workspace_readonly_toolpack.md").read_text(encoding="utf-8").lower()
    assert "live probe is manual" in text
