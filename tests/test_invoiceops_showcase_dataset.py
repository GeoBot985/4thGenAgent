from __future__ import annotations

from runtime.invoiceops_showcase_demo import (
    SHOWCASE_SCENARIOS,
    SHOWCASE_TABS,
    build_showcase_demo_dataset,
)


def test_all_scenarios_defined() -> None:
    assert len(SHOWCASE_SCENARIOS) >= 8


def test_required_scenario_keys() -> None:
    required = {
        "invoice_number", "scenario", "scenario_label", "supplier_name",
        "po_number", "expected_match_status", "expected_posting_status",
        "expected_reconciliation_status", "expected_exception_type",
    }
    for s in SHOWCASE_SCENARIOS:
        missing = required - s.keys()
        assert not missing, f"{s['invoice_number']} missing keys: {missing}"


def test_inv_001_is_clean_match() -> None:
    inv001 = next(s for s in SHOWCASE_SCENARIOS if s["invoice_number"] == "INV-001")
    assert inv001["expected_match_status"] == "matched"
    assert inv001["expected_posting_status"] == "EXECUTED_VERIFIED"
    assert inv001["expected_reconciliation_status"] == "RECONCILED"
    assert inv001["expected_exception_type"] == ""


def test_inv_002_is_duplicate() -> None:
    inv002 = next(s for s in SHOWCASE_SCENARIOS if s["invoice_number"] == "INV-002")
    assert inv002["expected_match_status"] == "exception"
    assert inv002["expected_exception_type"] == "DUPLICATE_INVOICE"


def test_all_exception_types_are_distinct() -> None:
    exceptions = [s["expected_exception_type"] for s in SHOWCASE_SCENARIOS if s["expected_exception_type"]]
    assert len(exceptions) == len(set(exceptions)), "Duplicate exception types in scenarios"


def test_match_statuses_are_valid() -> None:
    valid = {"matched", "exception", "blocked"}
    for s in SHOWCASE_SCENARIOS:
        assert s["expected_match_status"] in valid, f"{s['invoice_number']}: bad match status"


def test_dataset_returns_all_scenarios() -> None:
    ds = build_showcase_demo_dataset()
    assert ds["ok"]
    assert len(ds["scenarios"]) == len(SHOWCASE_SCENARIOS)
    assert len(ds["supplier_master"]) >= 5
    assert len(ds["po_register"]) >= 5
    assert len(ds["goods_receipts"]) >= 5


def test_dataset_invoice_limit() -> None:
    ds = build_showcase_demo_dataset(invoice_limit=3)
    assert ds["invoice_count"] == 3
    assert len(ds["scenarios"]) == 3


def test_all_fixture_files_listed_in_dir() -> None:
    from pathlib import Path
    fixture_dir = Path("fixtures/invoiceops_showcase/invoices")
    assert fixture_dir.is_dir(), "Fixture directory must exist"
    files = sorted(fixture_dir.glob("INV-*.txt"))
    assert len(files) >= 8, f"Expected >= 8 fixture files, found {len(files)}"


def test_showcase_tabs_list() -> None:
    required_tabs = {
        "Dashboard", "Invoices", "PO Register", "Goods Receipts",
        "Supplier Master", "Match Results", "Exceptions", "Ledger",
        "Posting Ledger", "Reconciliation", "Rollback Plans",
        "Evidence Index", "Demo Run Log",
    }
    assert required_tabs.issubset(set(SHOWCASE_TABS))


def test_talking_points_non_empty() -> None:
    for s in SHOWCASE_SCENARIOS:
        assert s.get("talking_point"), f"{s['invoice_number']} missing talking_point"
