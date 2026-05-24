from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .invoiceops_sheet_tools import (
    invoiceops_read_exception_register,
    invoiceops_read_invoice_register,
    invoiceops_read_ledger,
)
from .live_execution_ledger import read_ledger_entries
from .persistence import ensure_dir, write_json_atomic
from .taskframe_reload import load_taskframe
from src.config_profiles import load_config_profile
from .invoiceops_posting_ledger import (
    STATUS_BLOCKED as POSTING_STATUS_BLOCKED,
    STATUS_EXECUTED_VERIFIED,
    STATUS_EXECUTED_UNVERIFIED,
    read_posting_ledger_entries,
)

RECONCILIATION_DIR = "invoiceops/reconciliation"
EVIDENCE_DIR = "invoiceops/accounting_evidence"
FIXTURE_BASE = Path("tests") / "fixtures" / "invoiceops"

_STATUS_VALUES = {
    "RECONCILED",
    "RECONCILED_WITH_WARNINGS",
    "UNRECONCILED",
    "MISSING_POSTING_EVIDENCE",
    "MANUAL_REVIEW_REQUIRED",
    "BLOCKED",
}

_TOLERANCE = 0.01


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_invoiceops_reconciliation_plan(
    *,
    frame_id: str = "",
    invoice_number: str = "",
    posting_plan_id: str = "",
    runtime_data_dir: str | Path = "runtime_data",
    profile: str = "service",
    fixture_mode: bool = True,
) -> dict[str, Any]:
    profile_config = load_config_profile(profile_name=profile, runtime_data_dir=runtime_data_dir)
    runtime_root = Path(runtime_data_dir)
    source_frame = _load_source_frame(frame_id, runtime_root)
    inferred = _infer_reference(source_frame, frame_id=frame_id, invoice_number=invoice_number, posting_plan_id=posting_plan_id)
    invoice_number = inferred["invoice_number"]
    frame_id = inferred["frame_id"]
    posting_plan_id = inferred["posting_plan_id"]

    case = _load_fixture_case(invoice_number) if fixture_mode else {}
    source_invoice = _resolve_source_invoice(source_frame, case)
    source_match_result = _resolve_source_match_result(source_frame, case)
    source_exception = _resolve_source_exception(source_frame, case)
    source_ledger_rows = _resolve_source_ledger_rows(source_frame, case)
    source_register_rows = _resolve_source_register_rows(
        invoice_number=invoice_number,
        runtime_data_dir=runtime_root,
        fixture_mode=fixture_mode,
        profile_config=profile_config,
    )
    posting_ledger_entry = _resolve_posting_ledger_entry(
        runtime_root,
        frame_id=frame_id,
        posting_plan_id=posting_plan_id,
        invoice_number=invoice_number,
    )
    rollback_plan = dict(posting_ledger_entry.get("rollback_plan") or {})
    source_evidence = _resolve_source_evidence(source_frame, case)

    plan = {
        "ok": True,
        "profile": profile,
        "fixture_mode": bool(fixture_mode),
        "generated_at": _utc_now(),
        "invoice_number": invoice_number,
        "invoice_id": str((source_invoice or {}).get("invoice_id", "") or ""),
        "supplier_name": str((source_invoice or {}).get("supplier_name", "") or ""),
        "posting_plan_id": posting_plan_id,
        "frame_id": frame_id,
        "match_status": str((source_match_result or {}).get("match_status", "") or ""),
        "source_frame": source_frame or {},
        "source_invoice": source_invoice or {},
        "source_match_result": source_match_result or {},
        "source_exception": source_exception or {},
        "invoice_register_rows": list(source_register_rows.get("invoice_register_rows", [])),
        "match_register_rows": list(source_register_rows.get("match_register_rows", [])),
        "exception_register_rows": list(source_register_rows.get("exception_register_rows", [])),
        "ledger_rows": list(source_ledger_rows or source_register_rows.get("ledger_rows", [])),
        "posting_ledger_entry": posting_ledger_entry or {},
        "rollback_plan": rollback_plan,
        "source_evidence": source_evidence,
        "posting_ledger_entries": _select_posting_ledger_entries(runtime_root, frame_id=frame_id, posting_plan_id=posting_plan_id, invoice_number=invoice_number),
        "live_execution_ledger": _select_live_execution_entries(runtime_root, frame_id=frame_id, invoice_number=invoice_number),
        "config_profile": _profile_as_dict(profile_config),
        "registers_checked": ["invoice_register", "match_register", "exception_register", "ledger_register", "posting_ledger"],
        "report_paths": {},
    }
    return plan


