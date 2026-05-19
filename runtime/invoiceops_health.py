from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from .invoiceops_contracts import (
    validate_invoice_shape,
    validate_match_result_shape,
    validate_prepared_write_shape,
    validate_report_shape,
    validate_rollback_plan_shape,
)
from .invoiceops_exception_tools import invoiceops_build_exception_action_plan, invoiceops_classify_exceptions
from .invoiceops_extraction_tools import invoiceops_extract_invoice_fields, invoiceops_validate_invoice_fields
from .invoiceops_matching_tools import invoiceops_match_three_way
from .invoiceops_reader_tools import invoiceops_read_invoice_file
from .invoiceops_report_tools import (
    invoiceops_build_evidence_bundle,
    invoiceops_build_exception_report,
    invoiceops_build_ledger_posting_summary,
    invoiceops_build_match_report,
    invoiceops_build_rollback_summary,
)
from .invoiceops_sheet_tools import (
    invoiceops_read_exception_register,
    invoiceops_read_invoice_register,
    invoiceops_read_ledger,
    invoiceops_read_po_register,
    invoiceops_read_receipt_register,
    invoiceops_read_supplier_master,
)
from .invoiceops_write_tools import (
    invoiceops_prepare_exception_register_write,
    invoiceops_prepare_invoice_register_write,
    invoiceops_prepare_ledger_write,
    invoiceops_prepare_match_register_write,
    invoiceops_prepare_rollback_plan,
)
from .taskframe import utc_now
from .tool_registry import TOOL_REGISTRY
from .tool_result_contract import validate_tool_result_contract


TOOL_ID = "invoiceops"
FIXTURE_BASE = Path("tests") / "fixtures" / "invoiceops"

