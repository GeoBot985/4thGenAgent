from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from runtime.invoiceops_contracts import validate_prepared_write_shape, validate_rollback_plan_shape
from runtime.invoiceops_write_tools import (
    invoiceops_prepare_exception_register_write,
    invoiceops_prepare_invoice_register_write,
    invoiceops_prepare_ledger_write,
    invoiceops_prepare_match_register_write,
    invoiceops_prepare_rollback_plan,
)
from runtime.tool_result_contract import validate_tool_result_contract

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "invoiceops" / "writes"


def _load(name: str):
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


_INVOICE = _load("invoice.json")
_MATCH_RESULT = _load("match_result.json")
_EXCEPTIONS = _load("exceptions.json")
_LEDGER_ROWS = _load("ledger_rows.json")


def _assert_tool_result(result: dict, expected_type: str) -> None:
    contract = validate_tool_result_contract(result, expected_type=expected_type)
    assert contract["ok"] is True, contract["errors"]


def test_invoice_register_prepared_write() -> None:
    result = invoiceops_prepare_invoice_register_write(_INVOICE)
    assert result["ok"] is True
    assert result["type"] == "invoiceops_prepared_write"
    prepared_write = result["data"]["prepared_write"]
    assert prepared_write["target"] == "InvoiceRegister"
    assert prepared_write["operation"] == "append"
    assert prepared_write["dry_run"] is True
    assert prepared_write["requires_approval"] is True
    assert prepared_write["rollback_plan"]["rollback_type"] == "delete_appended_rows"
    assert result["metadata"]["dry_run"] is True
    assert result["metadata"]["live_side_effect"] is False
    assert validate_prepared_write_shape(prepared_write)["ok"] is True
    _assert_tool_result(result, "invoiceops_prepared_write")


def test_match_register_prepared_write() -> None:
    result = invoiceops_prepare_match_register_write(_MATCH_RESULT)
    assert result["ok"] is True
    prepared_write = result["data"]["prepared_write"]
    assert prepared_write["target"] == "MatchRegister"
    assert prepared_write["rollback_plan"]["rollback_type"] == "delete_appended_rows"
    assert validate_prepared_write_shape(prepared_write)["ok"] is True
    _assert_tool_result(result, "invoiceops_prepared_write")


def test_exception_register_prepared_write() -> None:
    result = invoiceops_prepare_exception_register_write(_EXCEPTIONS)
    assert result["ok"] is True
    prepared_write = result["data"]["prepared_write"]
    assert prepared_write["target"] == "ExceptionRegister"
    assert len(prepared_write["rows"]) == len(_EXCEPTIONS)
    assert prepared_write["rollback_plan"]["rollback_type"] == "delete_appended_rows"
    assert validate_prepared_write_shape(prepared_write)["ok"] is True
    _assert_tool_result(result, "invoiceops_prepared_write")


def test_ledger_prepared_write() -> None:
    result = invoiceops_prepare_ledger_write(_LEDGER_ROWS)
    assert result["ok"] is True
    prepared_write = result["data"]["prepared_write"]
    assert prepared_write["target"] == "Ledger"
    assert prepared_write["rollback_plan"]["rollback_type"] == "mark_reversed"
    assert validate_prepared_write_shape(prepared_write)["ok"] is True
    _assert_tool_result(result, "invoiceops_prepared_write")


def test_every_prepared_write_has_rollback_plan() -> None:
    for fn, payload in (
        (invoiceops_prepare_invoice_register_write, _INVOICE),
        (invoiceops_prepare_match_register_write, _MATCH_RESULT),
        (invoiceops_prepare_exception_register_write, _EXCEPTIONS),
        (invoiceops_prepare_ledger_write, _LEDGER_ROWS),
    ):
        result = fn(payload)
        prepared_write = result["data"]["prepared_write"]
        assert "rollback_plan" in prepared_write
        assert validate_rollback_plan_shape(prepared_write["rollback_plan"])["ok"] is True


