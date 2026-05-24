# Live Sheet Write Pilot

## Purpose

The sheet write pilot is the v1 implementation of controlled live side-effect execution for TaskFrame. It proves that TaskFrame can perform a governed, approved, idempotency-enforced sheet write operation against a real Google Sheets API while maintaining full audit and rollback metadata.

---

## What the Pilot Covers

- **Only `sheet/write_rows`** — One tool, one spreadsheet operation.
- **Full approval gate** — Operator approval required before any execution.
- **Typed confirmation** — Frame/action/tool-specific phrase required.
- **Idempotency enforcement** — Ledger prevents duplicate executions.
- **Rollback metadata** — Stored in ledger for operator reference.
- **Post-execution verification** — Checks result consistency.
- **Audit trail** — JSONL ledger + audit log.

---

## Profile: `controlled_live_write`

```json
{
  "profile_id": "controlled_live_write",
  "environment": "pilot",
  "allow_live_reads": true,
  "allow_live_side_effects": true,
  "executable_tools": ["sheet/write_rows"],
  "blocked_tool_classes": ["rpa", "send", "delete", "mutation"]
}
```

---

## How to Use

### Step 1 — Prepare the pending action

The pending action must include all extended Spec 155 fields:

```python
pending_action = {
    "frame_id": "my_frame",
    "action_id": "action_001",
    "tool": "sheet/write_rows",
    "status": "APPROVED",
    "approved_by": "operator_name",
    "approved_at": "2026-05-24T10:00:00Z",
    "worker_identity": "worker_pilot_1",
    "idempotency_key": "ikey_pilot_001",
    "business_ref": "inv-0042",
    "target_ref": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
    "prepared_payload_hash": hash_payload(rows_payload),
    "rollback_plan": {
        "action": "delete_rows",
        "range": "Sheet1!A2:D5",
        "note": "Delete the 3 written rows to undo.",
    },
}
```

### Step 2 — Run preflight

```bash
python -m src.taskframe_cli live-side-effect preflight \
  --frame-id my_frame \
  --action-id action_001 \
  --tool sheet/write_rows \
  --profile controlled_live_write \
  --json
```

The preflight output includes the expected confirmation phrase:

```json
{
  "ok": false,
  "confirmation_phrase": "EXECUTE LIVE sheet/write_rows my_frame action_001"
}
```

### Step 3 — Execute with typed confirmation

```bash
python -m src.taskframe_cli live-side-effect execute \
  --frame-id my_frame \
  --action-id action_001 \
  --confirm "EXECUTE LIVE sheet/write_rows my_frame action_001" \
  --json
```

### Step 4 — Verify post-execution

```bash
python -m src.taskframe_cli live-side-effect verify \
  --frame-id my_frame \
  --action-id action_001 \
  --json
```

### Step 5 — Review ledger

```bash
python -m src.taskframe_cli live-side-effect report --json
```

---

## What Remains Blocked in v1

| Tool | Status | Reason |
|---|---|---|
| `gmail/send` | BLOCKED | v1 scope |
| `calendar/create` | BLOCKED | v1 scope |
| `calendar/update` | BLOCKED | v1 scope |
| `calendar/delete` | BLOCKED | v1 scope |
| `rpa/*` | BLOCKED | v1 scope |

---

## Guardrail Constraints (from sheet_write_tool)

- Maximum 50 rows per action
- Spreadsheet ID must be in the allowed list (if configured)
- Range must be in the allowed list (if configured)
- `business_ref` required
- `idempotency_key` required

---

## Credentials

Live execution requires:

- `credentials.json` — OAuth2 client credentials
- `token.json` — Valid OAuth2 token with Sheets write scope (`https://www.googleapis.com/auth/spreadsheets`)

Release verification does **not** require credentials — it uses boundary-only checks.

---

## Reports

Execution evidence is written to:

- `runtime_data/live_execution/<frame>_<action>_<timestamp>.json`
- `runtime_data/live_execution/<frame>_<action>_<timestamp>.md`
- `runtime_data/live_execution/live_execution_ledger.jsonl` (JSONL append)
- `runtime_data/audit/live_side_effect_audit.jsonl` (JSONL append)

---

## Safety Statement

> Only `sheet/write_rows` is executable in this pilot.
> All other side-effect tools are blocked at the policy level.
> No automatic rollback is performed.
> All executions require operator approval and typed confirmation.
> All executions are idempotency-enforced and audit-logged.

---

## See Also

- [live_side_effect_approval_execution.md](live_side_effect_approval_execution.md) — Execution model
- [live_execution_ledger.md](live_execution_ledger.md) — Ledger storage
- [governed_live_read_proof.md](governed_live_read_proof.md) — Live read proof
