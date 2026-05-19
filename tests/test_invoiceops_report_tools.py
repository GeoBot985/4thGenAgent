from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from runtime.invoiceops_contracts import validate_report_shape
from runtime.invoiceops_report_tools import (
    invoiceops_build_evidence_bundle,
    invoiceops_build_exception_report,
    invoiceops_build_ledger_posting_summary,
    invoiceops_build_match_report,
    invoiceops_build_rollback_summary,
)
from runtime.invoiceops_write_tools import (
    invoiceops_prepare_exception_register_write,
    invoiceops_prepare_invoice_register_write,
    invoiceops_prepare_ledger_write,
)
from runtime.tool_result_contract import validate_tool_result_contract

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "invoiceops" / "reports"


def _load(name: str):
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


_HAPPY = _load("happy_match.json")
_BLOCKED = _load("blocked_match.json")
_EXC_MULTI = _load("exceptions_multi.json")
_LEDGER = _load("ledger_summary.json")
_ROLLBACK = _load("rollback_mixed.json")
_BUNDLE = _load("evidence_bundle.json")


def _assert_tool_result(result: dict) -> None:
    contract = validate_tool_result_contract(result, expected_type="invoiceops_report")
    assert contract["ok"] is True, contract["errors"]


def test_match_report_happy_path() -> None:
    result = invoiceops_build_match_report(_HAPPY["invoice"], _HAPPY["match_result"])
    assert result["ok"] is True
    assert result["type"] == "invoiceops_report"
    report = result["data"]["report"]
    assert report["invoice_number"] == "INV-2024-001"
    assert report["match_status"] == "matched"
    assert report["ledger_posting_allowed"] is True
    assert report["prepared_write_allowed"] is True
    assert report["check_summary"]["pass"] == 3
    assert validate_report_shape(report)["ok"] is True
    _assert_tool_result(result)


def test_match_report_blocked_match() -> None:
    result = invoiceops_build_match_report(_BLOCKED["invoice"], _BLOCKED["match_result"])
    report = result["data"]["report"]
    assert report["match_status"] == "blocked"
    assert report["prepared_write_decision"] == "blocked"
    assert report["check_summary"]["fail"] >= 1
    assert validate_report_shape(report)["ok"] is True
    _assert_tool_result(result)


def test_exception_report_multiple_exceptions() -> None:
    result = invoiceops_build_exception_report(
        _EXC_MULTI["invoice"],
        _EXC_MULTI["exceptions"],
        _EXC_MULTI["action_plan"],
    )
    report = result["data"]["report"]
    assert report["exception_count"] == 3
    assert set(report["exception_types"]) == {"amount_mismatch", "tax_mismatch", "missing_receipt"}
    assert report["blocking_status"] is True
    assert report["operator_review_required"] is True
    assert report["recommended_action"] == "operator_review"
    assert report["severity_summary"]["high"] == 1
    assert validate_report_shape(report)["ok"] is True
    _assert_tool_result(result)


def test_ledger_posting_summary_valid_rows() -> None:
    result = invoiceops_build_ledger_posting_summary(_LEDGER["invoice"], _LEDGER["ledger_rows"])
    report = result["data"]["report"]
    assert report["ledger_row_count"] == 1
    assert report["debit_account"] == "5000"
    assert report["credit_account"] == "2000"
    assert report["amount"] == 1150.0
    assert report["currency"] == "ZAR"
    assert report["posting_allowed"] is True
    assert validate_report_shape(report)["ok"] is True
    _assert_tool_result(result)


def test_rollback_summary_mixed_types() -> None:
    result = invoiceops_build_rollback_summary(_ROLLBACK["prepared_writes"])
    report = result["data"]["report"]
    assert report["prepared_write_count"] == 3
    assert set(report["target_registers"]) == {"InvoiceRegister", "Ledger", "ExceptionRegister"}
    assert len(report["rollback_type_by_write"]) == 3
    assert report["manual_review_required"] is True
    assert report["unsafe_rollback_warnings"]
    assert validate_report_shape(report)["ok"] is True
    _assert_tool_result(result)


