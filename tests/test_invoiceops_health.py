from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import runtime.invoiceops_health as invoiceops_health


def test_contract_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_contracts_health()
    assert result["tool_id"] == "invoiceops"
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["severity"] == "info"
    assert result["checked_at"]
    assert isinstance(result["details"], dict)


def test_reader_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_reader_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["details"]["tool_result_contract"]["ok"] is True


def test_extraction_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_extraction_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["details"]["extract_result"]["ok"] is True


def test_sheet_fixture_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_sheet_fixture_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert set(result["details"]["results"]) == {
        "supplier_master",
        "po_register",
        "receipt_register",
        "invoice_register",
        "ledger",
        "exception_register",
    }


def test_matching_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_matching_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["details"]["result"]["type"] == "invoiceops_match_result"


def test_exception_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_exception_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["details"]["classify_result"]["type"] == "invoiceops_exception_classification"


def test_prepared_write_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_prepared_write_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["details"]["results"]["ledger"]["data"]["prepared_write"]["rollback_plan"]["rollback_type"] == "mark_reversed"


def test_reporting_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_reporting_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["details"]["results"]["match"]["type"] == "invoiceops_report"


def test_registry_health_passes_in_fixture_mode() -> None:
    result = invoiceops_health.invoiceops_registry_health()
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert "checks" in result["details"]


def test_check_tool_health_includes_invoiceops() -> None:
    from runtime.tool_health import check_all_tool_health, check_tool_health

    result = check_tool_health("invoiceops", live=False)
    assert result.ok is True
    assert result.status == "healthy"
    assert result.details["checks"]["registry"]["ok"] is True

    results = check_all_tool_health(include_optional=False, live_rpa=False)
    assert any(item.tool_id == "invoiceops" for item in results)


def test_missing_fixture_data_produces_warning_or_failure() -> None:
    with patch.object(invoiceops_health, "_SAMPLE_INVOICE_TEXT", Path("tests/fixtures/invoiceops/missing_invoice.txt")):
        result = invoiceops_health.invoiceops_registry_health()
        assert result["ok"] is False
        assert result["status"] in {"warning", "failed"}
        assert result["severity"] in {"warning", "error"}
        assert result["details"]["issues"]


def test_no_live_calls_or_writes_occur() -> None:
    with patch("runtime.google_sheet_tools.sheet_read_range", side_effect=AssertionError("live sheet read must not be called")), patch(
        "runtime.google_sheet_tools.sheet_write_rows",
        side_effect=AssertionError("live sheet write must not be called"),
    ), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=AssertionError("live write_sheet_entries must not be called"),
    ):
        invoiceops_health.invoiceops_registry_health()
        invoiceops_health.invoiceops_reader_health()
        invoiceops_health.invoiceops_extraction_health()
        invoiceops_health.invoiceops_sheet_fixture_health()
        invoiceops_health.invoiceops_matching_health()
        invoiceops_health.invoiceops_exception_health()
        invoiceops_health.invoiceops_prepared_write_health()
        invoiceops_health.invoiceops_reporting_health()
