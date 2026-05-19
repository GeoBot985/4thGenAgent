from __future__ import annotations

from collections import Counter
from typing import Any

from .invoiceops_contracts import (
    validate_exception_shape,
    validate_invoice_shape,
    validate_ledger_row_shape,
    validate_match_result_shape,
    validate_prepared_write_shape,
    validate_report_shape,
    validate_rollback_plan_shape,
)
from .tool_result_contract import build_tool_evidence

_RESULT_TYPE = "invoiceops_report"

_TOOL_KEYS = {
    "match_report": "invoiceops/build_match_report",
    "exception_report": "invoiceops/build_exception_report",
    "ledger_summary": "invoiceops/build_ledger_posting_summary",
    "rollback_summary": "invoiceops/build_rollback_summary",
    "evidence_bundle": "invoiceops/build_evidence_bundle",
}

_INVALID_CODES = {
    "match_report": "INVALID_MATCH_RESULT_FOR_REPORT",
    "exception_report": "INVALID_EXCEPTION_FOR_REPORT",
    "ledger_summary": "INVALID_LEDGER_ROW_FOR_REPORT",
    "rollback_summary": "INVALID_PREPARED_WRITE_FOR_REPORT",
    "evidence_bundle": "INVALID_INVOICE_FOR_REPORT",
}


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def invoiceops_build_match_report(invoice: dict, match_result: dict) -> dict:
    inv = _unwrap_invoice(invoice)
    mr = _unwrap_match_result(match_result)
    if not isinstance(inv, dict) or not validate_invoice_shape(inv)["ok"]:
        return _failed_report("match_report", "INVALID_INVOICE_FOR_REPORT", "Invoice input failed validation.")
    if not isinstance(mr, dict) or not validate_match_result_shape(mr)["ok"]:
        return _failed_report("match_report", "INVALID_MATCH_RESULT_FOR_REPORT", "Match result input failed validation.")

    checks = list(mr.get("checks", [])) if isinstance(mr.get("checks", []), list) else []
    check_summary = _count_check_statuses(checks)
    exceptions = list(mr.get("exceptions", [])) if isinstance(mr.get("exceptions", []), list) else []
    report = _base_report(
        inv=inv,
        match_status=str(mr.get("match_status", "exception")),
        summary=_match_summary(inv, mr, check_summary),
        checks=checks,
        exceptions=exceptions,
        prepared_writes=[],
        rollback_plans=[],
        extra={
            "invoice_number": str(inv.get("invoice_number", "")),
            "supplier_name": str(inv.get("supplier_name", "")),
            "po_number": str(inv.get("po_number", "")),
            "check_summary": check_summary,
            "ledger_posting_allowed": bool(mr.get("ledger_posting_allowed", False)),
            "prepared_write_allowed": bool(mr.get("prepared_write_allowed", False)),
            "prepared_write_decision": _decision_from_allowed(bool(mr.get("prepared_write_allowed", False))),
            "match_evidence": _match_evidence_section(mr),
        },
    )
    evidence = _bundle_evidence(
        tool_key="match_report",
        invoice=inv,
        sections=[
            _invoice_evidence(inv),
            _extraction_evidence(inv),
            report["match_evidence"],
        ],
        input_refs=[str(inv.get("invoice_number", "")), str(inv.get("po_number", ""))],
        extra={"match_status": report["match_status"]},
    )
    report["evidence"] = evidence["sections"]
    return _report_result("match_report", report, evidence["evidence"])