_SAMPLE_INVOICE_TEXT = FIXTURE_BASE / "sample_invoice.txt"
_SAMPLE_MATCH = FIXTURE_BASE / "matching" / "happy_path.json"
_SAMPLE_REPORT_MATCH = FIXTURE_BASE / "reports" / "happy_match.json"
_SAMPLE_REPORT_BLOCKED = FIXTURE_BASE / "reports" / "blocked_match.json"
_SAMPLE_REPORT_EXCEPTIONS = FIXTURE_BASE / "reports" / "exceptions_multi.json"
_SAMPLE_REPORT_LEDGER = FIXTURE_BASE / "reports" / "ledger_summary.json"
_SAMPLE_REPORT_ROLLBACK = FIXTURE_BASE / "reports" / "rollback_mixed.json"
_SAMPLE_REPORT_BUNDLE = FIXTURE_BASE / "reports" / "evidence_bundle.json"
_SAMPLE_WRITE = FIXTURE_BASE / "writes" / "invoice.json"
_SAMPLE_WRITE_MATCH = FIXTURE_BASE / "writes" / "match_result.json"
_SAMPLE_WRITE_EXCEPTIONS = FIXTURE_BASE / "writes" / "exceptions.json"
_SAMPLE_WRITE_LEDGER = FIXTURE_BASE / "writes" / "ledger_rows.json"
_SHEET_FIXTURES = {
    "supplier_master": FIXTURE_BASE / "sheets" / "supplier_master.json",
    "po_register": FIXTURE_BASE / "sheets" / "po_register.json",
    "receipt_register": FIXTURE_BASE / "sheets" / "goods_receipts.json",
    "invoice_register": FIXTURE_BASE / "sheets" / "invoice_register.json",
    "ledger": FIXTURE_BASE / "sheets" / "ledger.json",
    "exception_register": FIXTURE_BASE / "sheets" / "exception_register.json",
}
_TOOL_IMPORTS = {
    "invoiceops/read_invoice_file": ("runtime.invoiceops_reader_tools", "invoiceops_read_invoice_file"),
    "invoiceops/extract_invoice_fields": ("runtime.invoiceops_extraction_tools", "invoiceops_extract_invoice_fields"),
    "invoiceops/validate_invoice_fields": ("runtime.invoiceops_extraction_tools", "invoiceops_validate_invoice_fields"),
    "invoiceops/read_supplier_master": ("runtime.invoiceops_sheet_tools", "invoiceops_read_supplier_master"),
    "invoiceops/read_po_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_po_register"),
    "invoiceops/read_receipt_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_receipt_register"),
    "invoiceops/read_invoice_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_invoice_register"),
    "invoiceops/read_ledger": ("runtime.invoiceops_sheet_tools", "invoiceops_read_ledger"),
    "invoiceops/read_exception_register": ("runtime.invoiceops_sheet_tools", "invoiceops_read_exception_register"),
    "invoiceops/check_duplicate_invoice": ("runtime.invoiceops_matching_tools", "invoiceops_check_duplicate_invoice"),
    "invoiceops/lookup_purchase_order": ("runtime.invoiceops_matching_tools", "invoiceops_lookup_purchase_order"),
    "invoiceops/lookup_goods_receipt": ("runtime.invoiceops_matching_tools", "invoiceops_lookup_goods_receipt"),
    "invoiceops/check_totals": ("runtime.invoiceops_matching_tools", "invoiceops_check_totals"),
    "invoiceops/check_tax": ("runtime.invoiceops_matching_tools", "invoiceops_check_tax"),
    "invoiceops/match_three_way": ("runtime.invoiceops_matching_tools", "invoiceops_match_three_way"),
    "invoiceops/classify_exceptions": ("runtime.invoiceops_exception_tools", "invoiceops_classify_exceptions"),
    "invoiceops/search_po_fallback": ("runtime.invoiceops_exception_tools", "invoiceops_search_po_fallback"),
    "invoiceops/search_receipt_fallback": ("runtime.invoiceops_exception_tools", "invoiceops_search_receipt_fallback"),
    "invoiceops/search_supplier_fallback": ("runtime.invoiceops_exception_tools", "invoiceops_search_supplier_fallback"),
    "invoiceops/build_exception_action_plan": ("runtime.invoiceops_exception_tools", "invoiceops_build_exception_action_plan"),
    "invoiceops/prepare_invoice_register_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_invoice_register_write"),
    "invoiceops/prepare_match_register_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_match_register_write"),
    "invoiceops/prepare_exception_register_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_exception_register_write"),
    "invoiceops/prepare_ledger_write": ("runtime.invoiceops_write_tools", "invoiceops_prepare_ledger_write"),
    "invoiceops/prepare_rollback_plan": ("runtime.invoiceops_write_tools", "invoiceops_prepare_rollback_plan"),
    "invoiceops/build_match_report": ("runtime.invoiceops_report_tools", "invoiceops_build_match_report"),
    "invoiceops/build_exception_report": ("runtime.invoiceops_report_tools", "invoiceops_build_exception_report"),
    "invoiceops/build_ledger_posting_summary": ("runtime.invoiceops_report_tools", "invoiceops_build_ledger_posting_summary"),
    "invoiceops/build_rollback_summary": ("runtime.invoiceops_report_tools", "invoiceops_build_rollback_summary"),
    "invoiceops/build_evidence_bundle": ("runtime.invoiceops_report_tools", "invoiceops_build_evidence_bundle"),
}


def invoiceops_contracts_health() -> dict[str, Any]:
    checked_at = utc_now()
    details: dict[str, Any] = {"fixture_base": str(FIXTURE_BASE)}
    issues: list[str] = []

    match_payload = _load_json(_SAMPLE_REPORT_MATCH)
    invoice = match_payload.get("invoice", {})
    match_result = match_payload.get("match_result", {})
    prepared_write = invoiceops_prepare_invoice_register_write(_load_json(_SAMPLE_WRITE)).get("data", {}).get("prepared_write", {})
    report = invoiceops_build_match_report(invoice, match_result).get("data", {}).get("report", {})

    validators = {
        "invoice": validate_invoice_shape(invoice),
        "match_result": validate_match_result_shape(match_result),
        "prepared_write": validate_prepared_write_shape(prepared_write),
        "rollback_plan": validate_rollback_plan_shape(prepared_write.get("rollback_plan", {})),
        "report": validate_report_shape(report),
    }
    details["validators"] = validators

    for name, outcome in validators.items():
        if not outcome.get("ok", False):
            issues.extend(f"{name}: {err}" for err in outcome.get("errors", []))

    if not _all_required_fixture_files_exist():
        issues.append("One or more InvoiceOps fixture files are missing.")

    ok = not issues
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="InvoiceOps contract validators passed against fixture data." if ok else "InvoiceOps contract validators failed.",
        details={**details, "issues": issues},
        checked_at=checked_at,
    )


