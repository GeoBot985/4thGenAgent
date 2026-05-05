from pathlib import Path


def test_readme_exists() -> None:
    assert Path("README.md").exists()


def test_readme_references_core_positioning() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "taskframe" in text
    assert "manifest" in text
    assert "approval" in text
    assert "validation" in text


def test_readme_does_not_present_absa_as_default_demo() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "absa" not in text or "optional rpa tools" in text


def test_demo_docs_exist() -> None:
    assert Path("docs/demo_walkthrough.md").exists()
    assert Path("docs/demo_script.md").exists()
    assert Path("docs/core_concepts.md").exists()


def test_release_commands_documented() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "python scripts/run_golden_demo.py" in text
    assert "python scripts/run_release_verification.py" in text


def test_optional_rpa_boundary_documented() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "optional rpa tools" in text
    assert "clean-clone release verification" in text


def test_architecture_doc_exists_and_has_flow() -> None:
    text = Path("docs/architecture_overview.md").read_text(encoding="utf-8").lower()
    assert "intent / event" in text
    assert "taskframe creation" in text
    assert "validation / acceptance gate" in text


def test_screenshots_folder_linked() -> None:
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "docs/screenshots/" in text