def invoiceops_build_exception_report(
    invoice: dict,
    exceptions: list[dict],
    action_plan: dict | None = None,
) -> dict:
    inv = _unwrap_invoice(invoice)
    excs = _unwrap_list(exceptions)
    plan = _unwrap_dict(action_plan) if action_plan is not None else None
    if not isinstance(inv, dict) or not validate_invoice_shape(inv)["ok"]:
        return _failed_report("exception_report", "INVALID_INVOICE_FOR_REPORT", "Invoice input failed validation.")
    if excs is None:
        return _failed_report("exception_report", "INVALID_EXCEPTION_FOR_REPORT", "Exceptions input must be a list.")
    validated: list[dict] = []
    for idx, exc in enumerate(excs):
        if not isinstance(exc, dict) or not validate_exception_shape(exc)["ok"]:
            return _failed_report("exception_report", "INVALID_EXCEPTION_FOR_REPORT", f"exceptions[{idx}] failed validation.")
        validated.append(dict(exc))

    sev_summary = Counter(str(exc.get("severity", "low")) for exc in validated)
    blocking = any(bool(exc.get("blocking", False)) for exc in validated)
    report = _base_report(
        inv=inv,
        match_status="blocked" if blocking else "exception",
        summary=_exception_summary(inv, validated, plan),
        checks=[],
        exceptions=validated,
        prepared_writes=[],
        rollback_plans=[],
        extra={
            "invoice_number": str(inv.get("invoice_number", "")),
            "supplier_name": str(inv.get("supplier_name", "")),
            "po_number": str(inv.get("po_number", "")),
            "exception_count": len(validated),
            "exception_types": _unique_values([str(exc.get("exception_type", "")) for exc in validated]),
            "severity_summary": dict(sev_summary),
            "blocking_status": blocking,
            "operator_review_required": True,
            "recommended_action": _recommended_exception_action(validated, plan),
            "action_plan": dict(plan or {}),
        },
    )
    evidence = _bundle_evidence(
        tool_key="exception_report",
        invoice=inv,
        sections=[
            _invoice_evidence(inv),
            _extraction_evidence(inv),
            _exception_evidence_section(validated),
            _action_plan_evidence(plan),
        ],
        input_refs=[str(inv.get("invoice_number", "")), str(inv.get("po_number", ""))],
        extra={"exception_count": len(validated), "blocking": blocking},
    )
    report["evidence"] = evidence["sections"]
    return _report_result("exception_report", report, evidence["evidence"])


def invoiceops_build_ledger_posting_summary(invoice: dict, ledger_rows: list[dict]) -> dict:
    inv = _unwrap_invoice(invoice)
    rows = _unwrap_list(ledger_rows)
    if not isinstance(inv, dict) or not validate_invoice_shape(inv)["ok"]:
        return _failed_report("ledger_summary", "INVALID_INVOICE_FOR_REPORT", "Invoice input failed validation.")
    if rows is None:
        return _failed_report("ledger_summary", "INVALID_LEDGER_ROW_FOR_REPORT", "Ledger rows input must be a list.")

    validated: list[dict] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict) or not validate_ledger_row_shape(row)["ok"]:
            return _failed_report("ledger_summary", "INVALID_LEDGER_ROW_FOR_REPORT", f"ledger_rows[{idx}] failed validation.")
        validated.append(dict(row))

    primary = validated[0] if validated else {}
    posting_allowed = bool(validated) and all(str(row.get("status", "")).strip() == "prepared" for row in validated)
    posting_status = "ready_for_posting" if posting_allowed else "not_ready"
    report = _base_report(
        inv=inv,
        match_status="matched" if posting_allowed else "exception",
        summary=_ledger_summary(inv, validated, posting_allowed),
        checks=[],
        exceptions=[],
        prepared_writes=[],
        rollback_plans=[],
        extra={
            "invoice_number": str(inv.get("invoice_number", "")),
            "supplier_name": str(inv.get("supplier_name", "")),
            "po_number": str(inv.get("po_number", "")),
            "ledger_row_count": len(validated),
            "debit_account": str(primary.get("debit_account", "")),
            "credit_account": str(primary.get("credit_account", "")),
            "amount": primary.get("amount", 0),
            "currency": str(primary.get("currency", str(inv.get("currency", "")))),
            "posting_status": posting_status,
            "posting_allowed": posting_allowed,
            "ledger_rows": validated,
        },
    )
    evidence = _bundle_evidence(
        tool_key="ledger_summary",
        invoice=inv,
        sections=[
            _invoice_evidence(inv),
            _extraction_evidence(inv),
            _ledger_evidence_section(validated),
        ],
        input_refs=[str(inv.get("invoice_number", "")), str(inv.get("po_number", ""))],
        extra={"ledger_row_count": len(validated), "posting_allowed": posting_allowed},
    )
    report["evidence"] = evidence["sections"]
    return _report_result("ledger_summary", report, evidence["evidence"])


