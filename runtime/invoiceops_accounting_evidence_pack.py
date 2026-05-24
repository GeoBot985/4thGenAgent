from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .invoiceops_reconciliation import (
    build_invoiceops_reconciliation_plan,
    build_invoiceops_reconciliation_result,
    render_invoiceops_reconciliation_markdown,
)
from .persistence import ensure_dir, write_json_atomic

ACCOUNTING_EVIDENCE_DIR = "invoiceops/accounting_evidence"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_accounting_evidence_pack(
    *,
    frame_id: str = "",
    invoice_number: str = "",
    posting_plan_id: str = "",
    runtime_data_dir: str | Path = "runtime_data",
    profile: str = "service",
    fixture_mode: bool = True,
    write_report: bool = False,
) -> dict[str, Any]:
    plan = build_invoiceops_reconciliation_plan(
        frame_id=frame_id,
        invoice_number=invoice_number,
        posting_plan_id=posting_plan_id,
        runtime_data_dir=runtime_data_dir,
        profile=profile,
        fixture_mode=fixture_mode,
    )
    reconciliation = build_invoiceops_reconciliation_result(
        plan,
        runtime_data_dir=runtime_data_dir,
        profile=profile,
        fixture_mode=fixture_mode,
        write_report=False,
    )
    pack = {
        "ok": True,
        "pack_id": f"ACP-{_safe_name(str(reconciliation.get('invoice_number', '') or invoice_number or 'unknown'))}",
        "invoice_number": str(reconciliation.get("invoice_number", "") or ""),
        "supplier_name": str(reconciliation.get("supplier_name", "") or ""),
        "status": str(reconciliation.get("status", "") or "MISSING_POSTING_EVIDENCE"),
        "sections": {
            "invoice_source": collect_invoice_source_evidence(plan, reconciliation),
            "extraction": collect_extraction_evidence(plan, reconciliation),
            "validation": collect_matching_evidence(plan, reconciliation),
            "matching": collect_matching_evidence(plan, reconciliation),
            "posting": collect_posting_evidence(plan, reconciliation),
            "reconciliation": collect_reconciliation_evidence(plan, reconciliation),
            "rollback": collect_rollback_evidence(plan, reconciliation),
            "audit_trail": _collect_audit_trail(plan, reconciliation),
        },
        "conclusion": _build_conclusion(reconciliation),
        "report_paths": {},
        "generated_at": _utc_now(),
        "reconciliation": reconciliation,
    }
    if write_report:
        pack["report_paths"] = write_accounting_evidence_pack(pack, runtime_data_dir=runtime_data_dir)
    return pack


