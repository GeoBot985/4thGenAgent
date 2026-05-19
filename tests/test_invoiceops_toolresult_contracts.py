from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from runtime.invoiceops_exception_tools import (
    invoiceops_build_exception_action_plan,
    invoiceops_classify_exceptions,
    invoiceops_search_po_fallback,
    invoiceops_search_receipt_fallback,
    invoiceops_search_supplier_fallback,
)
from runtime.invoiceops_extraction_tools import invoiceops_extract_invoice_fields, invoiceops_validate_invoice_fields
from runtime.invoiceops_matching_tools import (
    invoiceops_check_duplicate_invoice,
    invoiceops_check_tax,
    invoiceops_check_totals,
    invoiceops_lookup_goods_receipt,
    invoiceops_lookup_purchase_order,
    invoiceops_match_three_way,
)
from runtime.invoiceops_reader_tools import invoiceops_read_invoice_file
from runtime.invoiceops_report_tools import (
    invoiceops_build_evidence_bundle,
    invoiceops_build_exception_report,
    invoiceops_build_ledger_posting_summary,
    invoiceops_build_match_report,
    invoiceops_build_rollback_summary,
)
from runtime.invoiceops_sheet_tools import (
    invoiceops_read_exception_register,
    invoiceops_read_invoice_register,
    invoiceops_read_ledger,
    invoiceops_read_po_register,
    invoiceops_read_receipt_register,
    invoiceops_read_supplier_master,
)
from runtime.invoiceops_write_tools import (
    invoiceops_prepare_exception_register_write,
    invoiceops_prepare_invoice_register_write,
    invoiceops_prepare_ledger_write,
    invoiceops_prepare_match_register_write,
    invoiceops_prepare_rollback_plan,
)
from runtime.tool_registry import TOOL_REGISTRY
from runtime.tool_result_contract import validate_tool_result_contract


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "invoiceops"


def _load_json(*parts: str) -> dict:
    return json.loads((FIXTURE_DIR.joinpath(*parts)).read_text(encoding="utf-8"))


