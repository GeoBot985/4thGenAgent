from pathlib import Path


def test_readme_exists():
    assert Path("README.md").is_file()


def test_architecture_overview_exists():
    assert Path("docs/architecture_overview.md").is_file()


def test_architecture_diagram_asset_exists():
    assert Path("docs/architecture_diagram.svg").is_file()
    assert Path("docs/architecture_diagram.mmd").is_file()


def test_demo_script_exists():
    assert Path("docs/demo_script.md").is_file()


def test_portfolio_summary_exists():
    assert Path("docs/portfolio_summary.md").is_file()


def test_screenshots_folder_exists():
    assert Path("docs/screenshots").is_dir()


def test_readme_mentions_taskframe():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "TaskFrame" in text


def test_readme_mentions_manifest():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "manifest" in text.lower()


def test_readme_mentions_customer_procurement_accounting():
    text = Path("README.md").read_text(encoding="utf-8")
    for term in ("Customer Support", "Procurement", "Accounting"):
        assert term in text


def test_readme_mentions_dry_run():
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "dry-run" in text


def test_readme_mentions_ollama():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Ollama" in text