def invoiceops_build_rollback_summary(prepared_writes: list[dict]) -> dict:
    writes = _unwrap_list(prepared_writes)
    if writes is None:
        return _failed_report("rollback_summary", "INVALID_PREPARED_WRITE_FOR_REPORT", "Prepared writes input must be a list.")

    validated: list[dict] = []
    rollback_plans: list[dict] = []
    warnings: list[str] = []
    for idx, item in enumerate(writes):
        prepared_write = _unwrap_prepared_write(item)
        if not isinstance(prepared_write, dict) or not validate_prepared_write_shape(prepared_write)["ok"]:
            return _failed_report("rollback_summary", "INVALID_PREPARED_WRITE_FOR_REPORT", f"prepared_writes[{idx}] failed validation.")
        validated.append(dict(prepared_write))
        rollback_plan = dict(prepared_write.get("rollback_plan", {}))
        if rollback_plan:
            rollback_plans.append(rollback_plan)
            if rollback_plan.get("rollback_type") == "manual_review_required" or not rollback_plan.get("safe_to_auto_prepare", False):
                warnings.append(f"{prepared_write.get('target', '')} requires manual review.")
        else:
            warnings.append(f"{prepared_write.get('target', '')} is missing rollback metadata.")

    targets = _unique_values([str(item.get("target", "")) for item in validated])
    invoice_ref = _first_non_empty(
        [
            str(item.get("invoice_id", "")) for item in validated
        ]
        + [
            str(row.get("invoice_id", "") or row.get("invoice_number", "") or row.get("source_ref", ""))
            for item in validated
            for row in (item.get("rows", []) if isinstance(item.get("rows", []), list) else [])
            if isinstance(row, dict)
        ]
        + [str(item.get("prepared_write_id", "")) for item in validated]
    ) or "ROLLBACK"
    report = _base_report(
        inv={"invoice_id": invoice_ref},
        match_status="exception" if warnings else "matched",
        summary=_rollback_summary(validated, rollback_plans, warnings),
        checks=[],
        exceptions=[],
        prepared_writes=validated,
        rollback_plans=rollback_plans,
        extra={
            "prepared_write_count": len(validated),
            "target_registers": targets,
            "rollback_type_by_write": [
                {
                    "prepared_write_id": str(item.get("prepared_write_id", "")),
                    "target": str(item.get("target", "")),
                    "rollback_type": str((item.get("rollback_plan") or {}).get("rollback_type", "")),
                }
                for item in validated
            ],
            "manual_review_required": any(
                (item.get("rollback_plan") or {}).get("rollback_type") == "manual_review_required"
                or not (item.get("rollback_plan") or {}).get("safe_to_auto_prepare", False)
                for item in validated
            ),
            "unsafe_rollback_warnings": warnings,
        },
    )
    evidence = _bundle_evidence(
        tool_key="rollback_summary",
        invoice=validated[0] if validated else {"invoice_id": ""},
        sections=[
            _prepared_write_evidence_section(validated),
            _rollback_evidence_section(rollback_plans),
        ],
        input_refs=[str(item.get("prepared_write_id", "")) for item in validated],
        extra={"prepared_write_count": len(validated), "warning_count": len(warnings)},
    )
    report["evidence"] = evidence["sections"]
    return _report_result("rollback_summary", report, evidence["evidence"])


