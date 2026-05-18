from __future__ import annotations

from pathlib import Path


def test_manifest_regression_gallery_docs_exist() -> None:
    path = Path("docs/manifest_regression_gallery.md")
    assert path.is_file()
    text = path.read_text(encoding="utf-8").lower()
    assert "manifest regression gallery" in text
    assert "autofix" in text
    assert "strict validation" in text


def test_cli_reference_mentions_gallery_commands() -> None:
    text = Path("docs/cli_reference.md").read_text(encoding="utf-8").lower()
    assert "manifests gallery list" in text
    assert "manifests gallery validate" in text
    assert "manifests gallery run" in text
    assert "manifests gallery report" in text
