from pathlib import Path


def test_default_demo_boundary_exists() -> None:
    assert Path("docs/default_demo_boundary.md").is_file()


def test_default_demo_boundary_excludes_optional_rpa() -> None:
    text = Path("docs/default_demo_boundary.md").read_text(encoding="utf-8").lower()
    assert "optional rpa" in text
    assert "excluded" in text
    assert "default rc" in text


def test_default_demo_boundary_includes_core_workflows() -> None:
    text = Path("docs/default_demo_boundary.md").read_text(encoding="utf-8").lower()
    for term in ("customer workflow", "procurement workflow", "accounting workflow", "approval gate", "dry-run execution", "audit evidence"):
        assert term in text