def load_invoiceops_posted_rows(
    *,
    frame_id: str = "",
    invoice_number: str = "",
    posting_plan_id: str = "",
    runtime_data_dir: str | Path = "runtime_data",
    profile: str = "service",
    fixture_mode: bool = True,
) -> dict[str, Any]:
    return build_invoiceops_reconciliation_plan(
        frame_id=frame_id,
        invoice_number=invoice_number,
        posting_plan_id=posting_plan_id,
        runtime_data_dir=runtime_data_dir,
        profile=profile,
        fixture_mode=fixture_mode,
    )


def reconcile_invoice_register(plan: dict[str, Any]) -> dict[str, Any]:
    source_invoice = dict(plan.get("source_invoice") or {})
    rows = _as_list(plan.get("invoice_register_rows"))
    invoice_number = str(plan.get("invoice_number", "") or source_invoice.get("invoice_number", "") or "")
    row = _find_row(rows, "invoice_number", invoice_number) or _find_row(rows, "invoice_id", str(source_invoice.get("invoice_id", "") or ""))
    if not row:
        return _check("invoice_register", "MISSING_POSTING_EVIDENCE", False, "Invoice register row not found.")

    supplier_ok = _match_text(row.get("supplier_name"), source_invoice.get("supplier_name")) or _match_text(row.get("supplier_id"), source_invoice.get("supplier_id"))
    po_ok = _match_text(row.get("po_number"), source_invoice.get("po_number"))
    amount_ok = _match_amount(row.get("invoice_total"), source_invoice.get("invoice_total"))
    frame_ok = True
    if plan.get("frame_id") and str(row.get("source_frame_id", "") or row.get("frame_id", "")):
        frame_ok = _match_text(row.get("source_frame_id") or row.get("frame_id"), plan.get("frame_id"))
    result_ok = supplier_ok and po_ok and amount_ok and frame_ok
    status = "OK" if result_ok else "FAIL"
    return _check(
        "invoice_register",
        "RECONCILED" if result_ok else "UNRECONCILED",
        result_ok,
        "Invoice register row reconciled." if result_ok else "Invoice register row does not match the source invoice.",
        details={"row": row, "source_invoice": source_invoice},
        evidence_refs=["invoice_register"],
    )


def reconcile_match_register(plan: dict[str, Any]) -> dict[str, Any]:
    match_status = str(plan.get("match_status", "") or "")
    rows = _as_list(plan.get("match_register_rows"))
    source_match = dict(plan.get("source_match_result") or {})
    if match_status not in {"matched", "exception", "blocked"}:
        return _check("match_register", "MANUAL_REVIEW_REQUIRED", False, "Match status is missing or unknown.")
    if not rows and match_status == "matched":
        return _check("match_register", "MISSING_POSTING_EVIDENCE", False, "Match register row not found for matched invoice.")
    if not rows and match_status in {"exception", "blocked"}:
        return _check("match_register", "MANUAL_REVIEW_REQUIRED", False, "Match or summary row is missing for an exception/blocked invoice.")
    row = rows[0] if rows else {}
    status_ok = _match_text(row.get("match_status"), match_status) or not row
    invoice_ok = _match_text(row.get("invoice_number"), plan.get("invoice_number")) or _match_text(row.get("invoice_id"), plan.get("invoice_id"))
    result_ok = bool(status_ok and invoice_ok)
    return _check(
        "match_register",
        "RECONCILED" if result_ok else "UNRECONCILED",
        result_ok,
        "Match register row reconciled." if result_ok else "Match register row does not agree with the source match result.",
        details={"rows": rows, "source_match_result": source_match},
        evidence_refs=["match_register"],
    )


