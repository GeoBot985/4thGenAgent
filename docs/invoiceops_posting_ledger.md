# InvoiceOps Posting Ledger (Spec 156)

## Overview

The InvoiceOps Posting Ledger is an append-only JSONL audit log for all live InvoiceOps sheet posting operations. It records the outcome of every attempted write — whether executed, blocked, or failed.

**Module:** `runtime/invoiceops_posting_ledger.py`

---

## Storage Paths

```
runtime_data/invoiceops/live_posting/invoiceops_live_posting_ledger.jsonl
runtime_data/invoiceops/live_posting/invoiceops_live_posting_latest.json
```

- **JSONL file**: Append-only. One JSON object per line.
- **Latest pointer**: Overwritten on each write with the most recent entry (for quick status checks).

---

## Status Values

| Status | Meaning |
|--------|---------|
| `EXECUTED_VERIFIED` | Write succeeded AND post-write verification passed |
| `EXECUTED_UNVERIFIED` | Write succeeded but verification did not fully pass |
| `BLOCKED` | Write was blocked by preflight before execution |
| `FAILED` | Write was attempted but failed |
| `PENDING` | Placeholder status (not written to ledger in normal flow) |

---

## Ledger Entry Shape

```json
{
  "posting_ledger_id": "PLG-a1b2c3d4e5f6",
  "frame_id": "frame_invoiceops_pilot_001",
  "posting_plan_id": "PP-abc123def456",
  "invoice_id": "INV-2026-001",
  "invoice_number": "INV-2026-001",
  "supplier_name": "Acme Supplies Ltd",
  "target_register": "invoice_register",
  "action_id": "pa_001",
  "tool": "sheet/write_rows",
  "profile": "controlled_live_write",
  "approved_by": "operator@company.com",
  "worker_identity": {"worker_id": "worker_abc", "model": "claude-sonnet-4-6"},
  "idempotency_key": "abcdef1234567890...",
  "payload_hash": "sha256hexstring...",
  "status": "EXECUTED_VERIFIED",
  "side_effect_performed": true,
  "verification": {"verified": true, "checks": [...]},
  "rollback_plan": {"rollback_id": "rp_001", "steps": [...]},
  "created_at": "2026-05-24T10:00:00Z"
}
```

---

## API Reference

### `build_posting_ledger_entry(**kwargs) -> dict`

Constructs a ledger entry dict with a generated `posting_ledger_id` (UUID-based, prefixed `PLG-`).

Required kwargs: `frame_id`, `posting_plan_id`, `invoice_id`, `invoice_number`, `supplier_name`, `target_register`, `action_id`, `approved_by`, `worker_identity`, `idempotency_key`, `payload_hash`, `status`, `side_effect_performed`.

Optional kwargs: `tool` (default `"sheet/write_rows"`), `profile` (default `"controlled_live_write"`), `verification`, `rollback_plan`.

### `append_posting_ledger_entry(entry, *, runtime_data_dir) -> None`

Appends the entry to the JSONL ledger and updates the latest pointer. Creates the ledger directory if it does not exist.

### `read_posting_ledger_entries(*, runtime_data_dir) -> list[dict]`

Reads all entries from the JSONL ledger. Returns an empty list if the ledger does not exist.

### `get_posting_ledger_entry_by_action(action_id, *, runtime_data_dir) -> dict | None`

Returns the most recent ledger entry for the given `action_id`, or `None`.

### `get_posting_ledger_entry_by_idempotency_key(idempotency_key, *, runtime_data_dir) -> dict | None`

Returns the most recent ledger entry for the given `idempotency_key`, or `None`.

### `build_posting_ledger_report(*, runtime_data_dir, limit=20) -> dict`

Returns a summary report of ledger contents:

```json
{
  "total_entries": 5,
  "executed_verified_count": 3,
  "executed_unverified_count": 1,
  "blocked_count": 1,
  "failed_count": 0,
  "side_effects_performed_count": 4,
  "recent_entries": [...],
  "ledger_path": "runtime_data/invoiceops/live_posting/invoiceops_live_posting_ledger.jsonl"
}
```

### `record_posting_execution(*, posting_plan, action, execution_result, verification, runtime_data_dir) -> dict`

Convenience function: derives status from `execution_result` and `verification`, builds an entry, appends it to the ledger, and returns it.

Status derivation:
- `executed=False` + `blocked=True` → `BLOCKED`
- `executed=False` → `FAILED`
- `executed=True` + `verified=True` → `EXECUTED_VERIFIED`
- `executed=True` + `verified=False` → `EXECUTED_UNVERIFIED`

---

## Idempotency Note

Unlike the Spec 155 live execution ledger, the InvoiceOps posting ledger does **not** enforce re-execution blocking by idempotency key. Idempotency enforcement for InvoiceOps live writes is handled by the Spec 155 `live_execution_ledger` — the InvoiceOps ledger is purely an evidence trail.