def invoiceops_build_evidence_bundle(
    invoice: dict,
    match_result: dict | None = None,
    exceptions: list[dict] | None = None,
    prepared_writes: list[dict] | None = None,
) -> dict:
    inv = _unwrap_invoice(invoice)
    mr = _unwrap_match_result(match_result) if match_result is not None else None
    excs = _unwrap_list(exceptions) if exceptions is not None else []
    writes = _unwrap_list(prepared_writes) if prepared_writes is not None else []
    if not isinstance(inv, dict) or not validate_invoice_shape(inv)["ok"]:
        return _failed_report("evidence_bundle", "INVALID_INVOICE_FOR_REPORT", "Invoice input failed validation.")
    if match_result is not None and (not isinstance(mr, dict) or not validate_match_result_shape(mr)["ok"]):
        return _failed_report("evidence_bundle", "INVALID_MATCH_RESULT_FOR_REPORT", "Match result input failed validation.")
    if exceptions is not None:
        for idx, exc in enumerate(excs):
            if not isinstance(exc, dict) or not validate_exception_shape(exc)["ok"]:
                return _failed_report("evidence_bundle", "INVALID_EXCEPTION_FOR_REPORT", f"exceptions[{idx}] failed validation.")
    if prepared_writes is not None:
        for idx, item in enumerate(writes):
            pw = _unwrap_prepared_write(item)
            if not isinstance(pw, dict) or not validate_prepared_write_shape(pw)["ok"]:
                return _failed_report("evidence_bundle", "INVALID_PREPARED_WRITE_FOR_REPORT", f"prepared_writes[{idx}] failed validation.")

    section_invoice = _invoice_evidence(inv)
    section_extraction = _extraction_evidence(inv)
    section_matching = _matching_evidence_section(mr) if mr is not None else _section("matching_evidence", [])
    section_exception = _exception_evidence_section([dict(exc) for exc in excs]) if excs is not None else _section("exception_evidence", [])
    prepared_write_items = [_unwrap_prepared_write(item) for item in writes if _unwrap_prepared_write(item) is not None]
    section_prepared = _prepared_write_evidence_section([item for item in prepared_write_items if item is not None])
    rollback_items = [dict(item.get("rollback_plan", {})) for item in prepared_write_items if isinstance(item, dict) and item.get("rollback_plan")]
    section_rollback = _rollback_evidence_section(rollback_items)
    sections = [
        section_invoice,
        section_extraction,
        section_matching,
        section_exception,
        section_prepared,
        section_rollback,
    ]
    sections = [section for section in sections if section["items"] or section["section"] == "invoice_source_evidence"]
    report = _base_report(
        inv=inv,
        match_status=str(mr.get("match_status", "matched")) if mr is not None else ("blocked" if excs else "matched"),
        summary=_bundle_summary(inv, mr, excs, writes),
        checks=mr.get("checks", []) if mr is not None else [],
        exceptions=[dict(exc) for exc in excs] if excs is not None else [],
        prepared_writes=prepared_write_items,
        rollback_plans=rollback_items,
        extra={
            "invoice_number": str(inv.get("invoice_number", "")),
            "supplier_name": str(inv.get("supplier_name", "")),
            "po_number": str(inv.get("po_number", "")),
            "invoice_source_evidence": section_invoice["items"],
            "extraction_evidence": section_extraction["items"],
            "matching_evidence": section_matching["items"],
            "exception_evidence": section_exception["items"],
            "prepared_write_evidence": section_prepared["items"],
            "rollback_evidence": section_rollback["items"],
        },
    )
    report["evidence"] = sections
    return _report_result("evidence_bundle", report, sections)


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _base_report(
    *,
    inv: dict,
    match_status: str,
    summary: str,
    checks: list[dict],
    exceptions: list[dict],
    prepared_writes: list[dict],
    rollback_plans: list[dict],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "report_id": f"RPT-{_string(inv.get('invoice_number') or inv.get('invoice_id') or 'UNKNOWN')}",
        "invoice_id": _string(inv.get("invoice_id", "")),
        "match_status": _normalize_match_status(match_status),
        "summary": summary,
        "checks": list(checks),
        "exceptions": list(exceptions),
        "prepared_writes": list(prepared_writes),
        "rollback_plans": list(rollback_plans),
        "evidence": [],
    }
    if extra:
        report.update({key: value for key, value in extra.items() if value is not None})
    validation = validate_report_shape(report)
    if not validation["ok"]:
        raise ValueError(f"Report validation failed: {validation['errors']}")
    return report


