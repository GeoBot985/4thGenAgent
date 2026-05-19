from __future__ import annotations

import importlib

from runtime.tool_registry import TOOL_REGISTRY


EXPECTED_TOOLS = {
    "invoiceops/read_invoice_file": ("runtime.invoiceops_reader_tools", "invoiceops_read_invoice_file", "invoiceops_raw_invoice_text"),
    "invoiceops/extract_invoice_fields": ("runtime.invoiceops_extraction_tools", "invoiceops_extract_invoice_fields", "invoiceops_invoice"),
    "invoiceops/validate_invoice_fields": ("runtime.invoiceops_extraction_tools", "invoiceops_validate_invoice_fields", "invoiceops_invoice_validation"),
    "invoiceops/read_supplier_master": ("runtime.invoiceops_sheet_tools", "invoiceops_read_supplier_master", "invoiceops_sheet_rows"),
    "invoiceops/read_po_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_po_register", "invoiceops_sheet_rows"),
    "invoiceops/read_receipt_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_receipt_register", "invoiceops_sheet_rows"),
    "invoiceops/read_invoice_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_invoice_register", "invoiceops_sheet_rows"),
    "invoiceops/read_ledger": ("runtime.invoiceops_sheet_tools", "invoiceops_read_ledger", "invoiceops_sheet_rows"),
    "invoiceops/read_exception_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_exception_register", "invoiceops_sheet_rows"),
    "invoiceops/check_duplicate_invoice": ("runtime.invoiceops_matching_tools", "invoiceops_check_duplicate_invoice", "invoiceops_match_check"),
    "invoiceops/lookup_purchase_order": ("runtime.invoiceops_matching_tools", "invoiceops_lookup_purchase_order", "invoiceops_match_check"),
    "invoiceops/lookup_goods_receipt": ("runtime.invoiceops_matching_tools", "invoiceops_lookup_goods_receipt", "invoiceops_match_check"),
    "invoiceops/check_totals": ("runtime.invoiceops_matching_tools", "invoiceops_check_totals", "invoiceops_match_check"),
    "invoiceops/check_tax": ("runtime.invoiceops_matching_tools", "invoiceops_check_tax", "invoiceops_match_check"),
    "invoiceops/match_three_way": ("runtime.invoiceops_matching_tools", "invoiceops_match_three_way", "invoiceops_match_result"),
    "invoiceops/classify_exceptions": ("runtime.invoiceops_exception_tools", "invoiceops_classify_exceptions", "invoiceops_exception_classification"),
    "invoiceops/search_po_fallback": ("runtime.invoiceops_exception_tools", "invoiceops_search_po_fallback", "invoiceops_fallback_result"),
    "invoiceops/search_receipt_fallback": ("runtime.invoiceops_exception_tools", "invoiceops_search_receipt_fallback", "invoiceops_fallback_result"),
    "invoiceops/search_supplier_fallback": ("runtime.invoiceops_exception_tools", "invoiceops_search_supplier_fallback", "invoiceops_fallback_result"),
    "invoiceops/build_exception_action_plan": ("runtime.invoiceops_exception_tools", "invoiceops_build_exception_action_plan", "invoiceops_exception_action_plan"),
    "invoiceops/prepare_invoice_register_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_invoice_register_write", "invoiceops_prepared_write"),
    "invoiceops/prepare_match_register_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_match_register_write", "invoiceops_prepared_write"),
    "invoiceops/prepare_exception_register_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_exception_register_write", "invoiceops_prepared_write"),
    "invoiceops/prepare_ledger_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_ledger_write", "invoiceops_prepared_write"),
    "invoiceops/prepare_rollback_plan": ("runtime.invoiceops_write_tools", "invoiceops_prepare_rollback_plan", "invoiceops_rollback_plan"),
    "invoiceops/build_match_report": ("runtime.invoiceops_report_tools", "invoiceops_build_match_report", "invoiceops_report"),
    "invoiceops/build_exception_report": ("runtime.invoiceops_report_tools", "invoiceops_build_exception_report", "invoiceops_report"),
    "invoiceops/build_ledger_posting_summary": ("runtime.invoiceops_report_tools", "invoiceops_build_ledger_posting_summary", "invoiceops_report"),
    "invoiceops/build_rollback_summary": ("runtime.invoiceops_report_tools", "invoiceops_build_rollback_summary", "invoiceops_report"),
    "invoiceops/build_evidence_bundle": ("runtime.invoiceops_report_tools", "invoiceops_build_evidence_bundle", "invoiceops_report"),
}


def test_every_invoiceops_tool_is_registered() -> None:
    for key in EXPECTED_TOOLS:
        assert key in TOOL_REGISTRY, key


def test_every_registered_module_function_imports_successfully() -> None:
    for key, (module_name, function_name, _) in EXPECTED_TOOLS.items():
        module = importlib.import_module(module_name)
        assert hasattr(module, function_name), key


def test_invoiceops_registry_metadata_is_non_live() -> None:
    for key in EXPECTED_TOOLS:
        spec = TOOL_REGISTRY[key]
        assert spec["namespace"] == "invoiceops"
        assert spec["side_effect"] is False, key
        assert spec["requires_approval"] is False, key
        assert spec["allow_live"] is False, key
        assert spec["allow_live_side_effect"] is False, key
        assert spec["live_guardrail"] == "blocked", key
        assert spec["dry_run_executes"] is True, key


def test_prepared_write_tools_are_registered_as_non_live_prepared_writes() -> None:
    prepared_keys = {
        "invoiceops/prepare_invoice_register_write",
        "invoiceops/prepare_match_register_write",
        "invoiceops/prepare_exception_register_write",
        "invoiceops/prepare_ledger_write",
    }
    for key in prepared_keys:
        spec = TOOL_REGISTRY[key]
        assert spec["output_type"] == "invoiceops_prepared_write"
        assert spec["side_effect"] is False
        assert spec["allow_live_side_effect"] is False
        assert spec["allow_live"] is False


def test_no_invoiceops_tool_allows_live_side_effects() -> None:
    for key in EXPECTED_TOOLS:
        assert TOOL_REGISTRY[key]["allow_live_side_effect"] is False, key


def test_registry_output_types_match_expected_contracts() -> None:
    for key, (_, _, output_type) in EXPECTED_TOOLS.items():
        assert TOOL_REGISTRY[key]["output_type"] == output_type, key