def test_ledger_rollback_uses_reversal_strategy() -> None:
    result = invoiceops_prepare_ledger_write(_LEDGER_ROWS)
    rollback_plan = result["data"]["prepared_write"]["rollback_plan"]
    assert rollback_plan["rollback_type"] == "mark_reversed"
    assert rollback_plan["steps"][0]["action"] == "mark_reversed"


def test_non_ledger_append_rollback_uses_delete_appended_rows() -> None:
    for fn, payload in (
        (invoiceops_prepare_invoice_register_write, _INVOICE),
        (invoiceops_prepare_match_register_write, _MATCH_RESULT),
        (invoiceops_prepare_exception_register_write, _EXCEPTIONS),
    ):
        result = fn(payload)
        rollback_plan = result["data"]["prepared_write"]["rollback_plan"]
        assert rollback_plan["rollback_type"] == "delete_appended_rows"
        assert rollback_plan["steps"][0]["action"] == "delete_appended_rows"


def test_rollback_plan_tool_builds_plan_from_prepared_write() -> None:
    prepared_write = invoiceops_prepare_invoice_register_write(_INVOICE)["data"]["prepared_write"]
    result = invoiceops_prepare_rollback_plan(prepared_write)
    assert result["ok"] is True
    assert result["type"] == "invoiceops_rollback_plan"
    assert result["data"]["rollback_plan"] == prepared_write["rollback_plan"]
    assert validate_rollback_plan_shape(result["data"]["rollback_plan"])["ok"] is True
    _assert_tool_result(result, "invoiceops_rollback_plan")


def test_invalid_input_fails_safely() -> None:
    cases = [
        (invoiceops_prepare_invoice_register_write, {}, "INVALID_INVOICE_FOR_WRITE"),
        (invoiceops_prepare_match_register_write, {}, "INVALID_MATCH_RESULT_FOR_WRITE"),
        (invoiceops_prepare_exception_register_write, [{"exception_id": "bad"}], "INVALID_EXCEPTION_FOR_WRITE"),
        (invoiceops_prepare_ledger_write, [{"ledger_entry_id": "bad"}], "INVALID_LEDGER_ROW_FOR_WRITE"),
        (invoiceops_prepare_rollback_plan, {}, "ROLLBACK_PLAN_REQUIRED"),
    ]
    for fn, payload, expected_error in cases:
        result = fn(payload)  # type: ignore[arg-type]
        assert result["ok"] is False
        assert result["error"] == expected_error


def test_all_outputs_are_toolresult_compatible() -> None:
    results = [
        invoiceops_prepare_invoice_register_write(_INVOICE),
        invoiceops_prepare_match_register_write(_MATCH_RESULT),
        invoiceops_prepare_exception_register_write(_EXCEPTIONS),
        invoiceops_prepare_ledger_write(_LEDGER_ROWS),
        invoiceops_prepare_rollback_plan(invoiceops_prepare_invoice_register_write(_INVOICE)["data"]["prepared_write"]),
    ]
    for result in results:
        _assert_tool_result(result, result["type"])


def test_no_live_write_helper_is_called() -> None:
    with patch("runtime.google_sheet_tools.sheet_write_rows", side_effect=AssertionError("live sheet_write_rows must not be called")), patch(
        "runtime.google_sheet_tools.write_sheet_entries",
        side_effect=AssertionError("live write_sheet_entries must not be called"),
    ):
        invoiceops_prepare_invoice_register_write(_INVOICE)
        invoiceops_prepare_match_register_write(_MATCH_RESULT)
        invoiceops_prepare_exception_register_write(_EXCEPTIONS)
        invoiceops_prepare_ledger_write(_LEDGER_ROWS)
        invoiceops_prepare_rollback_plan(invoiceops_prepare_invoice_register_write(_INVOICE)["data"]["prepared_write"])

