from __future__ import annotations

"""
Boundary-only checks for the Spec 158 release verifier.
Mirrors the checks in tools/run_release_candidate_verification.py without
invoking the full verifier pipeline.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_showcase_demo_module_exists() -> None:
    assert (ROOT / "runtime" / "invoiceops_showcase_demo.py").is_file()


def test_showcase_sheet_formatting_module_exists() -> None:
    assert (ROOT / "runtime" / "invoiceops_showcase_sheet_formatting.py").is_file()


def test_fixture_directory_exists() -> None:
    assert (ROOT / "fixtures" / "invoiceops_showcase" / "invoices").is_dir()


def test_fixture_files_exist() -> None:
    fixture_dir = ROOT / "fixtures" / "invoiceops_showcase" / "invoices"
    files = sorted(fixture_dir.glob("INV-*.txt"))
    assert len(files) >= 8, f"Expected >= 8 fixture files, got {len(files)}"


def test_config_example_exists() -> None:
    assert (ROOT / "config" / "examples" / "invoiceops_showcase.example.json").is_file()


def test_showcase_demo_module_has_required_symbols() -> None:
    content = (ROOT / "runtime" / "invoiceops_showcase_demo.py").read_text(encoding="utf-8")
    for symbol in (
        "build_showcase_demo_dataset",
        "create_or_reset_showcase_google_sheet",
        "apply_showcase_sheet_formatting",
        "run_showcase_invoice_batch",
        "build_showcase_posting_plan",
        "execute_showcase_live_posting",
        "run_showcase_reconciliation",
        "build_showcase_dashboard_data",
        "write_showcase_demo_report",
        "render_showcase_demo_markdown",
        "get_showcase_status",
        "REQUIRED_PROFILE",
        "CONFIRMATION_TEMPLATE",
        "SHOWCASE_TABS",
    ):
        assert symbol in content, f"Missing symbol: {symbol}"


def test_showcase_formatting_module_has_required_symbols() -> None:
    content = (ROOT / "runtime" / "invoiceops_showcase_sheet_formatting.py").read_text(encoding="utf-8")
    for symbol in (
        "build_showcase_formatting_spec",
        "get_tab_headers",
        "get_all_tab_headers",
    ):
        assert symbol in content, f"Missing symbol: {symbol}"


def test_cli_has_showcase_commands() -> None:
    content = (ROOT / "src" / "taskframe_cli.py").read_text(encoding="utf-8")
    for token in ("showcase", "_run_invoiceops_showcase", "iosc_command", "setup-sheet"):
        assert token in content, f"CLI missing token: {token}"


def test_import_showcase_demo_no_side_effects() -> None:
    from runtime.invoiceops_showcase_demo import (
        SHOWCASE_TABS,
        REQUIRED_PROFILE,
        CONFIRMATION_TEMPLATE,
        build_showcase_demo_dataset,
    )
    assert REQUIRED_PROFILE == "controlled_live_write"
    assert "Dashboard" in SHOWCASE_TABS
    dataset = build_showcase_demo_dataset()
    assert dataset["ok"]
    assert dataset["invoice_count"] >= 8


def test_boundary_run_does_not_perform_live_writes() -> None:
    from runtime.invoiceops_showcase_demo import run_showcase_invoice_batch
    result = run_showcase_invoice_batch(live_mode=False, invoice_limit=1)
    assert result["ok"]
    assert result["live_side_effects_performed"] is False
    assert result["live_writes_performed"] == 0


def test_live_run_blocked_without_confirmation() -> None:
    from runtime.invoiceops_showcase_demo import run_showcase_invoice_batch, REQUIRED_PROFILE
    result = run_showcase_invoice_batch(
        live_mode=True,
        profile=REQUIRED_PROFILE,
        spreadsheet_id="SHEET_RC",
        confirm="wrong",
    )
    assert not result["ok"]
    assert result["live_side_effects_performed"] is False