def invoiceops_reader_health() -> dict[str, Any]:
    checked_at = utc_now()
    details: dict[str, Any] = {"sample_invoice_text": str(_SAMPLE_INVOICE_TEXT)}
    if not _SAMPLE_INVOICE_TEXT.is_file():
        return _health_result(
            ok=False,
            status="warning",
            severity="warning",
            message="Sample invoice text fixture is missing.",
            details=details,
            checked_at=checked_at,
        )

    result = invoiceops_read_invoice_file(str(_SAMPLE_INVOICE_TEXT))
    contract = validate_tool_result_contract(result, expected_type="invoiceops_raw_invoice_text")
    details["tool_result_contract"] = contract
    details["read_result"] = result
    ok = bool(result.get("ok", False)) and contract["ok"]
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="Invoice file reader works in fixture mode." if ok else str(result.get("error", "Invoice reader failed.")),
        details=details,
        checked_at=checked_at,
    )


def invoiceops_extraction_health() -> dict[str, Any]:
    checked_at = utc_now()
    details: dict[str, Any] = {"sample_invoice_text": str(_SAMPLE_INVOICE_TEXT)}
    if not _SAMPLE_INVOICE_TEXT.is_file():
        return _health_result(
            ok=False,
            status="warning",
            severity="warning",
            message="Sample invoice text fixture is missing.",
            details=details,
            checked_at=checked_at,
        )

    read_result = invoiceops_read_invoice_file(str(_SAMPLE_INVOICE_TEXT))
    extract_result = invoiceops_extract_invoice_fields(str(read_result.get("data", {}).get("text", "")), source_ref=str(_SAMPLE_INVOICE_TEXT))
    validate_result = invoiceops_validate_invoice_fields(extract_result.get("data", {}).get("invoice", {}))

    details["read_result"] = read_result
    details["extract_result"] = extract_result
    details["validate_result"] = validate_result
    ok = bool(read_result.get("ok", False)) and bool(extract_result.get("ok", False)) and bool(validate_result.get("ok", False))
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="Invoice extraction and validation work in fixture mode." if ok else "Invoice extraction health check failed.",
        details=details,
        checked_at=checked_at,
    )


def invoiceops_sheet_fixture_health() -> dict[str, Any]:
    checked_at = utc_now()
    details: dict[str, Any] = {"fixtures": {name: str(path) for name, path in _SHEET_FIXTURES.items()}}
    missing = [name for name, path in _SHEET_FIXTURES.items() if not path.is_file()]
    if missing:
        return _health_result(
            ok=False,
            status="warning",
            severity="warning",
            message="One or more sheet fixtures are missing.",
            details={**details, "missing": missing},
            checked_at=checked_at,
        )

    readers = {
        "supplier_master": invoiceops_read_supplier_master,
        "po_register": invoiceops_read_po_register,
        "receipt_register": invoiceops_read_receipt_register,
        "invoice_register": invoiceops_read_invoice_register,
        "ledger": invoiceops_read_ledger,
        "exception_register": invoiceops_read_exception_register,
    }
    results: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for name, reader in readers.items():
        result = reader(fixture_mode=True, _fixture_dir=str(FIXTURE_BASE / "sheets"))
        results[name] = result
        if not result.get("ok", False):
            issues.append(f"{name}: {result.get('error', 'SHEET_READ_FAILED')}")
    details["results"] = results

    ok = not issues
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="Invoice sheet fixtures are readable in fixture mode." if ok else "Invoice sheet fixture health check failed.",
        details={**details, "issues": issues},
        checked_at=checked_at,
    )