def reconcile_exception_register(plan: dict[str, Any]) -> dict[str, Any]:
    match_status = str(plan.get("match_status", "") or "")
    rows = _as_list(plan.get("exception_register_rows"))
    source_exception = dict(plan.get("source_exception") or {})
    if match_status == "matched":
        return _check("exception_register", "SKIPPED", True, "Matched invoices do not require exception register reconciliation.", skipped=True, evidence_refs=["exception_register"])
    if not rows:
        return _check("exception_register", "MANUAL_REVIEW_REQUIRED", False, "Exception register row is missing or incomplete.")
    row = rows[0]
    type_ok = _match_text(row.get("exception_type"), source_exception.get("exception_type")) or bool(source_exception.get("exception_type"))
    sev_ok = _match_text(row.get("severity"), source_exception.get("severity")) or bool(source_exception.get("severity"))
    result_ok = type_ok and sev_ok
    return _check(
        "exception_register",
        "RECONCILED" if result_ok else "MANUAL_REVIEW_REQUIRED",
        result_ok,
        "Exception register row reconciled." if result_ok else "Exception register row is incomplete or mismatched.",
        details={"rows": rows, "source_exception": source_exception},
        evidence_refs=["exception_register"],
    )


def reconcile_ledger_register(plan: dict[str, Any]) -> dict[str, Any]:
    match_status = str(plan.get("match_status", "") or "")
    rows = _as_list(plan.get("ledger_rows"))
    source_invoice = dict(plan.get("source_invoice") or {})
    invoice_total = _num(source_invoice.get("invoice_total"))
    if match_status == "blocked":
        if rows:
            return _check("ledger_register", "UNRECONCILED", False, "Blocked invoice must not create final ledger rows.", critical=True, details={"rows": rows}, evidence_refs=["ledger_register"])
        return _check("ledger_register", "RECONCILED", True, "Blocked invoice has no final ledger rows.", evidence_refs=["ledger_register"])
    if match_status == "exception":
        if rows:
            return _check("ledger_register", "UNRECONCILED", False, "Exception invoice has ledger rows without explicit allowance.", critical=True, details={"rows": rows}, evidence_refs=["ledger_register"])
        return _check("ledger_register", "RECONCILED_WITH_WARNINGS", True, "Exception invoice has no final ledger rows.", warning=True, evidence_refs=["ledger_register"])
    if not rows:
        return _check("ledger_register", "MISSING_POSTING_EVIDENCE", False, "Ledger rows are missing for a matched invoice.")
    total_debit = sum(_num(row.get("amount")) for row in rows if str(row.get("debit_account", "")).strip())
    total_credit = sum(_num(row.get("amount")) for row in rows if str(row.get("credit_account", "")).strip())
    balanced = abs(total_debit - total_credit) <= _TOLERANCE
    invoice_match = True if invoice_total is None else abs(total_debit - invoice_total) <= _TOLERANCE
    result_ok = balanced and invoice_match
    return _check(
        "ledger_register",
        "RECONCILED" if result_ok else "UNRECONCILED",
        result_ok,
        "Ledger rows balance and match the invoice total." if result_ok else "Ledger rows are unbalanced or do not match the invoice total.",
        critical=not result_ok,
        details={"rows": rows, "total_debit": total_debit, "total_credit": total_credit, "invoice_total": invoice_total},
        evidence_refs=["ledger_register"],
    )


def reconcile_posting_ledger(plan: dict[str, Any]) -> dict[str, Any]:
    entries = _as_list(plan.get("posting_ledger_entries"))
    entry = dict(plan.get("posting_ledger_entry") or {})
    if not entries and not entry:
        return _check("posting_ledger", "MISSING_POSTING_EVIDENCE", False, "Posting ledger entry is missing.")
    if not entry and entries:
        entry = dict(entries[-1])
    if not entry:
        return _check("posting_ledger", "MISSING_POSTING_EVIDENCE", False, "Posting ledger entry is missing.")
    status = str(entry.get("status", "") or "").upper()
    if status not in {STATUS_EXECUTED_VERIFIED, STATUS_EXECUTED_UNVERIFIED, POSTING_STATUS_BLOCKED, "FAILED", "PENDING"}:
        return _check("posting_ledger", "MANUAL_REVIEW_REQUIRED", False, "Posting ledger status is unknown.")
    if str(plan.get("match_status", "") or "") == "blocked" and status == STATUS_EXECUTED_VERIFIED:
        return _check("posting_ledger", "UNRECONCILED", False, "Blocked invoice has a verified posting ledger entry.", critical=True, details={"entry": entry}, evidence_refs=["posting_ledger"])
    rollback_plan = dict(entry.get("rollback_plan") or plan.get("rollback_plan") or {})
    rollback_ok = bool(rollback_plan)
    if not rollback_ok and str(plan.get("match_status", "") or "") == "matched":
        return _check("posting_ledger", "MANUAL_REVIEW_REQUIRED", False, "Rollback plan is missing from the posting ledger entry.")
    result_ok = status == STATUS_EXECUTED_VERIFIED and rollback_ok
    return _check(
        "posting_ledger",
        "RECONCILED" if result_ok else "RECONCILED_WITH_WARNINGS",
        result_ok or status == STATUS_EXECUTED_UNVERIFIED,
        "Posting ledger entry agrees with the posted rows." if result_ok else "Posting ledger entry is present but not fully verified.",
        warning=not result_ok,
        details={"entry": entry, "rollback_plan": rollback_plan},
        evidence_refs=["posting_ledger"],
    )