def _tool_results() -> dict[str, dict]:
    sample_text = invoiceops_read_invoice_file(str(FIXTURE_DIR / "sample_invoice.txt"))
    extracted = invoiceops_extract_invoice_fields(sample_text["data"]["text"], source_ref=str(FIXTURE_DIR / "sample_invoice.txt"))
    invoice = extracted["data"]["invoice"]
    validation = invoiceops_validate_invoice_fields(invoice)

    matching = _load_json("matching", "happy_path.json")
    write_invoice = _load_json("writes", "invoice.json")
    write_match = _load_json("writes", "match_result.json")
    write_exceptions = _load_json("writes", "exceptions.json")
    write_ledger = _load_json("writes", "ledger_rows.json")
    report_match = _load_json("reports", "happy_match.json")
    report_blocked = _load_json("reports", "blocked_match.json")
    report_exceptions = _load_json("reports", "exceptions_multi.json")
    report_ledger = _load_json("reports", "ledger_summary.json")
    report_rollback = _load_json("reports", "rollback_mixed.json")
    report_bundle = _load_json("reports", "evidence_bundle.json")

    supplier_master = invoiceops_read_supplier_master(fixture_mode=True, _fixture_dir=str(FIXTURE_DIR / "sheets"))
    po_register = invoiceops_read_po_register(fixture_mode=True, _fixture_dir=str(FIXTURE_DIR / "sheets"))
    receipt_register = invoiceops_read_receipt_register(fixture_mode=True, _fixture_dir=str(FIXTURE_DIR / "sheets"))
    invoice_register = invoiceops_read_invoice_register(fixture_mode=True, _fixture_dir=str(FIXTURE_DIR / "sheets"))
    ledger_sheet = invoiceops_read_ledger(fixture_mode=True, _fixture_dir=str(FIXTURE_DIR / "sheets"))
    exception_register = invoiceops_read_exception_register(fixture_mode=True, _fixture_dir=str(FIXTURE_DIR / "sheets"))

    match_result = invoiceops_match_three_way(matching["invoice"], matching["purchase_order"], matching["goods_receipt"], matching["invoice_register"])
    duplicate_check = invoiceops_check_duplicate_invoice(invoice, invoice_register["data"]["records"])
    purchase_order_check = invoiceops_lookup_purchase_order(invoice, po_register["data"]["records"])
    goods_receipt_check = invoiceops_lookup_goods_receipt(invoice, receipt_register["data"]["records"])
    totals_check = invoiceops_check_totals(matching["invoice"], matching["purchase_order"])
    tax_check = invoiceops_check_tax(invoice)

    classify = invoiceops_classify_exceptions({"data": {"match_result": {"exceptions": report_exceptions["exceptions"]}}}, report_exceptions["invoice"])
    fallback_po = invoiceops_search_po_fallback(invoice, po_register["data"]["records"])
    fallback_receipt = invoiceops_search_receipt_fallback(invoice, receipt_register["data"]["records"])
    fallback_supplier = invoiceops_search_supplier_fallback(invoice, supplier_master["data"]["records"])
    action_plan = invoiceops_build_exception_action_plan(report_exceptions["invoice"], report_exceptions["exceptions"], report_exceptions["action_plan"].get("fallback_results"))

    prepared_invoice = invoiceops_prepare_invoice_register_write(write_invoice)
    prepared_match = invoiceops_prepare_match_register_write(write_match)
    prepared_exceptions = invoiceops_prepare_exception_register_write(write_exceptions)
    prepared_ledger = invoiceops_prepare_ledger_write(write_ledger)
    rollback_plan = invoiceops_prepare_rollback_plan(prepared_invoice["data"]["prepared_write"])

    match_report = invoiceops_build_match_report(report_match["invoice"], report_match["match_result"])
    blocked_report = invoiceops_build_match_report(report_blocked["invoice"], report_blocked["match_result"])
    exception_report = invoiceops_build_exception_report(report_exceptions["invoice"], report_exceptions["exceptions"], report_exceptions["action_plan"])
    ledger_report = invoiceops_build_ledger_posting_summary(report_ledger["invoice"], report_ledger["ledger_rows"])
    rollback_report = invoiceops_build_rollback_summary(report_rollback["prepared_writes"])
    evidence_bundle = invoiceops_build_evidence_bundle(report_bundle["invoice"], report_bundle["match_result"], report_bundle["exceptions"], report_bundle["prepared_writes"])

    return {
        "invoiceops/read_invoice_file": sample_text,
        "invoiceops/extract_invoice_fields": extracted,
        "invoiceops/validate_invoice_fields": validation,
        "invoiceops/read_supplier_master": supplier_master,
        "invoiceops/read_po_register": po_register,
        "invoiceops/read_receipt_register": receipt_register,
        "invoiceops/read_invoice_register": invoice_register,
        "invoiceops/read_ledger": ledger_sheet,
        "invoiceops/read_exception_register": exception_register,
        "invoiceops/check_duplicate_invoice": duplicate_check,
        "invoiceops/lookup_purchase_order": purchase_order_check,
        "invoiceops/lookup_goods_receipt": goods_receipt_check,
        "invoiceops/check_totals": totals_check,
        "invoiceops/check_tax": tax_check,
        "invoiceops/match_three_way": match_result,
        "invoiceops/classify_exceptions": classify,
        "invoiceops/search_po_fallback": fallback_po,
        "invoiceops/search_receipt_fallback": fallback_receipt,
        "invoiceops/search_supplier_fallback": fallback_supplier,
        "invoiceops/build_exception_action_plan": action_plan,
        "invoiceops/prepare_invoice_register_write": prepared_invoice,
        "invoiceops/prepare_match_register_write": prepared_match,
        "invoiceops/prepare_exception_register_write": prepared_exceptions,
        "invoiceops/prepare_ledger_write": prepared_ledger,
        "invoiceops/prepare_rollback_plan": rollback_plan,
        "invoiceops/build_match_report": match_report,
        "invoiceops/build_exception_report": exception_report,
        "invoiceops/build_ledger_posting_summary": ledger_report,
        "invoiceops/build_rollback_summary": rollback_report,
        "invoiceops/build_evidence_bundle": evidence_bundle,
    }


