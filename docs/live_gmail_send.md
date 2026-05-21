# Approved Live Gmail Send Tool (Spec 133)

## Purpose

Spec 133 implements the first narrow live side-effect tool: `gmail/send`. It builds on the Spec 132 live side-effect execution contract and may only send a real email when all contract checks pass.

---

## Safety constraints

- `demo`, `dev`, `test`, `release`, and `pilot` profiles **never** allow live Gmail sends.
- The `live` profile may allow sends only when the manifest explicitly opts in.
- Gmail sending is **disabled by default** (`enabled: false`).
- No automatic sending. No unapproved sends. No attachments unless the config explicitly enables them.
- Full email body is **never written** to reports or audit logs.

---

## Tool key

`gmail/send`

---

## Tool registry entry

```python
{
    "side_effect": True,
    "requires_approval": True,
    "allow_live": True,
    "allow_live_side_effect": True,
    "live_guardrail": "gmail_send",
}
```

---

## Pending action payload

```json
{
  "action_id": "string",
  "tool": "gmail/send",
  "operation": "side_effect",
  "status": "PENDING_APPROVAL",
  "business_ref": "string",
  "idempotency_key": "string",
  "live_capable": true,
  "payload": {
    "to": ["recipient@example.com"],
    "cc": [],
    "bcc": [],
    "subject": "string",
    "body": "string",
    "attachments": []
  }
}
```

---

## Gmail send config

```json
{
  "gmail_send": {
    "enabled": false,
    "allowed_sender": "",
    "allowed_recipient_domains": [],
    "blocked_recipient_domains": [],
    "max_recipients": 5,
    "allow_attachments": false
  }
}
```

- `enabled` defaults to `false`.
- `allowed_recipient_domains`: only these domains may receive emails. Empty = no restriction.
- `blocked_recipient_domains`: these domains are always rejected.
- `max_recipients`: hard cap on total recipients (to + cc + bcc). Default: 5.
- `allow_attachments`: attachments are disabled by default.

---

## Dry-run execution

Dry-run validates the payload without calling the Gmail API and without sending any email.

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --dry-run
```

Returns:

```json
{
  "ok": true,
  "type": "gmail_send_result",
  "data": {
    "dry_run": true,
    "sent": false,
    "to": ["recipient@example.com"],
    "subject": "Your subject",
    "message_id": ""
  }
}
```

---

## Live execution

All ten Spec 132 preflight checks must pass, plus all gmail_send guardrail checks.

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "LIVE-EXECUTE"
```

Returns on success:

```json
{
  "ok": true,
  "type": "gmail_send_result",
  "data": {
    "dry_run": false,
    "sent": true,
    "to": ["recipient@example.com"],
    "subject": "Your subject",
    "message_id": "msg_abc123"
  }
}
```

---

## Gmail send guardrail checks

The `gmail_send` guardrail verifies:

| Check | Description |
|---|---|
| `action_approved` | Pending action status is `APPROVED` |
| `tool_is_gmail_send` | Tool key is `gmail/send` |
| `tool_allows_live_side_effect` | Tool registry allows live side effects |
| `recipients_not_empty` | `to` list has at least one address |
| `subject_not_empty` | Subject is not blank |
| `body_not_empty` | Body is not blank |
| `business_ref_exists` | Business ref is present |
| `idempotency_key_present` | Idempotency key is present |
| `no_blocked_domains` | No recipient is in the blocked domain list |
| `recipient_domain_allowlist` | All recipients are in the allowed domain list (if configured) |
| `max_recipients` | Total recipients ≤ max_recipients (default 5) |
| `attachments_allowed` | No attachments unless config enables them |

---

## Audit events

| Event | When |
|---|---|
| `LIVE_EMAIL_SENT` | Email was successfully sent |
| `LIVE_EMAIL_SEND_BLOCKED` | Send was blocked at preflight or guardrail |

Audit events are appended to `runtime_data/audit/live_side_effect_audit.jsonl`.

---

## Execution reports

Reports are written to `runtime_data/live_execution/` with the pattern:

```
email_send_<frame_id>_<action_id>_<timestamp>.json
email_send_<frame_id>_<action_id>_<timestamp>.md
```

**The email body is never included in reports.** Reports include: recipients (`to`), subject, message ID, sent status, guardrail result, and idempotency key.

---

## Manifest allowlist

A manifest must explicitly opt in:

```json
{
  "live_execution": {
    "enabled": true,
    "allowed_tools": ["gmail/send"],
    "allowed_actions": ["send_customer_reply"],
    "max_live_actions": 1,
    "requires_operator_confirmation": true
  }
}
```

---

## Out of scope (Spec 133)

- Live Sheets writes
- Live database writes
- Live RPA sending
- Attachments (disabled by default)
- Automatic sending
- Unapproved sends
- Enabling Gmail live send in demo, release, or pilot profiles

---

## Related docs

- [live_side_effect_execution_contract.md](live_side_effect_execution_contract.md) — Spec 132 contract
- [live_execution_safety.md](live_execution_safety.md) — Safety overview
- [runtime_profiles.md](runtime_profiles.md) — Profile restrictions
