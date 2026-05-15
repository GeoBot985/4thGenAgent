from __future__ import annotations

from pathlib import Path


def test_live_execution_safety_doc_exists():
    assert Path("docs/live_execution_safety.md").is_file()


def test_readme_mentions_dry_run_default():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "does not perform live side effects" in text.lower()


def test_cli_reference_documents_live_safety_commands():
    text = Path("docs/cli_reference.md").read_text(encoding="utf-8")
    for phrase in ("taskframe safety-status", "taskframe pending-actions", "taskframe live-preflight", "taskframe execute-approved"):
        assert phrase in text


def test_docs_mention_live_execution_env_and_confirmation():
    text = Path("docs/live_execution_safety.md").read_text(encoding="utf-8")
    assert "TASKFRAME_ENABLE_LIVE_EXECUTION" in text
    assert "typed confirmation" in text.lower()