def test_evidence_bundle_includes_all_supplied_evidence() -> None:
    result = invoiceops_build_evidence_bundle(
        _BUNDLE["invoice"],
        _BUNDLE["match_result"],
        _BUNDLE["exceptions"],
        _BUNDLE["prepared_writes"],
    )
    report = result["data"]["report"]
    sections = {section["section"]: section["items"] for section in report["evidence"]}
    assert "invoice_source_evidence" in sections
    assert "extraction_evidence" in sections
    assert "matching_evidence" in sections
    assert "exception_evidence" in sections
    assert "prepared_write_evidence" in sections
    assert "rollback_evidence" in sections
    assert sections["matching_evidence"]
    assert sections["prepared_write_evidence"]
    assert sections["rollback_evidence"]
    assert validate_report_shape(report)["ok"] is True
    _assert_tool_result(result)


def test_invalid_inputs_fail_safely() -> None:
    cases = [
        (invoiceops_build_match_report, (None, {}), "INVALID_INVOICE_FOR_REPORT"),
        (invoiceops_build_match_report, (_HAPPY["invoice"], {}), "INVALID_MATCH_RESULT_FOR_REPORT"),
        (invoiceops_build_exception_report, (_HAPPY["invoice"], [{"exception_id": "bad"}]), "INVALID_EXCEPTION_FOR_REPORT"),
        (invoiceops_build_ledger_posting_summary, (_HAPPY["invoice"], [{"ledger_entry_id": "bad"}]), "INVALID_LEDGER_ROW_FOR_REPORT"),
        (invoiceops_build_rollback_summary, ([{"prepared_write_id": "bad"}],), "INVALID_PREPARED_WRITE_FOR_REPORT"),
        (invoiceops_build_evidence_bundle, (None,), "INVALID_INVOICE_FOR_REPORT"),
    ]
    for fn, args, expected_error in cases:
        result = fn(*args)  # type: ignore[misc]
        assert result["ok"] is False
        assert result["error"] == expected_error


def test_all_outputs_are_toolresult_compatible() -> None:
    prepared_invoice = invoiceops_prepare_invoice_register_write(_HAPPY["invoice"])["data"]["prepared_write"]
    prepared_ledger = invoiceops_prepare_ledger_write(_LEDGER["ledger_rows"])["data"]["prepared_write"]
    prepared_exceptions = invoiceops_prepare_exception_register_write(_EXC_MULTI["exceptions"])["data"]["prepared_write"]
    results = [
        invoiceops_build_match_report(_HAPPY["invoice"], _HAPPY["match_result"]),
        invoiceops_build_exception_report(_EXC_MULTI["invoice"], _EXC_MULTI["exceptions"], _EXC_MULTI["action_plan"]),
        invoiceops_build_ledger_posting_summary(_LEDGER["invoice"], _LEDGER["ledger_rows"]),
        invoiceops_build_rollback_summary([prepared_invoice, prepared_ledger, prepared_exceptions]),
        invoiceops_build_evidence_bundle(_BUNDLE["invoice"], _BUNDLE["match_result"], _BUNDLE["exceptions"], _BUNDLE["prepared_writes"]),
    ]
    for result in results:
        _assert_tool_result(result)


def test_no_writes_or_side_effects_occur() -> None:
    with patch("runtime.google_sheet_tools.sheet_write_rows", side_effect=AssertionError("live sheet_write_rows must not be called")), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=AssertionError("live write_sheet_entries must not be called"),
    ):
        invoiceops_build_match_report(_HAPPY["invoice"], _HAPPY["match_result"])
        invoiceops_build_exception_report(_EXC_MULTI["invoice"], _EXC_MULTI["exceptions"], _EXC_MULTI["action_plan"])
        invoiceops_build_ledger_posting_summary(_LEDGER["invoice"], _LEDGER["ledger_rows"])
        invoiceops_build_rollback_summary(_ROLLBACK["prepared_writes"])
        invoiceops_build_evidence_bundle(_BUNDLE["invoice"], _BUNDLE["match_result"], _BUNDLE["exceptions"], _BUNDLE["prepared_writes"])

