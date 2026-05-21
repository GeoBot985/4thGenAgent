# Live Side-Effect Execution Contract (Spec 132)

## Purpose

This document defines the first safe, narrow contract for executing approved live side effects in TaskFrame.

**This spec does not add live email, Sheets, database, or RPA writes.** It creates the common execution rules that later live-write tools must obey.

---

## Default: disabled

Live side effects are **disabled by default**.

```json
{
  "live_side_effect_execution": {
    "enabled": false,
    "default_dry_run": true
  }
}
```

No existing demo, release, pilot, or portfolio workflow performs live side effects because of this spec.

---

## Execution preflight gate

Before any live side effect executes, all ten checks must pass:

| Check | Error code |
|---|---|
| `dry_run == false` explicitly supplied | `LIVE_SIDE_EFFECTS_DISABLED` |
| Active profile allows live side effects | `LIVE_PROFILE_NOT_ALLOWED` |
| Manifest allowlist enables the tool | `LIVE_MANIFEST_NOT_ALLOWED` |
| Tool registry allows live side effects | `LIVE_TOOL_NOT_ALLOWED` |
| Pending action status is `APPROVED` | `PENDING_ACTION_NOT_APPROVED` |
| Approval record (`approved_by` + `approved_at`) exists | `PENDING_ACTION_NOT_APPROVED` |
| Idempotency key is present | `IDEMPOTENCY_KEY_REQUIRED` |
| Idempotency key has not been used before | `DUPLICATE_SIDE_EFFECT_BLOCKED` |
| Tool-specific guardrail is specified (not `blocked`) | `LIVE_GUARDRAIL_FAILED` |
| Typed confirmation `LIVE-EXECUTE` provided (when required) | `TYPED_CONFIRMATION_REQUIRED` |

If any check fails, execution is blocked and a `LIVE_SIDE_EFFECT_BLOCKED` audit event is written.

---

## Profile restrictions

Live side effects are unconditionally blocked in these profiles:

| Profile | Side effects allowed |
|---|---|
| `demo` | No |
| `dev` | No |
| `test` | No |
| `release` | No |
| `pilot` | No (read-only) |
| `live` | Only with explicit allowlists + guardrail + approval |

---

## Manifest live allowlist

Manifests must explicitly opt in:

```json
{
  "live_execution": {
    "enabled": false,
    "allowed_tools": ["gmail/send"],
    "allowed_actions": ["send_customer_reply"],
    "max_live_actions": 1,
    "requires_operator_confirmation": true
  }
}
```

- `enabled` defaults to `false` — must be explicitly set to `true`
- Only tools listed in `allowed_tools` may execute live
- Only actions listed in `allowed_actions` are permitted (empty list = no restriction)
- `max_live_actions` caps the number of live side effects per run
- Approval-state completion still works even when live execution is disabled

---

## Tool registry requirements

A tool may execute live side effects only when its registry entry explicitly sets:

```json
{
  "side_effect": true,
  "requires_approval": true,
  "allow_live": true,
  "allow_live_side_effect": true,
  "live_guardrail": "specific_guardrail_name"
}
```

A tool with `allow_live_side_effect: false` is blocked even if the manifest allows it.

---

## Pending action live fields

Every live-capable pending action must carry:

```json
{
  "action_id": "string",
  "tool": "gmail/send",
  "operation": "side_effect",
  "status": "PENDING_APPROVAL",
  "approval_required": true,
  "approved_by": "",
  "approved_at": "",
  "idempotency_key": "string",
  "business_ref": "string",
  "live_capable": true,
  "live_executed": false,
  "live_executed_at": "",
  "dry_run_executed": false,
  "guardrail_result": null
}
```

Pending actions without `live_capable: true` remain dry-run only.

---

## Guardrail interface

Every live-capable tool must declare a guardrail function:

```python
def check_live_side_effect_guardrail(action, frame, profile, tool_spec) -> dict:
    return {
        "ok": True,
        "guardrail": "gmail_send_guardrail",
        "reason": "",
        "checks": []
    }
```

The guardrail result is recorded in the pending action before execution proceeds.

---

## CLI usage

### Dry-run (default and safe)

```bash
taskframe execute-approved --frame-id <frame_id> --action-id <action_id> --dry-run
```

### Live execution (requires all gates)

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "LIVE-EXECUTE"
```

Without `--confirm LIVE-EXECUTE` the command fails with `TYPED_CONFIRMATION_REQUIRED`.

---

## Audit records

**Executed:**
```json
{
  "event_type": "LIVE_SIDE_EFFECT_EXECUTED",
  "frame_id": "string",
  "action_id": "string",
  "tool": "string",
  "idempotency_key": "string",
  "approved_by": "string",
  "executed_at": "timestamp",
  "guardrail_result": {},
  "result_ref": "string"
}
```

**Blocked:**
```json
{
  "event_type": "LIVE_SIDE_EFFECT_BLOCKED",
  "reason": "string",
  "error_code": "string"
}
```

Audit events are appended to `runtime_data/audit/live_side_effect_audit.jsonl`.

---

## Execution reports

Every live execution attempt (blocked or executed) produces:

```
runtime_data/live_execution/<frame_id>_<action_id>_<timestamp>.json
runtime_data/live_execution/<frame_id>_<action_id>_<timestamp>.md
```

---

## What this spec does NOT do

- Does not implement live Sheets write
- Does not implement live database writes
- Does not enable live RPA mutation
- Does not add background live execution
- Does not add automatic approval
- Does not allow live side effects in pilot mode
- Does not claim full production readiness

## Spec 133 — First live tool: gmail/send

Spec 133 implements `gmail/send` as the first live side-effect tool built on this contract.

- `gmail/send` requires all 10 preflight checks from this contract to pass.
- Additional `gmail_send` guardrail checks run after preflight.
- Gmail sending is disabled by default and blocked in all non-`live` profiles.
- Email body is never included in reports.

See [live_gmail_send.md](live_gmail_send.md) for the full Spec 133 documentation.

## Spec 134 — Second live tool: sheet/write_rows

Spec 134 implements `sheet/write_rows` as the second narrow live side-effect tool built on this contract.

- `sheet/write_rows` requires all 10 preflight checks from this contract to pass.
- Additional `sheet_write_rows_guardrail` checks run after preflight, including spreadsheet/range allowlist enforcement.
- Sheets live writing is disabled by default (`enabled: false`) and blocked in all non-`live` profiles.
- Row payloads are never written to summary reports or audit logs.
- `append` mode is the default safe write mode. `update` mode is disabled by default.
- Spreadsheet ID and range/tab allowlists are mandatory for live writes.

See [live_google_sheets_write.md](live_google_sheets_write.md) for the full Spec 134 documentation.
