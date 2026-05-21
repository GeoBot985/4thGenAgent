# Approved Live Google Sheets Write Tool (Spec 134)

## Purpose

Spec 134 implements the second narrow live side-effect tool: `sheet/write_rows`. It builds on the Spec 132 live side-effect execution contract and follows the same safety pattern as Spec 133 (Gmail live send).

Live Google Sheets writing may only execute when all contract checks pass. **Default behaviour remains dry-run and safe.**

---

## Safety constraints

- `demo`, `dev`, `test`, `release`, and `pilot` profiles **never** allow live Sheets writes.
- The `live` profile may allow writes only when the manifest explicitly opts in.
- Google Sheets writing is **disabled by default** (`enabled: false`).
- No automatic writes. No unapproved writes. No spreadsheet mutations without an explicit allowlist.
- Full row payloads are **never written** to summary reports or audit logs. Reports include row count, headers, target range, and evidence references only.
- `update` mode is **disabled by default**. Only `append` mode is enabled.

---

## Tool key

`sheet/write_rows`

---

## Tool registry entry

```python
{
    "namespace": "sheet",
    "action": "write_rows",
    "side_effect": True,
    "requires_approval": True,
    "allow_live": True,
    "allow_live_side_effect": True,
    "live_guardrail": "sheet_write_rows_guardrail",
    "output_type": "sheet_write_result",
}
```

---

## Pending action payload

```json
{
  "action_id": "string",
  "tool": "sheet/write_rows",
  "operation": "side_effect",
  "status": "PENDING_APPROVAL",
  "business_ref": "string",
  "idempotency_key": "string",
  "live_capable": true,
  "payload": {
    "spreadsheet_id": "string",
    "range_name": "ExceptionRegister!A:H",
    "rows": [],
    "write_mode": "append",
    "expected_headers": [],
    "source_ref": "string"
  }
}
```

### Required payload fields

| Field | Description |
|---|---|
| `spreadsheet_id` | Google Sheets spreadsheet ID |
| `range_name` | Target range or tab (e.g. `ExceptionRegister!A:H`) |
| `rows` | 2D list of values to write |
| `write_mode` | `append` or `update` (see supported modes) |
| `business_ref` | Business entity reference (e.g. invoice ref) |
| `idempotency_key` | Unique key to prevent duplicate writes |

---

## Supported write modes

| Mode | Meaning | Default enabled |
|---|---|---|
| `append` | Append rows to an approved range/table | Yes |
| `update` | Update an explicitly approved range | No (disabled by default) |

**Preferred mode: `append`.** Use `append` for low-risk operational writes such as register entries.

`update` mode must be explicitly enabled in the `sheet_write` config. It is not enabled in demo, release, or pilot profiles.

---

## Configuration defaults

```json
{
  "sheet_write": {
    "enabled": false,
    "allowed_spreadsheets": [],
    "allowed_ranges": [],
    "blocked_ranges": [],
    "max_rows_per_action": 50,
    "allow_update_mode": false,
    "allow_append_mode": true
  }
}
```

No demo, release, or pilot profile may enable live Sheets writing by default.

To enable for an approved `live` profile:

```json
{
  "sheet_write": {
    "enabled": true,
    "allowed_spreadsheets": ["<your-spreadsheet-id>"],
    "allowed_ranges": ["ExceptionRegister!A:H"],
    "max_rows_per_action": 50,
    "allow_append_mode": true,
    "allow_update_mode": false
  }
}
```

---

## Guardrail: `sheet_write_rows_guardrail`

The Sheets write guardrail is executed after preflight and before the API call. It re-validates the operation in the context of the specific tool's constraints.

| Check | Description |
|---|---|
| `action_approved` | Pending action status must be `APPROVED` |
| `tool_is_sheet_write_rows` | Tool must be `sheet/write_rows` |
| `tool_allows_live_side_effect` | Tool spec must set `allow_live_side_effect: true` |
| `sheet_write_config_enabled` | Config must have `sheet_write.enabled: true` |
| `spreadsheet_id_present` | Spreadsheet ID must not be empty |
| `spreadsheet_id_allowlisted` | Spreadsheet ID must be in `allowed_spreadsheets` (if configured) |
| `range_allowlisted` | Range must be in `allowed_ranges` (if configured) |
| `range_not_blocked` | Range must not be in `blocked_ranges` |
| `write_mode_supported` | Write mode must be enabled in config |
| `rows_not_empty` | Row list must not be empty |
| `row_count_within_limit` | Row count must not exceed `max_rows_per_action` |
| `column_count_matches_headers` | Column count must match `expected_headers` (if supplied) |
| `business_ref_exists` | `business_ref` must be present |
| `idempotency_key_present` | `idempotency_key` must be present |