def _report_result(kind: str, report: dict, evidence: list[dict] | None) -> dict:
    evidence_payload = evidence if evidence is not None else []
    result_evidence = build_tool_evidence(
        tool=_TOOL_KEYS[kind],
        mode="dry_run",
        source="builtin",
        operation="report",
        input_refs=_input_refs_from_report(report),
        output_ref=_RESULT_TYPE,
        extra={
            "report_id": report.get("report_id", ""),
            "match_status": report.get("match_status", ""),
            "section_count": len(report.get("evidence", [])),
        },
    )
    return {
        "ok": True,
        "type": _RESULT_TYPE,
        "data": {"report": report},
        "evidence": {
            "tool": result_evidence["tool"],
            "mode": result_evidence["mode"],
            "source": result_evidence["source"],
            "operation": result_evidence["operation"],
            "input_refs": result_evidence["input_refs"],
            "output_ref": result_evidence["output_ref"],
            "sections": evidence_payload,
        },
        "error": "",
        "metadata": {
            "report_id": report.get("report_id", ""),
            "invoice_id": report.get("invoice_id", ""),
            "match_status": report.get("match_status", ""),
            "dry_run": True,
            "live_side_effect": False,
        },
    }


def _failed_report(kind: str, error_code: str, message: str) -> dict:
    evidence = build_tool_evidence(
        tool=_TOOL_KEYS[kind],
        mode="dry_run",
        source="builtin",
        operation="report",
        input_refs=[],
        output_ref=_RESULT_TYPE,
        extra={"error_code": error_code},
    )
    return {
        "ok": False,
        "type": _RESULT_TYPE,
        "data": {"report": {}},
        "evidence": evidence,
        "error": error_code,
        "metadata": {"dry_run": True, "live_side_effect": False},
    }


