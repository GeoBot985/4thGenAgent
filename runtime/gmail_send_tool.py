from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .live_side_effect_contract import (
    mark_pending_action_dry_run_executed,
    mark_pending_action_live_capable,
    mark_pending_action_live_executed,
    run_live_side_effect_preflight,
)


GMAIL_SEND_TOOL_KEY = "gmail/send"

GMAIL_SEND_DEFAULT_CONFIG: dict[str, Any] = {
    "gmail_send": {
        "enabled": False,
        "allowed_sender": "",
        "allowed_recipient_domains": [],
        "blocked_recipient_domains": [],
        "max_recipients": 5,
        "allow_attachments": False,
    }
}

GMAIL_SEND_AUDIT_EVENT_EXECUTED = "LIVE_EMAIL_SENT"
GMAIL_SEND_AUDIT_EVENT_BLOCKED = "LIVE_EMAIL_SEND_BLOCKED"


def normalize_gmail_send_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(GMAIL_SEND_DEFAULT_CONFIG["gmail_send"])
    if config is None:
        return base
    section = config.get("gmail_send")
    if not isinstance(section, dict):
        return base
    merged = dict(base)
    for key in base:
        if key in section:
            merged[key] = section[key]
    return merged


def build_gmail_send_pending_action(
    *,
    action_id: str,
    business_ref: str,
    idempotency_key: str,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[Any] | None = None,
    approved_by: str = "",
    approved_at: str = "",
    status: str = "PENDING_APPROVAL",
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "action_id": action_id,
        "tool": GMAIL_SEND_TOOL_KEY,
        "operation": "side_effect",
        "status": status,
        "business_ref": business_ref,
        "idempotency_key": idempotency_key,
        "live_capable": True,
        "live_executed": False,
        "live_executed_at": "",
        "dry_run_executed": False,
        "guardrail_result": None,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "payload": {
            "to": list(to),
            "cc": list(cc or []),
            "bcc": list(bcc or []),
            "subject": subject,
            "body": body,
            "attachments": list(attachments or []),
        },
    }
    mark_pending_action_live_capable(action)
    return action


def validate_gmail_send_payload(
    payload: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = normalize_gmail_send_config(config)
    errors: list[str] = []

    to_list = list(payload.get("to") or [])
    cc_list = list(payload.get("cc") or [])
    bcc_list = list(payload.get("bcc") or [])
    subject = str(payload.get("subject") or "").strip()
    body = str(payload.get("body") or "").strip()
    attachments = list(payload.get("attachments") or [])

    if not to_list:
        errors.append("to: recipient list must not be empty.")
    if not subject:
        errors.append("subject: must not be empty.")
    if not body:
        errors.append("body: must not be empty.")

    all_recipients = to_list + cc_list + bcc_list
    max_recipients = int(cfg.get("max_recipients") or 5)
    if len(all_recipients) > max_recipients:
        errors.append(
            f"recipients: total recipients ({len(all_recipients)}) exceeds max ({max_recipients})."
        )

    blocked_domains = [d.lower() for d in (cfg.get("blocked_recipient_domains") or [])]
    if blocked_domains:
        for addr in all_recipients:
            domain = addr.split("@")[-1].lower() if "@" in addr else ""
            if domain in set(blocked_domains):
                errors.append(f"recipients: domain '{domain}' is blocked.")
                break

    allowed_domains = [d.lower() for d in (cfg.get("allowed_recipient_domains") or [])]
    if allowed_domains:
        for addr in all_recipients:
            domain = addr.split("@")[-1].lower() if "@" in addr else ""
            if domain not in set(allowed_domains):
                errors.append(f"recipients: domain '{domain}' is not in the allowlist.")
                break

    if attachments and not cfg.get("allow_attachments"):
        errors.append("attachments: attachments are not enabled in the Gmail send config.")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "to": to_list,
        "cc": cc_list,
        "bcc": bcc_list,
        "subject": subject,
        "body": body,
        "recipient_count": len(all_recipients),
        "attachment_count": len(attachments),
    }