def build_invoiceops_reconciliation_result(
    plan: dict[str, Any] | None = None,
    *,
    frame_id: str = "",
    invoice_number: str = "",
    posting_plan_id: str = "",
    runtime_data_dir: str | Path = "runtime_data",
    profile: str = "service",
    fixture_mode: bool = True,
    write_report: bool = False,
) -> dict[str, Any]:
    plan = dict(plan or build_invoiceops_reconciliation_plan(
        frame_id=frame_id,
        invoice_number=invoice_number,
        posting_plan_id=posting_plan_id,
        runtime_data_dir=runtime_data_dir,
        profile=profile,
        fixture_mode=fixture_mode,
    ))
    checks = [
        reconcile_invoice_register(plan),
        reconcile_match_register(plan),
        reconcile_exception_register(plan),
        reconcile_ledger_register(plan),
        reconcile_posting_ledger(plan),
    ]
    registers_checked = list(dict.fromkeys(plan.get("registers_checked", [])))
    blockers = [item["message"] for item in checks if item.get("critical") or item.get("status") in {"UNRECONCILED", "BLOCKED"}]
    warnings = [item["message"] for item in checks if item.get("warning")]
    exceptions = [item for item in checks if item.get("status") in {"MANUAL_REVIEW_REQUIRED", "MISSING_POSTING_EVIDENCE"}]
    status = _classify_reconciliation(plan, checks, blockers, warnings, exceptions)
    result = {
        "ok": status in {"RECONCILED", "RECONCILED_WITH_WARNINGS"},
        "status": status,
        "invoice_id": str(plan.get("invoice_id", "") or ""),
        "invoice_number": str(plan.get("invoice_number", "") or invoice_number or ""),
        "supplier_name": str(plan.get("supplier_name", "") or ""),
        "posting_plan_id": str(plan.get("posting_plan_id", "") or posting_plan_id or ""),
        "frame_id": str(plan.get("frame_id", "") or frame_id or ""),
        "registers_checked": registers_checked,
        "checks": checks,
        "exceptions": exceptions,
        "warnings": warnings,
        "blockers": blockers,
        "evidence_refs": _collect_evidence_refs(checks, plan),
        "report_paths": {},
        "plan": plan,
        "recommended_action": _recommended_action(status, blockers, warnings),
        "generated_at": _utc_now(),
    }
    if write_report:
        result["report_paths"] = write_invoiceops_reconciliation_report(result, runtime_data_dir=runtime_data_dir)
    return result