def invoiceops_matching_health() -> dict[str, Any]:
    checked_at = utc_now()
    payload = _load_json(_SAMPLE_MATCH)
    invoice = payload.get("invoice", {})
    purchase_order = payload.get("purchase_order", {})
    goods_receipt = payload.get("goods_receipt", {})
    invoice_register = payload.get("invoice_register", [])
    result = invoiceops_match_three_way(invoice, purchase_order, goods_receipt, invoice_register)
    contract = validate_tool_result_contract(result, expected_type="invoiceops_match_result")
    match_contract = validate_match_result_shape(result.get("data", {}).get("match_result", {}))
    details = {
        "fixture": str(_SAMPLE_MATCH),
        "tool_result_contract": contract,
        "match_result_contract": match_contract,
        "result": result,
    }
    ok = bool(result.get("ok", False)) and contract["ok"] and match_contract.get("ok", False)
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="Invoice matching works in fixture mode." if ok else "Invoice matching health check failed.",
        details=details,
        checked_at=checked_at,
    )


def invoiceops_exception_health() -> dict[str, Any]:
    checked_at = utc_now()
    payload = _load_json(_SAMPLE_REPORT_EXCEPTIONS)
    invoice = payload.get("invoice", {})
    exceptions = payload.get("exceptions", [])
    action_plan_seed = payload.get("action_plan", {})
    classify_result = invoiceops_classify_exceptions({"data": {"match_result": {"exceptions": exceptions}}}, invoice)
    action_plan_result = invoiceops_build_exception_action_plan(invoice, exceptions, fallback_results=action_plan_seed.get("fallback_results"))
    details = {
        "fixture": str(_SAMPLE_REPORT_EXCEPTIONS),
        "classify_result": classify_result,
        "action_plan_result": action_plan_result,
    }
    classify_contract = validate_tool_result_contract(classify_result, expected_type="invoiceops_exception_classification")
    action_plan_contract = validate_tool_result_contract(action_plan_result, expected_type="invoiceops_exception_action_plan")
    ok = bool(classify_result.get("ok", False)) and bool(action_plan_result.get("ok", False)) and classify_contract["ok"] and action_plan_contract["ok"]
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="Invoice exception classification works in fixture mode." if ok else "Invoice exception health check failed.",
        details=details,
        checked_at=checked_at,
    )


def invoiceops_prepared_write_health() -> dict[str, Any]:
    checked_at = utc_now()
    invoice = _load_json(_SAMPLE_WRITE)
    match_result = _load_json(_SAMPLE_WRITE_MATCH)
    exceptions = _load_json(_SAMPLE_WRITE_EXCEPTIONS)
    ledger_rows = _load_json(_SAMPLE_WRITE_LEDGER)
    results = {
        "invoice_register": invoiceops_prepare_invoice_register_write(invoice),
        "match_register": invoiceops_prepare_match_register_write(match_result),
        "exception_register": invoiceops_prepare_exception_register_write(exceptions),
        "ledger": invoiceops_prepare_ledger_write(ledger_rows),
    }
    rollback_plan_result = invoiceops_prepare_rollback_plan(results["invoice_register"].get("data", {}).get("prepared_write", {}))
    details = {"results": results, "rollback_plan_result": rollback_plan_result}
    issues: list[str] = []
    for name, result in results.items():
        contract = validate_tool_result_contract(result, expected_type="invoiceops_prepared_write")
        if not result.get("ok", False) or not contract["ok"]:
            issues.append(f"{name}: prepared write invalid")
        prepared_write = result.get("data", {}).get("prepared_write", {})
        if not validate_prepared_write_shape(prepared_write).get("ok", False):
            issues.append(f"{name}: prepared write shape invalid")
        if not validate_rollback_plan_shape(prepared_write.get("rollback_plan", {})).get("ok", False):
            issues.append(f"{name}: rollback plan invalid")
    if not validate_tool_result_contract(rollback_plan_result, expected_type="invoiceops_rollback_plan")["ok"]:
        issues.append("rollback_plan_result: tool result contract invalid")
    if not rollback_plan_result.get("ok", False):
        issues.append("rollback_plan_result: failed")

    ok = not issues
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="Prepared write staging works and includes rollback plans." if ok else "Prepared write health check failed.",
        details={**details, "issues": issues},
        checked_at=checked_at,
    )