def _bundle_evidence(
    *,
    tool_key: str,
    invoice: dict,
    sections: list[dict],
    input_refs: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = build_tool_evidence(
        tool=_TOOL_KEYS[tool_key],
        mode="dry_run",
        source="builtin",
        operation="report",
        input_refs=[item for item in input_refs if str(item).strip()],
        output_ref=_RESULT_TYPE,
        extra=extra or {},
    )
    return {"evidence": evidence, "sections": sections}


# ---------------------------------------------------------------------------
# Evidence section builders
# ---------------------------------------------------------------------------

def _section(section: str, items: list[dict]) -> dict[str, Any]:
    return {"section": section, "items": [dict(item) for item in items]}


def _invoice_evidence(inv: dict) -> dict[str, Any]:
    items = [
        {
            "evidence_id": f"EVD-INVOICE-{_string(inv.get('invoice_id') or inv.get('invoice_number') or 'UNKNOWN')}",
            "source_type": "tool_output",
            "source_ref": _string(inv.get("invoice_id") or inv.get("invoice_number") or "invoice"),
            "field_path": "invoice",
            "raw_value": _string(inv.get("invoice_number") or inv.get("invoice_id") or ""),
            "confidence": 1.0,
        }
    ]
    return _section("invoice_source_evidence", items)


def _extraction_evidence(inv: dict) -> dict[str, Any]:
    items = [
        {
            "evidence_id": f"EVD-EXTRACT-{_string(inv.get('invoice_id') or inv.get('invoice_number') or 'UNKNOWN')}-1",
            "source_type": "tool_output",
            "source_ref": _string(inv.get("invoice_id") or inv.get("invoice_number") or "invoice"),
            "field_path": "invoice.invoice_number",
            "raw_value": _string(inv.get("invoice_number", "")),
            "confidence": 1.0,
        },
        {
            "evidence_id": f"EVD-EXTRACT-{_string(inv.get('invoice_id') or inv.get('invoice_number') or 'UNKNOWN')}-2",
            "source_type": "tool_output",
            "source_ref": _string(inv.get("invoice_id") or inv.get("invoice_number") or "invoice"),
            "field_path": "invoice.po_number",
            "raw_value": _string(inv.get("po_number", "")),
            "confidence": 1.0,
        },
    ]
    return _section("extraction_evidence", items)


def _matching_evidence_section(match_result: dict | None) -> dict[str, Any]:
    if not isinstance(match_result, dict):
        return _section("matching_evidence", [])
    evidence = match_result.get("evidence")
    items = [dict(evidence)] if isinstance(evidence, dict) else []
    items.append(
        {
            "evidence_id": f"EVD-MATCH-{_string(match_result.get('match_id', 'UNKNOWN'))}",
            "source_type": "tool_output",
            "source_ref": _string(match_result.get("match_id", "")),
            "field_path": "match_result.match_status",
            "raw_value": _string(match_result.get("match_status", "")),
            "confidence": 1.0,
        }
    )
    return _section("matching_evidence", items)


def _match_evidence_section(match_result: dict) -> dict[str, Any]:
    return _matching_evidence_section(match_result)


def _exception_evidence_section(exceptions: list[dict]) -> dict[str, Any]:
    items: list[dict] = []
    for exc in exceptions:
        items.append(
            {
                "evidence_id": f"EVD-EXC-{_string(exc.get('exception_id', 'UNKNOWN'))}",
                "source_type": "tool_output",
                "source_ref": _string(exc.get("exception_id", "")),
                "field_path": "exception",
                "raw_value": _string(exc.get("exception_type", "")),
                "confidence": 1.0,
            }
        )
    return _section("exception_evidence", items)


def _action_plan_evidence(action_plan: dict | None) -> dict[str, Any]:
    if not isinstance(action_plan, dict) or not action_plan:
        return _section("action_plan_evidence", [])
    return _section(
        "action_plan_evidence",
        [
            {
                "evidence_id": f"EVD-PLAN-{_string(action_plan.get('exception_action_plan_id', 'UNKNOWN'))}",
                "source_type": "tool_output",
                "source_ref": _string(action_plan.get("exception_action_plan_id", "")),
                "field_path": "action_plan",
                "raw_value": _string(action_plan.get("recommended_action", "")),
                "confidence": 1.0,
            }
        ],
    )


def _ledger_evidence_section(rows: list[dict]) -> dict[str, Any]:
    items: list[dict] = []
    for row in rows:
        items.append(
            {
                "evidence_id": f"EVD-LEDGER-{_string(row.get('ledger_entry_id', 'UNKNOWN'))}",
                "source_type": "tool_output",
                "source_ref": _string(row.get("ledger_entry_id", "")),
                "field_path": "ledger_row",
                "raw_value": _string(row.get("status", "")),
                "confidence": 1.0,
            }
        )
    return _section("ledger_evidence", items)


def _prepared_write_evidence_section(prepared_writes: list[dict]) -> dict[str, Any]:
    items: list[dict] = []
    for write in prepared_writes:
        items.append(
            {
                "evidence_id": f"EVD-PW-{_string(write.get('prepared_write_id', 'UNKNOWN'))}",
                "source_type": "tool_output",
                "source_ref": _string(write.get("prepared_write_id", "")),
                "field_path": "prepared_write",
                "raw_value": _string(write.get("target", "")),
                "confidence": 1.0,
            }
        )
    return _section("prepared_write_evidence", items)


def _rollback_evidence_section(rollback_plans: list[dict]) -> dict[str, Any]:
    items: list[dict] = []
    for plan in rollback_plans:
        if not plan:
            continue
        items.append(
            {
                "evidence_id": f"EVD-RBK-{_string(plan.get('rollback_id', 'UNKNOWN'))}",
                "source_type": "tool_output",
                "source_ref": _string(plan.get("rollback_id", "")),
                "field_path": "rollback_plan",
                "raw_value": _string(plan.get("rollback_type", "")),
                "confidence": 1.0,
            }
        )
    return _section("rollback_evidence", items)


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------

def _match_summary(inv: dict, match_result: dict, check_summary: dict[str, int]) -> str:
    return (
        f"Invoice {inv.get('invoice_number', '')} for {inv.get('supplier_name', '')} "
        f"is {match_result.get('match_status', 'exception')} with "
        f"{check_summary.get('pass', 0)} pass, {check_summary.get('fail', 0)} fail, "
        f"{check_summary.get('warn', 0)} warn checks."
    )


def _exception_summary(inv: dict, exceptions: list[dict], plan: dict | None) -> str:
    severity_counts = Counter(str(exc.get("severity", "low")) for exc in exceptions)
    action = _recommended_exception_action(exceptions, plan)
    return (
        f"Invoice {inv.get('invoice_number', '')} has {len(exceptions)} exception(s): "
        f"{dict(severity_counts)}. Recommended action: {action}."
    )


def _ledger_summary(inv: dict, rows: list[dict], posting_allowed: bool) -> str:
    return (
        f"Invoice {inv.get('invoice_number', '')} has {len(rows)} ledger row(s); "
        f"posting is {'allowed' if posting_allowed else 'not allowed'}."
    )


def _rollback_summary(prepared_writes: list[dict], rollback_plans: list[dict], warnings: list[str]) -> str:
    return (
        f"{len(prepared_writes)} prepared write(s) reviewed; "
        f"{len(rollback_plans)} rollback plan(s) available."
    )


def _bundle_summary(inv: dict, mr: dict | None, excs: list[dict] | None, writes: list[dict] | None) -> str:
    return (
        f"Evidence bundle for invoice {inv.get('invoice_number', '')} includes "
        f"{1 + (1 if mr else 0) + (len(excs or [])) + (len(writes or []))} source group(s)."
    )


def _recommended_exception_action(exceptions: list[dict], plan: dict | None) -> str:
    if isinstance(plan, dict) and str(plan.get("recommended_action", "")).strip():
        return str(plan["recommended_action"])
    for exc in exceptions:
        action = str(exc.get("recommended_action", "")).strip()
        if action:
            return action
    return "operator_review"


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _count_check_statuses(checks: list[dict]) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "warn": 0, "not_applicable": 0}
    for check in checks:
        status = str(check.get("status", "")).strip()
        if status in counts:
            counts[status] += 1
    return counts