def collect_invoice_source_evidence(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    invoice = dict(plan.get("source_invoice") or {})
    refs = []
    if invoice:
        refs.append(
            {
                "evidence_id": f"INV-{_safe_name(str(invoice.get('invoice_number', '') or invoice.get('invoice_id', 'unknown')))}",
                "source_type": "invoice",
                "source_ref": str(invoice.get("invoice_id", "") or invoice.get("invoice_number", "") or ""),
                "summary": f"Invoice {invoice.get('invoice_number', '')} from {invoice.get('supplier_name', '')}.",
                "details": invoice,
            }
        )
    return refs


def collect_extraction_evidence(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    invoice = dict(plan.get("source_invoice") or {})
    return [
        {
            "evidence_id": f"EXT-{_safe_name(str(invoice.get('invoice_number', '') or 'unknown'))}",
            "source_type": "taskframe_output",
            "source_ref": str(plan.get("frame_id", "") or ""),
            "summary": "Extracted invoice fields and validation results were reviewed.",
            "details": {
                "invoice": invoice,
                "validation": dict(plan.get("source_match_result") or {}),
            },
        }
    ] if invoice else []


def collect_matching_evidence(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    match_result = dict(plan.get("source_match_result") or {})
    if not match_result:
        return []
    return [
        {
            "evidence_id": f"MAT-{_safe_name(str(match_result.get('match_id', '') or 'unknown'))}",
            "source_type": "taskframe_output",
            "source_ref": str(match_result.get("match_id", "") or plan.get("posting_plan_id", "") or ""),
            "summary": f"Match status: {match_result.get('match_status', '')}.",
            "details": match_result,
        }
    ]


def collect_posting_evidence(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    entry = dict(plan.get("posting_ledger_entry") or {})
    if not entry:
        return []
    return [
        {
            "evidence_id": f"POST-{_safe_name(str(entry.get('posting_ledger_id', '') or 'unknown'))}",
            "source_type": "posting_ledger",
            "source_ref": str(entry.get("posting_ledger_id", "") or ""),
            "summary": f"Posting ledger status: {entry.get('status', '')}.",
            "details": entry,
        }
    ]


def collect_reconciliation_evidence(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": f"REC-{_safe_name(str(reconciliation.get('invoice_number', '') or 'unknown'))}",
            "source_type": "reconciliation",
            "source_ref": str(reconciliation.get("invoice_number", "") or ""),
            "summary": f"Final reconciliation status: {reconciliation.get('status', '')}.",
            "details": reconciliation,
        }
    ]


def collect_rollback_evidence(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    rollback_plan = dict((plan.get("rollback_plan") or {}) or {})
    if not rollback_plan:
        return []
    return [
        {
            "evidence_id": f"RBK-{_safe_name(str(rollback_plan.get('rollback_id', '') or 'unknown'))}",
            "source_type": "rollback_plan",
            "source_ref": str(rollback_plan.get("rollback_id", "") or ""),
            "summary": "Rollback plan linked to the posting ledger entry.",
            "details": rollback_plan,
        }
    ]


def write_accounting_evidence_pack(
    pack: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, str]:
    out_dir = ensure_dir(Path(runtime_data_dir) / ACCOUNTING_EVIDENCE_DIR)
    invoice_number = _safe_name(str(pack.get("invoice_number", "") or "unknown_invoice"))
    json_path = out_dir / f"{invoice_number}_accounting_evidence_pack.json"
    md_path = out_dir / f"{invoice_number}_accounting_evidence_pack.md"
    write_json_atomic(json_path, pack)
    md_path.write_text(render_accounting_evidence_markdown(pack), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_accounting_evidence_markdown(report: dict[str, Any]) -> str:
    sections = report.get("sections", {}) if isinstance(report.get("sections", {}), dict) else {}
    lines = [
        "# InvoiceOps Accounting Evidence Pack",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Pack ID | {report.get('pack_id', '')} |",
        f"| Invoice Number | {report.get('invoice_number', '')} |",
        f"| Supplier | {report.get('supplier_name', '')} |",
        f"| Status | {report.get('status', '')} |",
        "",
        "## Conclusion",
        "",
        report.get("conclusion", ""),
        "",
        "## Sections",
        "",
    ]
    for name in ("invoice_source", "extraction", "validation", "matching", "posting", "reconciliation", "rollback", "audit_trail"):
        items = sections.get(name, [])
        lines.append(f"### {name}")
        if not items:
            lines.append("- None")
        else:
            for item in items:
                lines.append(f"- {item.get('summary', '')}")
        lines.append("")
    lines.extend(
        [
            "## Safety Statement",
            "",
            "This evidence pack is read-only. It does not write rows, approve actions, or perform rollback.",
        ]
    )
    return "\n".join(lines)


def _collect_audit_trail(plan: dict[str, Any], reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    trail: list[dict[str, Any]] = []
    source_frame = dict(plan.get("source_frame") or {})
    if source_frame.get("audit"):
        trail.append(
            {
                "evidence_id": f"AUD-{_safe_name(str(plan.get('frame_id', '') or 'unknown'))}",
                "source_type": "taskframe_audit",
                "source_ref": str(plan.get("frame_id", "") or ""),
                "summary": "Source TaskFrame audit trail attached.",
                "details": list(source_frame.get("audit", [])),
            }
        )
    entry = dict(plan.get("posting_ledger_entry") or {})
    if entry:
        trail.append(
            {
                "evidence_id": f"LEDGER-{_safe_name(str(entry.get('posting_ledger_id', '') or 'unknown'))}",
                "source_type": "posting_ledger",
                "source_ref": str(entry.get("posting_ledger_id", "") or ""),
                "summary": "Posting ledger entry attached.",
                "details": entry,
            }
        )
    return trail


def _build_conclusion(reconciliation: dict[str, Any]) -> str:
    status = str(reconciliation.get("status", "") or "")
    if status == "RECONCILED":
        return "The posted accounting rows reconcile and the evidence pack is complete enough for reviewer use."
    if status == "RECONCILED_WITH_WARNINGS":
        return "The posted accounting rows reconcile, but warnings should be reviewed before filing."
    if status == "MANUAL_REVIEW_REQUIRED":
        return "The evidence is incomplete and requires human review."
    if status == "BLOCKED":
        return "The blocked path was preserved and no final ledger mutation is indicated."
    return "The posted rows do not reconcile cleanly; review the blockers before treating the posting as complete."


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value or ""))