def invoiceops_reporting_health() -> dict[str, Any]:
    checked_at = utc_now()
    happy = _load_json(_SAMPLE_REPORT_MATCH)
    blocked = _load_json(_SAMPLE_REPORT_BLOCKED)
    exceptions = _load_json(_SAMPLE_REPORT_EXCEPTIONS)
    ledger = _load_json(_SAMPLE_REPORT_LEDGER)
    rollback = _load_json(_SAMPLE_REPORT_ROLLBACK)
    bundle = _load_json(_SAMPLE_REPORT_BUNDLE)

    results = {
        "match": invoiceops_build_match_report(happy.get("invoice", {}), happy.get("match_result", {})),
        "blocked_match": invoiceops_build_match_report(blocked.get("invoice", {}), blocked.get("match_result", {})),
        "exception": invoiceops_build_exception_report(exceptions.get("invoice", {}), exceptions.get("exceptions", []), exceptions.get("action_plan")),
        "ledger": invoiceops_build_ledger_posting_summary(ledger.get("invoice", {}), ledger.get("ledger_rows", [])),
        "rollback": invoiceops_build_rollback_summary(rollback.get("prepared_writes", [])),
        "bundle": invoiceops_build_evidence_bundle(bundle.get("invoice", {}), bundle.get("match_result"), bundle.get("exceptions"), bundle.get("prepared_writes")),
    }
    details = {"results": results}
    issues: list[str] = []
    for name, result in results.items():
        contract = validate_tool_result_contract(result, expected_type="invoiceops_report")
        if not result.get("ok", False) or not contract["ok"]:
            issues.append(f"{name}: report invalid")
        report = result.get("data", {}).get("report", {})
        if not validate_report_shape(report).get("ok", False):
            issues.append(f"{name}: report shape invalid")

    ok = not issues
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="InvoiceOps reporting tools build deterministic reports in fixture mode." if ok else "InvoiceOps reporting health check failed.",
        details={**details, "issues": issues},
        checked_at=checked_at,
    )


def invoiceops_registry_health() -> dict[str, Any]:
    checked_at = utc_now()
    checks = {
        "contracts": invoiceops_contracts_health(),
        "reader": invoiceops_reader_health(),
        "extraction": invoiceops_extraction_health(),
        "sheet_fixtures": invoiceops_sheet_fixture_health(),
        "matching": invoiceops_matching_health(),
        "exception": invoiceops_exception_health(),
        "prepared_write": invoiceops_prepared_write_health(),
        "reporting": invoiceops_reporting_health(),
        "registry": _registry_metadata_health(),
    }

    registry_result = checks["registry"]
    failed_sections = [name for name, result in checks.items() if not result.get("ok", False)]
    issues: list[str] = []
    if not registry_result.get("ok", False):
        issues.extend(registry_result.get("details", {}).get("issues", []))
    if failed_sections:
        issues.append(f"Failed health sections: {failed_sections}")

    ok = not issues
    status = "healthy" if ok else "failed"
    severity = "info" if ok else "error"
    if not ok and not failed_sections:
        status = "warning"
        severity = "warning"

    return _health_result(
        ok=ok,
        status=status,
        severity=severity,
        message="InvoiceOps registry and fixture health checks passed." if ok else "InvoiceOps registry health check found issues.",
        details={
            "checks": checks,
            "failed_sections": failed_sections,
            "issues": issues,
            "fixture_base": str(FIXTURE_BASE),
        },
        checked_at=checked_at,
    )