def _decision_from_allowed(allowed: bool) -> str:
    return "allowed" if allowed else "blocked"


def _normalize_match_status(status: str) -> str:
    text = str(status or "").strip().lower()
    if text in {"matched", "exception", "blocked"}:
        return text
    return "exception"


def _unique_values(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        value = str(value).strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def _first_non_empty(values: list[str]) -> str:
    for value in values:
        if str(value).strip():
            return str(value).strip()
    return ""


def _input_refs_from_report(report: dict) -> list[str]:
    refs = [
        str(report.get("invoice_id", "")).strip(),
        str(report.get("invoice_number", "")).strip(),
        str(report.get("po_number", "")).strip(),
    ]
    return [item for item in refs if item]


def _unwrap_invoice(invoice: Any) -> dict | None:
    if not isinstance(invoice, dict):
        return None
    data = invoice.get("data") if isinstance(invoice.get("data"), dict) else None
    if isinstance(data, dict):
        for key in ("invoice", "report", "invoice_data"):
            nested = data.get(key)
            if isinstance(nested, dict):
                return dict(nested)
    return dict(invoice)


def _unwrap_match_result(match_result: Any) -> dict | None:
    if not isinstance(match_result, dict):
        return None
    data = match_result.get("data") if isinstance(match_result.get("data"), dict) else None
    if isinstance(data, dict):
        nested = data.get("match_result")
        if isinstance(nested, dict):
            return dict(nested)
    return dict(match_result)


def _unwrap_prepared_write(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    data = value.get("data") if isinstance(value.get("data"), dict) else None
    if isinstance(data, dict):
        nested = data.get("prepared_write")
        if isinstance(nested, dict):
            return dict(nested)
    return dict(value)


def _unwrap_list(value: Any) -> list[dict] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [dict(value)]
    return None


def _unwrap_dict(value: Any) -> dict | None:
    return value if isinstance(value, dict) else None


def _string(value: Any) -> str:
    return str(value or "")
