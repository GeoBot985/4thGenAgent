from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIVE_EXECUTION_REPORTS_DIR = "live_execution"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


def get_live_execution_report_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / LIVE_EXECUTION_REPORTS_DIR


def build_live_execution_report(
    *,
    frame_id: str,
    manifest_id: str,
    profile: str,
    action_id: str,
    tool: str,
    business_ref: str,
    idempotency_key: str,
    approval_record: dict[str, Any],
    guardrail_result: dict[str, Any],
    execution_result: dict[str, Any] | None,
    blocked: bool,
    error_code: str | None = None,
    evidence_path: str = "",
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "report_type": "live_execution_attempt",
        "generated_at": _utc_now(),
        "frame_id": frame_id,
        "manifest_id": manifest_id,
        "profile": profile,
        "action_id": action_id,
        "tool": tool,
        "business_ref": business_ref,
        "idempotency_key": idempotency_key,
        "approval_record": approval_record,
        "guardrail_result": guardrail_result,
        "execution_result": execution_result,
        "blocked": blocked,
        "executed": not blocked and execution_result is not None,
        "error_code": error_code or "",
        "evidence_path": evidence_path,
        "preflight": preflight or {},
    }


def _build_report_md(report: dict[str, Any]) -> str:
    blocked = report.get("blocked", True)
    status_line = "BLOCKED" if blocked else "EXECUTED"
    lines = [
        f"# Live Side-Effect Execution Report — {status_line}",
        "",
        f"**Generated:** {report.get('generated_at', '')}",
        f"**Frame ID:** {report.get('frame_id', '')}",
        f"**Manifest ID:** {report.get('manifest_id', '')}",
        f"**Profile:** {report.get('profile', '')}",
        f"**Action ID:** {report.get('action_id', '')}",
        f"**Tool:** {report.get('tool', '')}",
        f"**Business Ref:** {report.get('business_ref', '')}",
        f"**Idempotency Key:** {report.get('idempotency_key', '')}",
        "",
        "## Approval Record",
        "",
    ]
    approval = report.get("approval_record") or {}
    lines.append(f"- Approved by: {approval.get('approved_by', '')}")
    lines.append(f"- Approved at: {approval.get('approved_at', '')}")
    lines.append(f"- Reason: {approval.get('approval_reason', '')}")
    lines += ["", "## Guardrail Result", ""]
    guardrail = report.get("guardrail_result") or {}
    lines.append(f"- Guardrail: {guardrail.get('guardrail', '')}")
    lines.append(f"- OK: {guardrail.get('ok', False)}")
    for check in guardrail.get("checks") or []:
        status = "pass" if check.get("ok") else "FAIL"
        lines.append(f"  - [{status}] {check.get('name', '')}: {check.get('message', '')}")
    lines += ["", "## Execution Result", ""]
    if blocked:
        lines.append(f"**BLOCKED** — error code: `{report.get('error_code', '')}`")
        pf = report.get("preflight") or {}
        for fc in pf.get("failed_checks") or []:
            lines.append(f"- [{fc.get('error_code', '')}] {fc.get('message', '')}")
    else:
        result = report.get("execution_result") or {}
        lines.append(f"- OK: {result.get('ok', False)}")
        lines.append(f"- Type: {result.get('type', '')}")
    lines += ["", "## Evidence", ""]
    lines.append(f"- Evidence path: {report.get('evidence_path', '') or 'n/a'}")
    return "\n".join(lines) + "\n"


def write_live_execution_report(
    report: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    reports_dir = get_live_execution_report_dir(runtime_data_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    frame_id = _safe_slug(str(report.get("frame_id") or "frame"))
    action_id = _safe_slug(str(report.get("action_id") or "action"))
    ts = _timestamp_slug()
    stem = f"{frame_id}_{action_id}_{ts}"

    json_path = reports_dir / f"{stem}.json"
    md_path = reports_dir / f"{stem}.md"

    try:
        json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        md_path.write_text(_build_report_md(report), encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "error_code": "LIVE_EVIDENCE_WRITE_FAILED",
            "message": str(exc),
            "json_path": "",
            "md_path": "",
        }

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def append_live_audit_event(
    event: dict[str, Any],
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> None:
    audit_dir = Path(runtime_data_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_log = audit_dir / "live_side_effect_audit.jsonl"
    with audit_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")