def test_toolresult_contract_is_enforced_for_all_invoiceops_tools() -> None:
    with patch("runtime.google_sheet_tools.sheet_read_range", side_effect=AssertionError("live sheet read must not be called")), patch(
        "runtime.google_sheet_tools.sheet_write_rows",
        side_effect=AssertionError("live sheet write must not be called"),
    ), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=AssertionError("live write_sheet_entries must not be called"),
    ):
        results = _tool_results()

    for tool_key, result in results.items():
        expected_type = TOOL_REGISTRY[tool_key]["output_type"]
        contract = validate_tool_result_contract(result, expected_type=expected_type)
        assert contract["ok"] is True, f"{tool_key}: {contract['errors']}"
        assert result["type"] == expected_type, tool_key


def test_successful_read_extraction_matching_prepared_write_and_report_outputs_include_evidence() -> None:
    results = _tool_results()
    for tool_key in (
        "invoiceops/read_invoice_file",
        "invoiceops/extract_invoice_fields",
        "invoiceops/match_three_way",
        "invoiceops/prepare_invoice_register_write",
        "invoiceops/build_match_report",
        "invoiceops/build_exception_report",
        "invoiceops/build_ledger_posting_summary",
        "invoiceops/build_rollback_summary",
        "invoiceops/build_evidence_bundle",
    ):
        assert results[tool_key]["evidence"], tool_key


def test_failed_tools_return_ok_false_and_clear_error() -> None:
    failure_cases = [
        (invoiceops_read_invoice_file, ("",), "UNSUPPORTED_INVOICE_FILE_TYPE"),
        (invoiceops_extract_invoice_fields, ("",), "INVOICE_TEXT_EMPTY"),
        (invoiceops_validate_invoice_fields, ("not-a-dict",), "INVALID_INVOICE_INPUT"),
        (invoiceops_prepare_invoice_register_write, ({},), "INVALID_INVOICE_FOR_WRITE"),
        (invoiceops_prepare_match_register_write, ({},), "INVALID_MATCH_RESULT_FOR_WRITE"),
        (invoiceops_prepare_rollback_plan, ({},), "ROLLBACK_PLAN_REQUIRED"),
        (invoiceops_build_match_report, ({}, {}), "INVALID_INVOICE_FOR_REPORT"),
        (invoiceops_build_exception_report, ({}, [{"exception_id": "bad"}]), "INVALID_INVOICE_FOR_REPORT"),
        (invoiceops_build_ledger_posting_summary, ({}, []), "INVALID_INVOICE_FOR_REPORT"),
        (invoiceops_build_evidence_bundle, ({},), "INVALID_INVOICE_FOR_REPORT"),
    ]
    for fn, args, expected_error_part in failure_cases:
        result = fn(*args)  # type: ignore[misc]
        assert result["ok"] is False
        assert result["error"]
        assert expected_error_part.lower() in result["error"].lower()


def test_registry_output_types_match_actual_tool_result_types() -> None:
    results = _tool_results()
    for tool_key, result in results.items():
        assert result["type"] == TOOL_REGISTRY[tool_key]["output_type"], tool_key


def test_no_live_write_helper_is_called() -> None:
    with patch("runtime.google_sheet_tools.sheet_write_rows", side_effect=AssertionError("live sheet write must not be called")), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=AssertionError("live write_sheet_entries must not be called"),
    ):
        _tool_results()