def _all_required_fixture_files_exist() -> bool:
    paths = [
        _SAMPLE_INVOICE_TEXT,
        _SAMPLE_MATCH,
        _SAMPLE_REPORT_MATCH,
        _SAMPLE_REPORT_BLOCKED,
        _SAMPLE_REPORT_EXCEPTIONS,
        _SAMPLE_REPORT_LEDGER,
        _SAMPLE_REPORT_ROLLBACK,
        _SAMPLE_REPORT_BUNDLE,
        _SAMPLE_WRITE,
        _SAMPLE_WRITE_MATCH,
        _SAMPLE_WRITE_EXCEPTIONS,
        _SAMPLE_WRITE_LEDGER,
    ]
    paths.extend(_SHEET_FIXTURES.values())
    return all(path.is_file() for path in paths)


def _registry_metadata_health() -> dict[str, Any]:
    checked_at = utc_now()
    missing_tools: list[str] = []
    import_errors: dict[str, str] = {}
    metadata_violations: list[str] = []
    output_type_mismatches: list[str] = []

    for tool_key, (module_name, function_name) in _TOOL_IMPORTS.items():
        spec = TOOL_REGISTRY.get(tool_key)
        if not spec:
            missing_tools.append(tool_key)
            continue
        if spec.get("allow_live") is not False or spec.get("allow_live_side_effect") is not False or spec.get("side_effect") is not False or spec.get("requires_approval") is not False:
            metadata_violations.append(tool_key)
        if spec.get("live_guardrail") != "blocked":
            metadata_violations.append(tool_key)
        if spec.get("dry_run_executes") is not True:
            metadata_violations.append(tool_key)
        try:
            module = importlib.import_module(module_name)
            getattr(module, function_name)
        except Exception as exc:
            import_errors[tool_key] = str(exc)
        if tool_key.startswith("invoiceops/prepare_") and tool_key != "invoiceops/prepare_rollback_plan" and spec.get("output_type") != "invoiceops_prepared_write":
            output_type_mismatches.append(tool_key)
        if tool_key == "invoiceops/prepare_rollback_plan" and spec.get("output_type") != "invoiceops_rollback_plan":
            output_type_mismatches.append(tool_key)

    issues: list[str] = []
    if missing_tools:
        issues.append(f"Missing registered tools: {missing_tools}")
    if import_errors:
        issues.append(f"Import failures: {import_errors}")
    if metadata_violations:
        issues.append(f"Registry metadata violations: {metadata_violations}")
    if output_type_mismatches:
        issues.append(f"Registry output type mismatches: {output_type_mismatches}")

    ok = not issues
    return _health_result(
        ok=ok,
        status="healthy" if ok else "failed",
        severity="info" if ok else "error",
        message="InvoiceOps registry metadata is complete and importable." if ok else "InvoiceOps registry metadata check failed.",
        details={
            "missing_tools": missing_tools,
            "import_errors": import_errors,
            "metadata_violations": metadata_violations,
            "output_type_mismatches": output_type_mismatches,
            "issues": issues,
        },
        checked_at=checked_at,
    )


def _load_json(path: Path) -> Any:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data


def _extract_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if "report" in payload and isinstance(payload["report"], dict):
        return payload["report"]
    if "data" in payload and isinstance(payload["data"], dict) and isinstance(payload["data"].get("report"), dict):
        return payload["data"]["report"]
    return {}


def _health_result(
    *,
    ok: bool,
    status: str,
    severity: str,
    message: str,
    details: dict[str, Any],
    checked_at: str | None = None,
) -> dict[str, Any]:
    return {
        "tool_id": TOOL_ID,
        "ok": ok,
        "status": status,
        "severity": severity,
        "message": message,
        "details": details,
        "checked_at": checked_at or utc_now(),
    }