def write_invoiceops_reconciliation_report(
    result: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, str]:
    out_dir = ensure_dir(Path(runtime_data_dir) / RECONCILIATION_DIR)
    invoice_number = _safe_name(str(result.get("invoice_number", "") or "unknown_invoice"))
    json_path = out_dir / f"{invoice_number}_reconciliation.json"
    md_path = out_dir / f"{invoice_number}_reconciliation.md"
    payload = dict(result)
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    write_json_atomic(json_path, payload)
    md_path.write_text(render_invoiceops_reconciliation_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_invoiceops_reconciliation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# InvoiceOps Post-Write Reconciliation",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Status | {report.get('status', '')} |",
        f"| Invoice Number | {report.get('invoice_number', '')} |",
        f"| Supplier | {report.get('supplier_name', '')} |",
        f"| Posting Plan ID | {report.get('posting_plan_id', '')} |",
        f"| Frame ID | {report.get('frame_id', '')} |",
        "",
        "## Summary",
        "",
        report.get("recommended_action", "") or "No recommended action.",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        lines.append(f"- [{ 'ok' if check.get('ok') else 'FAIL' }] {check.get('name', '')}: {check.get('message', '')}")
    lines.extend(
        [
            "",
            "## Registers Checked",
            "",
        ]
    )
    for item in report.get("registers_checked", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Blockers",
            "",
        ]
    )
    if report.get("blockers"):
        lines.extend(f"- {item}" for item in report.get("blockers", []))
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    if report.get("warnings"):
        lines.extend(f"- {item}" for item in report.get("warnings", []))
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    if report.get("evidence_refs"):
        lines.extend(f"- {item}" for item in report.get("evidence_refs", []))
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Rollback",
            "",
            f"- Rollback plan linked: {bool((report.get('plan') or {}).get('rollback_plan'))}",
            "",
            "## Final Status",
            "",
            f"- {report.get('status', '')}",
        ]
    )
    return "\n".join(lines)


def _classify_reconciliation(plan: dict[str, Any], checks: list[dict[str, Any]], blockers: list[str], warnings: list[str], exceptions: list[dict[str, Any]]) -> str:
    if any(check.get("critical") and not check.get("ok") for check in checks):
        return "UNRECONCILED"
    if any(check.get("status") == "UNRECONCILED" for check in checks):
        return "UNRECONCILED"
    if any(check.get("status") == "BLOCKED" for check in checks):
        return "BLOCKED"
    if any(check.get("status") == "MISSING_POSTING_EVIDENCE" for check in checks) or not plan.get("posting_ledger_entry"):
        return "MISSING_POSTING_EVIDENCE"
    if str(plan.get("match_status", "") or "") == "exception":
        return "MANUAL_REVIEW_REQUIRED"
    if any(check.get("status") == "MANUAL_REVIEW_REQUIRED" for check in checks):
        return "MANUAL_REVIEW_REQUIRED"
    if blockers and not warnings:
        return "BLOCKED"
    if warnings:
        return "RECONCILED_WITH_WARNINGS"
    return "RECONCILED"


