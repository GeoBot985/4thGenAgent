from pathlib import Path


def test_readme_has_public_onboarding_sections():
    text = Path("README.md").read_text(encoding="utf-8").lower()
    for phrase in [
        "what this is",
        "what this is not",
        "5-minute quickstart",
        "safe by default",
        "demo workflows",
        "cli commands",
        "optional integrations",
    ]:
        assert phrase in text, f"README missing section: {phrase!r}"


def test_readme_has_quickstart_commands():
    text = Path("README.md").read_text(encoding="utf-8")
    for command in [
        "pip install -e .",
        "taskframe demo",
        "taskframe ui",
        "taskframe verify",
    ]:
        assert command in text, f"README missing command: {command!r}"


def test_readme_states_safe_default_behavior():
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "safe by default" in text
    assert "no live emails" in text or "no live email" in text
    assert "no live google sheets" in text or "no live sheet" in text
    assert "no browser/rpa" in text or "no browser" in text


def test_quickstart_doc_exists():
    assert Path("docs/quickstart.md").is_file()


def test_docs_index_exists():
    assert Path("docs/index.md").is_file()


def test_readme_links_key_docs():
    text = Path("README.md").read_text(encoding="utf-8")
    for path in [
        "docs/quickstart.md",
        "docs/cli_reference.md",
        "docs/architecture_overview.md",
        "docs/index.md",
    ]:
        assert path in text, f"README missing link to: {path!r}"


def test_readme_mentions_optional_integrations_not_required():
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "optional" in text
    assert "not required" in text or "not needed" in text


def test_readme_mentions_no_live_side_effects_by_default():
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "by default" in text
    assert "no live" in text


def test_quickstart_doc_has_required_sections():
    text = Path("docs/quickstart.md").read_text(encoding="utf-8").lower()
    for section in [
        "requirements",
        "windows",
        "linux",
        "troubleshooting",
        "pip install -e .",
        "taskframe demo",
        "taskframe ui",
        "taskframe verify",
    ]:
        assert section in text, f"docs/quickstart.md missing: {section!r}"


def test_docs_index_links_key_sections():
    text = Path("docs/index.md").read_text(encoding="utf-8").lower()
    for section in [
        "architecture",
        "manifests",
        "tools",
        "release",
    ]:
        assert section in text, f"docs/index.md missing section: {section!r}"
