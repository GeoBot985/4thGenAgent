from pathlib import Path


def test_optional_rpa_doc_exists():
    assert Path("docs/optional_rpa.md").is_file()


def test_optional_rpa_doc_contains_safety_warning():
    text = Path("docs/optional_rpa.md").read_text(encoding="utf-8").lower()
    assert "safety warning" in text
    assert "browser" in text
    assert "authenticated" in text
    assert "excluded from the default" in text


def test_optional_rpa_doc_has_required_sections():
    text = Path("docs/optional_rpa.md").read_text(encoding="utf-8").lower()
    for section in [
        "overview",
        "why rpa is optional",
        "safety warning",
        "dependencies",
        "configuration",
        "browser profile",
        "live probe",
        "troubleshooting",
    ]:
        assert section in text, f"docs/optional_rpa.md missing section: {section!r}"


def test_readme_links_optional_rpa_doc():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "docs/optional_rpa.md" in text


def test_cli_reference_documents_rpa_commands():
    text = Path("docs/cli_reference.md").read_text(encoding="utf-8")
    assert "taskframe rpa status" in text
    assert "taskframe rpa health" in text


def test_optional_rpa_doc_mentions_playwright():
    text = Path("docs/optional_rpa.md").read_text(encoding="utf-8").lower()
    assert "playwright" in text


def test_optional_rpa_doc_mentions_not_required_for_default():
    text = Path("docs/optional_rpa.md").read_text(encoding="utf-8").lower()
    assert "taskframe demo" in text or "default demo" in text


def test_optional_rpa_doc_mentions_browser_profile_risk():
    text = Path("docs/optional_rpa.md").read_text(encoding="utf-8").lower()
    assert "browser profile" in text
    assert "sensitive" in text