def _collect_evidence_refs(checks: list[dict[str, Any]], plan: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for check in checks:
        refs.extend(list(check.get("evidence_refs", [])))
    if plan.get("frame_id"):
        refs.append(f"frame:{plan.get('frame_id')}")
    if plan.get("posting_plan_id"):
        refs.append(f"posting_plan:{plan.get('posting_plan_id')}")
    if plan.get("invoice_number"):
        refs.append(f"invoice:{plan.get('invoice_number')}")
    return list(dict.fromkeys(refs))


def _load_source_frame(frame_id: str, runtime_root: Path) -> dict[str, Any]:
    if not frame_id:
        return {}
    try:
        frame = load_taskframe(frame_id, runtime_root)
    except Exception:
        return {}
    if frame is None:
        return {}
    if hasattr(frame, "to_dict"):
        try:
            return dict(frame.to_dict())
        except Exception:
            pass
    if isinstance(frame, dict):
        return dict(frame)
    try:
        from .taskframe import to_dict as frame_to_dict

        return frame_to_dict(frame)
    except Exception:
        return {}


def _infer_reference(source_frame: dict[str, Any], *, frame_id: str, invoice_number: str, posting_plan_id: str) -> dict[str, str]:
    if not invoice_number and isinstance(source_frame, dict):
        invoice_number = _extract_value(source_frame, ("outputs", "invoice", "invoice_number")) or _extract_value(source_frame, ("outputs", "match_result", "invoice_number")) or _extract_value(source_frame, ("inputs", "invoice_number"))
    if not posting_plan_id and isinstance(source_frame, dict):
        posting_plan_id = _extract_value(source_frame, ("outputs", "posting_plan", "posting_plan_id")) or _extract_value(source_frame, ("outputs", "posting_plan", "data", "posting_plan_id"))
    source_frame_id = str(source_frame.get("frame_id", "") or "") if isinstance(source_frame, dict) else ""
    frame_id = str(frame_id or source_frame_id or "")
    return {"invoice_number": str(invoice_number or ""), "posting_plan_id": str(posting_plan_id or ""), "frame_id": frame_id}


def _resolve_source_invoice(source_frame: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    for path in (("outputs", "invoice"), ("outputs", "extracted_invoice", "data", "invoice"), ("invoice"), ("invoice",)):
        found = _extract_mapping(source_frame, path)
        if found:
            return found
    if case.get("invoice"):
        return dict(case["invoice"])
    return {}


def _resolve_source_match_result(source_frame: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    for path in (("outputs", "match_result"), ("outputs", "match_result", "data", "match_result"), ("match_result"),):
        found = _extract_mapping(source_frame, path)
        if found:
            return found
    if case.get("match_result"):
        return dict(case["match_result"])
    return {}


def _resolve_source_exception(source_frame: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    if case.get("exceptions"):
        exceptions = case["exceptions"]
        if isinstance(exceptions, list) and exceptions:
            return dict(exceptions[0])
    for path in (("outputs", "classified_exceptions"), ("outputs", "exceptions")):
        value = _extract_value(source_frame, path)
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return dict(first)
    return {}


def _resolve_source_ledger_rows(source_frame: dict[str, Any], case: dict[str, Any]) -> list[dict[str, Any]]:
    for path in (("outputs", "ledger_rows"), ("outputs", "match_result", "ledger_rows"), ("outputs", "prepared_ledger_write", "data", "prepared_write", "rows")):
        value = _extract_value(source_frame, path)
        if isinstance(value, list) and value:
            return [dict(item) for item in value if isinstance(item, dict)]
    if case.get("prepared_writes"):
        writes = case["prepared_writes"]
        if isinstance(writes, list):
            for item in writes:
                if isinstance(item, dict):
                    if str(item.get("target", "")).lower() in {"ledger", "ledger_register"}:
                        rows = item.get("rows", [])
                        if isinstance(rows, list):
                            return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _resolve_source_register_rows(
    *,
    invoice_number: str,
    runtime_data_dir: Path,
    fixture_mode: bool,
    profile_config: Any,
) -> dict[str, list[dict[str, Any]]]:
    invoice_register_rows: list[dict[str, Any]] = []
    exception_register_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    if fixture_mode:
        base = FIXTURE_BASE / "sheets"
        invoice_result = invoiceops_read_invoice_register(fixture_mode=True, _fixture_dir=str(base))
        exception_result = invoiceops_read_exception_register(fixture_mode=True, _fixture_dir=str(base))
        ledger_result = invoiceops_read_ledger(fixture_mode=True, _fixture_dir=str(base))
        invoice_register_rows = _rows_from_sheet_result(invoice_result, invoice_number)
        exception_register_rows = _rows_from_sheet_result(exception_result, invoice_number)
        ledger_rows = _rows_from_sheet_result(ledger_result, invoice_number)
    else:
        spreadsheet_id = _resolve_spreadsheet_id(profile_config)
        if spreadsheet_id:
            try:
                invoice_result = invoiceops_read_invoice_register(spreadsheet_id=spreadsheet_id, fixture_mode=False)
                exception_result = invoiceops_read_exception_register(spreadsheet_id=spreadsheet_id, fixture_mode=False)
                ledger_result = invoiceops_read_ledger(spreadsheet_id=spreadsheet_id, fixture_mode=False)
                invoice_register_rows = _rows_from_sheet_result(invoice_result, invoice_number)
                exception_register_rows = _rows_from_sheet_result(exception_result, invoice_number)
                ledger_rows = _rows_from_sheet_result(ledger_result, invoice_number)
            except Exception:
                pass
    match_register_rows = []
    case = _load_fixture_case(invoice_number) if fixture_mode else {}
    if case.get("match_result"):
        match_register_rows.append(dict(case["match_result"]))
    return {
        "invoice_register_rows": invoice_register_rows,
        "match_register_rows": match_register_rows,
        "exception_register_rows": exception_register_rows,
        "ledger_rows": ledger_rows,
    }


def _resolve_posting_ledger_entry(runtime_root: Path, *, frame_id: str, posting_plan_id: str, invoice_number: str) -> dict[str, Any]:
    entries = read_posting_ledger_entries(runtime_data_dir=runtime_root)
    for entry in reversed(entries):
        if posting_plan_id and str(entry.get("posting_plan_id", "") or "") == posting_plan_id:
            return dict(entry)
        if frame_id and str(entry.get("frame_id", "") or "") == frame_id:
            return dict(entry)
        if invoice_number and str(entry.get("invoice_number", "") or "") == invoice_number:
            return dict(entry)
    return {}


def _select_posting_ledger_entries(runtime_root: Path, *, frame_id: str, posting_plan_id: str, invoice_number: str) -> list[dict[str, Any]]:
    entries = read_posting_ledger_entries(runtime_data_dir=runtime_root)
    selected: list[dict[str, Any]] = []
    for entry in entries:
        if posting_plan_id and str(entry.get("posting_plan_id", "") or "") == posting_plan_id:
            selected.append(dict(entry))
        elif frame_id and str(entry.get("frame_id", "") or "") == frame_id:
            selected.append(dict(entry))
        elif invoice_number and str(entry.get("invoice_number", "") or "") == invoice_number:
            selected.append(dict(entry))
    return selected


def _select_live_execution_entries(runtime_root: Path, *, frame_id: str, invoice_number: str) -> list[dict[str, Any]]:
    entries = read_ledger_entries(runtime_data_dir=runtime_root)
    selected: list[dict[str, Any]] = []
    for entry in entries:
        if frame_id and str(entry.get("frame_id", "") or "") == frame_id:
            selected.append(dict(entry))
        elif invoice_number and str(entry.get("business_ref", "") or "") == invoice_number:
            selected.append(dict(entry))
    return selected


def _resolve_source_evidence(source_frame: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    if case.get("evidence"):
        return dict(case["evidence"])
    if isinstance(source_frame, dict):
        outputs = source_frame.get("outputs", {})
        if isinstance(outputs, dict):
            bundle = outputs.get("evidence_bundle")
            if isinstance(bundle, dict):
                return dict(bundle)
    return {}


def _load_fixture_case(invoice_number: str) -> dict[str, Any]:
    invoice_number = str(invoice_number or "").strip()
    if invoice_number == "INV-2024-001":
        return _load_fixture_json(FIXTURE_BASE / "reports" / "happy_match.json")
    if invoice_number == "INV-2024-002":
        return _load_fixture_json(FIXTURE_BASE / "reports" / "blocked_match.json")
    if invoice_number == "INV-2024-005":
        return _load_fixture_json(FIXTURE_BASE / "reports" / "evidence_bundle.json")
    if invoice_number in {"INV-2026-001", "INV-2026-002"}:
        return {
            "invoice": _find_fixture_invoice(invoice_number),
            "match_result": _find_fixture_match_result(invoice_number),
            "exceptions": _find_fixture_exceptions(invoice_number),
            "prepared_writes": _find_fixture_prepared_writes(invoice_number),
            "evidence": _find_fixture_evidence_bundle(invoice_number),
        }
    return {}


def _find_fixture_invoice(invoice_number: str) -> dict[str, Any]:
    for path in (FIXTURE_BASE / "writes" / "invoice.json", FIXTURE_BASE / "matching" / "happy_path.json", FIXTURE_BASE / "reports" / "happy_match.json"):
        payload = _load_fixture_json(path)
        invoice = payload.get("invoice") if isinstance(payload, dict) else {}
        if isinstance(invoice, dict) and str(invoice.get("invoice_number", "") or "") == invoice_number:
            return dict(invoice)
    return {}


def _find_fixture_match_result(invoice_number: str) -> dict[str, Any]:
    for path in (FIXTURE_BASE / "writes" / "match_result.json", FIXTURE_BASE / "matching" / "happy_path.json", FIXTURE_BASE / "reports" / "happy_match.json", FIXTURE_BASE / "reports" / "blocked_match.json", FIXTURE_BASE / "reports" / "evidence_bundle.json"):
        payload = _load_fixture_json(path)
        match_result = payload.get("match_result") if isinstance(payload, dict) else {}
        if isinstance(match_result, dict) and str(match_result.get("invoice_number", "") or "") == invoice_number:
            return dict(match_result)
    return {}


def _find_fixture_exceptions(invoice_number: str) -> list[dict[str, Any]]:
    for path in (FIXTURE_BASE / "writes" / "exceptions.json", FIXTURE_BASE / "reports" / "evidence_bundle.json", FIXTURE_BASE / "reports" / "exceptions_multi.json", FIXTURE_BASE / "reports" / "blocked_match.json"):
        payload = _load_fixture_json(path)
        exceptions = payload.get("exceptions") if isinstance(payload, dict) else []
        if isinstance(exceptions, list):
            rows = [dict(item) for item in exceptions if isinstance(item, dict) and str(item.get("invoice_id", "") or item.get("invoice_number", "") or "") in {invoice_number, "", str(item.get("invoice_id", "") or "")}]
            if rows:
                return rows
    return []


def _find_fixture_prepared_writes(invoice_number: str) -> list[dict[str, Any]]:
    payload = _load_fixture_json(FIXTURE_BASE / "reports" / "evidence_bundle.json")
    prepared = payload.get("prepared_writes") if isinstance(payload, dict) else []
    if isinstance(prepared, list):
        return [dict(item) for item in prepared if isinstance(item, dict)]
    return []


def _find_fixture_evidence_bundle(invoice_number: str) -> dict[str, Any]:
    payload = _load_fixture_json(FIXTURE_BASE / "reports" / "evidence_bundle.json")
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def _load_fixture_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _rows_from_sheet_result(result: dict[str, Any], invoice_number: str) -> list[dict[str, Any]]:
    if not isinstance(result, dict) or not result.get("ok", False):
        return []
    data = result.get("data", {})
    rows = data.get("records") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []
    if not invoice_number:
        return [dict(item) for item in rows if isinstance(item, dict)]
    return [dict(item) for item in rows if isinstance(item, dict) and str(item.get("invoice_number", "") or item.get("invoice_id", "") or "") == invoice_number]


def _resolve_spreadsheet_id(profile_config: Any) -> str:
    path = getattr(profile_config, "accounting_sheet_config_path", None)
    if path and Path(path).is_file():
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            return str(payload.get("spreadsheet_id", "") or "")
        except Exception:
            return ""
    return ""


def _extract_value(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_mapping(data: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    value = _extract_value(data, path)
    return dict(value) if isinstance(value, dict) else {}


def _match_text(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left).strip() == str(right).strip()


def _match_amount(left: Any, right: Any) -> bool:
    left_num = _num(left)
    right_num = _num(right)
    if left_num is None or right_num is None:
        return False
    return abs(left_num - right_num) <= _TOLERANCE


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value or ""))


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _find_row(rows: list[dict[str, Any]], field: str, value: str) -> dict[str, Any]:
    if not value:
        return {}
    for row in rows:
        if str(row.get(field, "") or "").strip() == value:
            return dict(row)
    return {}


def _check(
    section: str,
    status: str,
    ok: bool,
    message: str,
    *,
    critical: bool = False,
    warning: bool = False,
    skipped: bool = False,
    details: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "section": section,
        "status": status,
        "ok": bool(ok),
        "message": message,
        "critical": critical,
        "warning": warning,
        "skipped": skipped,
        "details": details or {},
        "evidence_refs": evidence_refs or [section],
    }


def _profile_as_dict(profile: Any) -> dict[str, Any]:
    if hasattr(profile, "__dict__"):
        try:
            return {k: v for k, v in vars(profile).items() if not k.startswith("_")}
        except Exception:
            return {}
    return {}


def _recommended_action(status: str, blockers: list[str], warnings: list[str]) -> str:
    if status == "RECONCILED":
        return "No manual action required."
    if status == "RECONCILED_WITH_WARNINGS":
        return "Review the warnings and keep the reconciliation evidence with the invoice packet."
    if status == "MISSING_POSTING_EVIDENCE":
        return "Locate the posting plan, source TaskFrame, and live posting ledger entry before closing the file."
    if status == "MANUAL_REVIEW_REQUIRED":
        return "Review the incomplete exception or rollback evidence with a human approver."
    if status == "BLOCKED":
        return "Confirm the blocked path and ensure no final ledger rows were posted."
    return "Investigate the reconciliation blockers and correct the posting evidence."