---

## Dry-run behaviour

Dry-run is the **default**. A dry-run validates the write request without calling Google Sheets.

```json
{
  "ok": true,
  "type": "sheet_write_result",
  "data": {
    "dry_run": true,
    "written": false,
    "spreadsheet_id": "string",
    "range_name": "string",
    "write_mode": "append",
    "row_count": 3,
    "updated_range": ""
  },
  "evidence": {},
  "error": ""
}
```

Dry-run:
- validates payload shape
- validates row count against `max_rows_per_action`
- does not call Google Sheets API
- marks action as `dry_run_executed`
- preserves existing fixture/demo behaviour

---

## Live write execution

Live write may only execute via the Spec 132 CLI command:

```
taskframe execute-approved <frame_id> --action <action_id> --live --confirm LIVE-EXECUTE
```

A successful live write result:

```json
{
  "ok": true,
  "type": "sheet_write_result",
  "data": {
    "dry_run": false,
    "written": true,
    "spreadsheet_id": "string",
    "range_name": "ExceptionRegister!A:H",
    "write_mode": "append",
    "row_count": 3,
    "updated_range": "ExceptionRegister!A42:H44"
  },
  "evidence": {},
  "error": ""
}
```

---

## Idempotency

Before writing, the system checks:

- No executed action has the same `idempotency_key`
- No Sheets write report has the same `idempotency_key`
- The current pending action has not already been live-executed
- The same `business_ref` has not been written to the same target range by the same action type

Duplicate writes are blocked with error code `DUPLICATE_SIDE_EFFECT_BLOCKED`. No write is made.

---

## Audit events

### On successful write

```json
{
  "event_type": "LIVE_SHEET_ROWS_WRITTEN",
  "frame_id": "string",
  "action_id": "string",
  "tool": "sheet/write_rows",
  "idempotency_key": "string",
  "business_ref": "string",
  "spreadsheet_id": "string",
  "range_name": "string",
  "updated_range": "string",
  "row_count": 0,
  "approved_by": "string",
  "executed_at": "timestamp"
}
```

### On blocked write

```json
{
  "event_type": "LIVE_SHEET_WRITE_BLOCKED",
  "error_code": "string",
  "reason": "string"
}
```

---

## Reports

Reports are written to:

```
runtime_data/live_execution/sheet_write_<frame_id>_<action_id>_<timestamp>.json
runtime_data/live_execution/sheet_write_<frame_id>_<action_id>_<timestamp>.md
```

Reports include:

- Frame ID, manifest ID, profile
- Action ID, spreadsheet ID, range name, write mode
- Row count, updated range, business reference, idempotency key
- Approval record and guardrail result
- Blocked/executed status

**Row payloads are not included in reports.** Reports reference row count, expected headers, and target range only.

---

## Inspecting evidence and reports

After a live write, inspect:

```
runtime_data/live_execution/sheet_write_*.json   # Full JSON evidence
runtime_data/live_execution/sheet_write_*.md     # Human-readable summary
runtime_data/audit/live_side_effect_audit.jsonl  # Audit event stream
```

---

## First supported business use case

**Invoice exception register append**

Append an exception row for an invoice with a PO mismatch:

```python
action = build_sheet_write_pending_action(
    action_id="pa-inv-001",
    business_ref="INV-10042",
    idempotency_key="inv-10042-exception-append-001",
    spreadsheet_id="<your-spreadsheet-id>",
    range_name="ExceptionRegister!A:H",
    rows=[
        ["INV-10042", "PO mismatch", "Supplier invoice total differs from PO", "open"]
    ],
    write_mode="append",
)
```

This use case is appropriate for low-risk operational writes. Irreversible accounting ledger posting is **out of scope** for Spec 134 and requires a separately approved spec.

---

## Out of scope

- Live database writes
- Live RPA writes
- Irreversible ledger posting
- Update mode enabled by default
- Row deletion or range clearing
- Broad spreadsheet mutation
- Unapproved writes
- Live Sheets write in demo, release, or pilot profiles

---

## Reference

- Spec 132: `docs/live_side_effect_execution_contract.md` — base contract and preflight gate
- Spec 133: `docs/live_gmail_send.md` — first live side-effect tool (pattern reference)
- Tool registry: `runtime/tool_registry.py`
- Guardrail: `runtime/live_guardrails.py` — `guardrail_sheet_write_rows`
- Implementation: `runtime/sheet_write_tool.py`
