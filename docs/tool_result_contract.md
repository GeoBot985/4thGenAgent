# Tool Result Contract

Every executed tool call should normalize to a canonical runtime result:

This document defines the canonical result shape used inside the runtime.

```json
{
  "ok": true,
  "type": "example_result",
  "data": {},
  "evidence": {
    "tool": "namespace/action",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": [],
    "output_ref": "example_output"
  },
  "error": "",
  "metadata": {
    "tool": "namespace/action",
    "source": "builtin",
    "mode": "dry_run"
  }
}
```

## Evidence Shape

Evidence is a dictionary, not a list. The minimum fields are:

- `tool`
- `mode`
- `source`
- `operation`
- `input_refs`
- `output_ref`

Safe additions for read-only tools include values such as `query` and `record_count`.

For staged side effects, evidence should include values such as `pending_action_id`, `requires_approval`, and `live_executed`.

For failures, evidence should include `failure_stage` and a safe error code, not secrets or raw credentials.

## Examples

Read-only example:

```json
{
  "ok": true,
  "type": "sheets_range_values",
  "data": {"rows": [["A1"]], "row_count": 1},
  "evidence": {
    "tool": "sheet/read",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": ["spreadsheet_id=demo"],
    "output_ref": "sheet_rows",
    "record_count": 1
  },
  "error": "",
  "metadata": {"tool": "sheet/read", "mode": "dry_run", "source": "builtin"}
}
```

Staged side-effect example:

```json
{
  "ok": true,
  "type": "pending_action",
  "data": {"action_id": "pa_123"},
  "evidence": {
    "tool": "wa/send",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "prepare",
    "input_refs": ["chat=Cornelia"],
    "output_ref": "sent_msg",
    "pending_action_id": "pa_123",
    "requires_approval": true,
    "live_executed": false
  },
  "error": "",
  "metadata": {"tool": "wa/send", "mode": "dry_run", "source": "builtin"}
}
```

Failure example:

```json
{
  "ok": false,
  "type": "sheet_rows",
  "data": {},
  "evidence": {
    "tool": "sheet/read",
    "mode": "dry_run",
    "source": "builtin",
    "operation": "read",
    "input_refs": ["spreadsheet_id=demo"],
    "output_ref": "sheet_rows",
    "failure_stage": "auth_check",
    "safe_error_code": "GOOGLE_AUTH_NOT_CONFIGURED"
  },
  "error": "GOOGLE_AUTH_NOT_CONFIGURED",
  "metadata": {"tool": "sheet/read", "mode": "dry_run", "source": "builtin"}
}
```

## Redaction Rules

- Do not place tokens, credentials, or raw secrets in evidence.
- Do not store full personal message bodies in evidence.
- Prefer IDs, counts, aliases, and safe summaries.

## TaskFrame Audit

The runtime writes tool calls into the TaskFrame with the tool key, result type, ok/error state, input summary, dry-run/live mode, source, and an evidence reference.

The contract runner and release verifier both use this contract as a release gate.
