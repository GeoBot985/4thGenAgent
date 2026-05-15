from __future__ import annotations

import json
from pathlib import Path


def test_gitignore_excludes_common_secret_files() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    for pattern in [
        ".taskframe/",
        "*.local.json",
        "config/*.local.json",
        "config/*credentials*.json",
        "config/*token*.json",
        "credentials.json",
        "google_token.json",
        "client_secret*.json",
    ]:
        assert pattern in text


def test_no_real_credentials_committed_to_config_examples() -> None:
    example_dir = Path("config/examples")
    for path in example_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(payload).lower()
        assert "ya29." not in text
        assert "super-secret" not in text
        assert "private key" not in text
        if path.name == "accounting_google_sheet.example.json":
            assert "<your-spreadsheet-id>" in text
        elif path.name == "taskframe.rpa-local.example.json":
            assert "<you>" in text
        elif path.name == "taskframe.google-live.example.json":
            assert "~/.taskframe/google/credentials.json" in text
        else:
            assert '"provider": "fake"' in text or '"provider": "ollama"' in text


def test_readme_links_configuration_doc() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "docs/configuration.md" in text


def test_configuration_doc_mentions_not_to_commit_secrets() -> None:
    text = Path("docs/configuration.md").read_text(encoding="utf-8").lower()
    assert "do not commit" in text
    assert "credentials" in text
    assert "tokens" in text
