from __future__ import annotations

from runtime.invoiceops_showcase_demo import (
    SHOWCASE_TABS,
    REQUIRED_PROFILE,
    CONFIRMATION_TEMPLATE,
    create_or_reset_showcase_google_sheet,
    get_showcase_status,
)


def test_required_profile_is_controlled_live_write() -> None:
    assert REQUIRED_PROFILE == "controlled_live_write"


def test_confirmation_template_contains_spreadsheet_id() -> None:
    phrase = CONFIRMATION_TEMPLATE.format(spreadsheet_id="TESTID123")
    assert "TESTID123" in phrase
    assert "EXECUTE LIVE INVOICEOPS SHOWCASE" in phrase


def test_all_required_tabs_present() -> None:
    required = {
        "Dashboard", "Invoices", "PO Register", "Goods Receipts",
        "Supplier Master", "Match Results", "Exceptions", "Ledger",
        "Posting Ledger", "Reconciliation", "Rollback Plans",
        "Evidence Index", "Demo Run Log",
    }
    assert required == set(SHOWCASE_TABS), f"Tab mismatch: {required.symmetric_difference(set(SHOWCASE_TABS))}"


def test_create_sheet_returns_spec() -> None:
    spec = create_or_reset_showcase_google_sheet(spreadsheet_id="SHEET123")
    assert spec["ok"]
    assert spec["spreadsheet_id"] == "SHEET123"
    assert "Dashboard" in spec["tabs_to_create"]


def test_create_sheet_live_mode_requires_id() -> None:
    spec = create_or_reset_showcase_google_sheet(spreadsheet_id="", live_mode=True)
    assert not spec["ok"]
    assert "spreadsheet_id" in spec.get("error", "").lower()


def test_create_sheet_boundary_mode_no_id_ok() -> None:
    spec = create_or_reset_showcase_google_sheet(spreadsheet_id="", live_mode=False)
    assert spec["ok"]


def test_status_missing_spreadsheet_id_returns_needs_config(tmp_path) -> None:
    status = get_showcase_status(runtime_data_dir=str(tmp_path), spreadsheet_id="")
    assert status["ok"]
    assert status["needs_config"]
    assert status["status"] == "needs_config"


def test_status_with_spreadsheet_id_returns_ready(tmp_path) -> None:
    status = get_showcase_status(runtime_data_dir=str(tmp_path), spreadsheet_id="MYSHEET456")
    assert status["ok"]
    assert not status["needs_config"]
    assert status["status"] == "ready"
    assert "MYSHEET456" in status["spreadsheet_url"]


def test_status_fixture_count(tmp_path) -> None:
    status = get_showcase_status(runtime_data_dir=str(tmp_path))
    assert status["invoice_fixture_count"] >= 8