def gmail_send_dry_run(
    pending_action: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(pending_action.get("payload") or {})
    validation = validate_gmail_send_payload(payload, config=config)
    mark_pending_action_dry_run_executed(pending_action)
    if not validation["ok"]:
        return {
            "ok": False,
            "type": "gmail_send_result",
            "error": "; ".join(validation["errors"]),
            "data": {
                "dry_run": True,
                "sent": False,
                "to": validation["to"],
                "subject": validation["subject"],
                "message_id": "",
            },
        }
    return {
        "ok": True,
        "type": "gmail_send_result",
        "data": {
            "dry_run": True,
            "sent": False,
            "to": validation["to"],
            "subject": validation["subject"],
            "message_id": "",
        },
    }


def _gmail_api_send(
    *,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    subject: str,
    body: str,
    sender: str = "",
) -> dict[str, Any]:
    try:
        import base64
        from email.message import EmailMessage

        from googleapiclient.errors import HttpError

        from tools.google_auth import build_service
    except ImportError as exc:
        return {"ok": False, "error": f"Gmail API unavailable: {exc}", "message_id": ""}

    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject
    if sender:
        msg["From"] = sender
    msg.set_content(body)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    try:
        service = build_service("gmail", "v1")
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {
            "ok": True,
            "message_id": str(sent.get("id") or ""),
            "thread_id": str(sent.get("threadId") or ""),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "message_id": ""}


def gmail_send_live_execute(
    pending_action: dict[str, Any],
    tool_spec: dict[str, Any],
    *,
    manifest_live_execution: dict[str, Any] | None = None,
    profile_name: str = "demo",
    profile_data: dict[str, Any] | None = None,
    executed_actions: list[dict[str, Any]] | None = None,
    confirmation: str | None = None,
    config: dict[str, Any] | None = None,
    _gmail_api_send_fn: Any = None,
) -> dict[str, Any]:
    preflight = run_live_side_effect_preflight(
        pending_action=pending_action,
        tool_spec=tool_spec,
        manifest_live_execution=manifest_live_execution,
        profile_name=profile_name,
        profile_data=profile_data,
        executed_actions=executed_actions,
        dry_run=False,
        confirmation=confirmation,
    )

    if not preflight["ok"]:
        return {
            "ok": False,
            "type": "gmail_send_result",
            "blocked": True,
            "error_code": preflight.get("error_code"),
            "preflight": preflight,
            "data": {
                "dry_run": False,
                "sent": False,
                "to": [],
                "subject": "",
                "message_id": "",
            },
        }

    from .live_guardrails import guardrail_gmail_send

    payload = dict(pending_action.get("payload") or {})
    guardrail_result = guardrail_gmail_send(pending_action, tool_spec, config=config)
    if not guardrail_result["ok"]:
        return {
            "ok": False,
            "type": "gmail_send_result",
            "blocked": True,
            "error_code": "LIVE_GUARDRAIL_FAILED",
            "guardrail_result": guardrail_result,
            "data": {
                "dry_run": False,
                "sent": False,
                "to": list(payload.get("to") or []),
                "subject": str(payload.get("subject") or ""),
                "message_id": "",
            },
        }

    cfg = normalize_gmail_send_config(config)
    validation = validate_gmail_send_payload(payload, config=config)
    if not validation["ok"]:
        return {
            "ok": False,
            "type": "gmail_send_result",
            "blocked": True,
            "error": "; ".join(validation["errors"]),
            "data": {
                "dry_run": False,
                "sent": False,
                "to": validation["to"],
                "subject": validation["subject"],
                "message_id": "",
            },
        }

    send_fn = _gmail_api_send_fn or _gmail_api_send
    send_result = send_fn(
        to=validation["to"],
        cc=validation["cc"],
        bcc=validation["bcc"],
        subject=validation["subject"],
        body=validation["body"],
        sender=str(cfg.get("allowed_sender") or ""),
    )

    if not send_result.get("ok"):
        return {
            "ok": False,
            "type": "gmail_send_result",
            "blocked": False,
            "error": send_result.get("error", "Gmail API error."),
            "data": {
                "dry_run": False,
                "sent": False,
                "to": validation["to"],
                "subject": validation["subject"],
                "message_id": "",
            },
        }

    message_id = str(send_result.get("message_id") or "")
    mark_pending_action_live_executed(pending_action, guardrail_result)
    pending_action["message_id"] = message_id

    return {
        "ok": True,
        "type": "gmail_send_result",
        "blocked": False,
        "guardrail_result": guardrail_result,
        "data": {
            "dry_run": False,
            "sent": True,
            "to": validation["to"],
            "subject": validation["subject"],
            "message_id": message_id,
        },
    }


def build_gmail_send_report(
    *,
    frame_id: str,
    action_id: str,
    to: list[str],
    subject: str,
    message_id: str = "",
    sent: bool = False,
    blocked: bool = False,
    error_code: str = "",
    guardrail_result: dict[str, Any] | None = None,
    idempotency_key: str = "",
    business_ref: str = "",
    approved_by: str = "",
) -> dict[str, Any]:
    # email body is intentionally excluded from reports
    return {
        "report_type": "gmail_send_attempt",
        "generated_at": _utc_now(),
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": GMAIL_SEND_TOOL_KEY,
        "to": to,
        "subject": subject,
        "message_id": message_id,
        "sent": sent,
        "blocked": blocked,
        "error_code": error_code,
        "guardrail_result": guardrail_result or {},
        "idempotency_key": idempotency_key,
        "business_ref": business_ref,
        "approval_record": {"approved_by": approved_by},
    }


def write_gmail_send_report(
    report: dict[str, Any],
    *,
    runtime_data_dir: str = "runtime_data",
) -> dict[str, Any]:
    from pathlib import Path
    import json

    reports_dir = Path(runtime_data_dir) / "live_execution"
    reports_dir.mkdir(parents=True, exist_ok=True)

    frame_id = _safe_slug(str(report.get("frame_id") or "frame"))
    action_id = _safe_slug(str(report.get("action_id") or "action"))
    ts = _timestamp_slug()
    stem = f"email_send_{frame_id}_{action_id}_{ts}"

    json_path = reports_dir / f"{stem}.json"
    md_path = reports_dir / f"{stem}.md"

    try:
        json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        md_path.write_text(_build_gmail_report_md(report), encoding="utf-8")
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


def _build_gmail_report_md(report: dict[str, Any]) -> str:
    blocked = report.get("blocked", True)
    sent = report.get("sent", False)
    if sent:
        status_line = "SENT"
    elif blocked:
        status_line = "BLOCKED"
    else:
        status_line = "DRY-RUN"

    lines = [
        f"# Gmail Send Report — {status_line}",
        "",
        f"**Generated:** {report.get('generated_at', '')}",
        f"**Frame ID:** {report.get('frame_id', '')}",
        f"**Action ID:** {report.get('action_id', '')}",
        f"**Tool:** {report.get('tool', '')}",
        f"**Business Ref:** {report.get('business_ref', '')}",
        f"**Idempotency Key:** {report.get('idempotency_key', '')}",
        "",
        "## Recipients",
        "",
    ]
    for addr in (report.get("to") or []):
        lines.append(f"- {addr}")
    lines += [
        "",
        f"**Subject:** {report.get('subject', '')}",
        "",
        "_(Email body is not included in this report for security reasons.)_",
        "",
        "## Result",
        "",
        f"- Message ID: {report.get('message_id', '') or 'n/a'}",
        f"- Sent: {sent}",
        f"- Blocked: {blocked}",
    ]
    if report.get("error_code"):
        lines.append(f"- Error Code: {report.get('error_code', '')}")
    approval = report.get("approval_record") or {}
    lines += [
        "",
        "## Approval",
        "",
        f"- Approved by: {approval.get('approved_by', '')}",
    ]
    guardrail = report.get("guardrail_result") or {}
    if guardrail:
        lines += ["", "## Guardrail", ""]
        lines.append(f"- Guardrail: {guardrail.get('guardrail', '')}")
        lines.append(f"- OK: {guardrail.get('ok', False)}")
        for check in guardrail.get("checks") or []:
            status = "pass" if check.get("ok") else "FAIL"
            lines.append(f"  - [{status}] {check.get('name', '')}: {check.get('message', '')}")
    return "\n".join(lines) + "\n"


def build_gmail_send_audit_event(
    *,
    event_type: str,
    frame_id: str,
    action_id: str,
    idempotency_key: str,
    to: list[str],
    subject: str,
    message_id: str = "",
    reason: str = "",
    error_code: str = "",
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "frame_id": frame_id,
        "action_id": action_id,
        "tool": GMAIL_SEND_TOOL_KEY,
        "idempotency_key": idempotency_key,
        "to": to,
        "subject": subject,
        "message_id": message_id,
        "reason": reason,
        "error_code": error_code,
        "recorded_at": _utc_now(),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)
