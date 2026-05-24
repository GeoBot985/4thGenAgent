# Live Execution Ledger

## Purpose

The live execution ledger is an append-only JSONL log that records every live side-effect execution attempt. It provides idempotency enforcement, audit history, and rollback metadata for the `controlled_live_write` profile.

---

## Storage

**File:** `runtime_data/live_execution/live_execution_ledger.jsonl`

One JSON object per line. Never modified in place — only appended to.

---

## Entry Schema

```json
{
  "ledger_entry_version": "1",
  "recorded_at": "2026-05-24T10:00:00Z",
  "frame_id": "frame_abc",
  "action_id": "action_xyz",
  "tool": "sheet/write_rows",
  "profile": "controlled_live_write",
  "idempotency_key": "ikey_abc123",
  "business_ref": "inv-0042",
  "target_ref": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
  "prepared_payload_hash": "sha256_hex_digest",
  "approved_by": "operator",
  "worker_identity": "worker_1",
  "status": "EXECUTED",
  "rollback_plan": {"action": "delete_rows", "range": "Sheet1!A2:D5"},
  "execution_result": {"ok": true, "rows_written": 3},
  "error": ""
}
```

---

## Status Values

| Status | Meaning |
|---|---|
| `EXECUTING` | In-flight marker written before execution starts |
| `EXECUTED` | Execution completed successfully |
| `FAILED` | Execution attempted but failed |
| `BLOCKED` | Preflight blocked execution before any attempt |

---

## Idempotency Enforcement

`is_idempotency_key_in_ledger(key)` returns `True` only when the key appears with `EXECUTED` status. This prevents duplicate executions:

- `EXECUTING` entries do not block re-execution (allows recovery from crashes)
- `FAILED` entries do not block re-execution (allows retry)
- `BLOCKED` entries do not block re-execution (preflight failure, no execution occurred)

---

## API

### `build_ledger_entry(...)`

Builds a ledger entry dict. Does not write to disk.

### `append_ledger_entry(entry, *, runtime_data_dir)`

Appends a JSON line to the ledger. Creates the file and directory if needed.

### `read_ledger_entries(*, runtime_data_dir)`

Returns all ledger entries as a list of dicts. Returns `[]` if the file does not exist.

### `is_idempotency_key_in_ledger(key, *, runtime_data_dir)`

Returns `True` if the key has been successfully executed (status=EXECUTED).

### `get_ledger_entry(key, *, runtime_data_dir)`

Returns the most recent ledger entry for the given idempotency key, or `None`.

### `hash_payload(payload)`

Returns the SHA-256 hex digest of the canonical JSON representation of a payload. Used to generate `prepared_payload_hash`.

### `build_ledger_report(*, runtime_data_dir, limit)`

Returns a summary report dict: total entries, executed count, failed count, recent entries.

---

## Rollback Plan Storage

The rollback plan is stored as a dict in the ledger entry. It is display-only metadata — no automatic rollback is performed. Use `get_ledger_entry()` to retrieve it by idempotency key.

---

## Audit Trail

The ledger is the primary audit trail for live side-effect executions. In addition, each execution appends an event to:

`runtime_data/audit/live_side_effect_audit.jsonl`

---

## See Also

- [live_side_effect_approval_execution.md](live_side_effect_approval_execution.md) — Execution model
- [live_sheet_write_pilot.md](live_sheet_write_pilot.md) — Sheet write pilot
