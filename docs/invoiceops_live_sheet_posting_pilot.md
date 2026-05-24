# InvoiceOps Live Sheet Posting Pilot (Spec 156)

## Overview

The InvoiceOps Live Sheet Write Pilot extends the [Spec 155 Live Side-Effect Approval Execution Model](live_side_effect_approval_execution.md) to the InvoiceOps bookkeeping workflow.

It provides a controlled, auditable path for writing verified invoice data to allowlisted Google Sheet registers — with mandatory operator approval, idempotency enforcement, and a full JSONL audit ledger.

**What this pilot does NOT do:**
- Execute any live write automatically
- Approve pending actions on behalf of the operator
- Support batch posting of all actions at once
- Write to blocked targets (supplier master, PO register, payment register, bank register)
- Send live Gmail supplier communications
- Execute live payments
- Mutate supplier/PO/receipt master data
- Auto-rollback executed writes

---

## Allowlisted Registers (v1)

| Register | Target Key | Notes |
|----------|-----------|-------|
| Invoice Register | `invoice_register` | Primary invoice posting target |
| Match Register | `match_register` | 3-way match results |
| Exception Register | `exception_register` | Invoice exceptions and flags |
| Ledger Register | `ledger_register` | Accounting ledger rows |
| Rollback Register | `rollback_register` | Rollback metadata (display-only) |

## Blocked Registers (v1)

| Register | Target Key | Reason |
|----------|-----------|--------|
| Supplier Master | `supplier_master` | Master data — too risky for pilot |
| PO Register | `po_register` | Master data — requires procurement approval |
| Goods Receipt Register | `goods_receipt_register` | Operations data |
| Bank Register | `bank_register` | Financial — blocked entirely |
| Payment Register | `payment_register` | Financial — blocked entirely |

---

## Workflow

```
InvoiceOps Frame (completed)
        │
        ▼
  [1] build_invoiceops_live_posting_plan()
        │  Converts prepared_writes → PENDING_APPROVAL pending actions
        │  Blocks disallowed targets
        │
        ▼
  [2] run_invoiceops_live_posting_preflight()
        │  Plan-level checks
        │
        ▼
  [3] build_invoiceops_posting_approval_pack()
        │  10-item checklist for operator review
        │
        ▼
  [STOP: WAITING_FOR_EXECUTE]
        │
        ▼  (operator reviews approval pack, types confirmation)
        │
  [4] taskframe invoiceops live-posting execute \
        --frame-id <id> --action-id <id> \
        --confirm "EXECUTE LIVE sheet/write_rows <frame_id> <action_id>"
        │
        ▼
  [5] verify_invoiceops_live_posting()
        │
        ▼
  Posting ledger entry (EXECUTED_VERIFIED or EXECUTED_UNVERIFIED)
```

---

## CLI Reference

### Build a posting plan
```bash
taskframe invoiceops live-posting plan \
  --frame-id <frame_id> \
  --invoice-id <id> \
  --invoice-number <number> \
  --supplier-name "<name>" \
  --po-number <po> \
  --match-status matched \
  --json
```

### Run preflight checks
```bash
taskframe invoiceops live-posting preflight \
  --frame-id <frame_id> \
  --json
```

### Build approval pack
```bash
taskframe invoiceops live-posting approval-pack \
  --frame-id <frame_id> \
  --json
```

### Execute one approved action (requires operator confirmation phrase)
```bash
taskframe invoiceops live-posting execute \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --confirm "EXECUTE LIVE sheet/write_rows <frame_id> <action_id>"
```

### Verify last execution
```bash
taskframe invoiceops live-posting verify \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --json
```

### View posting report
```bash
taskframe invoiceops live-posting report
```

---

## Approval Pack — 10-Item Checklist

| # | Item | Required |
|---|------|---------|
| 1 | invoice_validated | Yes |
| 2 | supplier_matched | Yes |
| 3 | po_matched_or_exception_recorded | Yes |
| 4 | receipt_matched_or_exception_recorded | Yes |
| 5 | duplicate_check_passed | Yes |
| 6 | totals_and_tax_checked | Yes |
| 7 | ledger_rows_balanced | Yes |
| 8 | rollback_plan_exists | Yes |
| 9 | target_sheet_and_range_identified | Yes |
| 10 | live_write_confirmation_required | Yes |

---

## Confirmation Phrase

The typed confirmation phrase required for each execute command:

```
EXECUTE LIVE sheet/write_rows <frame_id> <action_id>
```

This phrase is action-specific. It must be typed exactly — case-sensitive.

---

## Audit Ledger

Posting results are recorded in:
```
runtime_data/invoiceops/live_posting/invoiceops_live_posting_ledger.jsonl
runtime_data/invoiceops/live_posting/invoiceops_live_posting_latest.json
```

### Status Values

| Status | Meaning |
|--------|---------|
| `EXECUTED_VERIFIED` | Write succeeded and post-write verification passed |
| `EXECUTED_UNVERIFIED` | Write succeeded but verification checks did not all pass |
| `BLOCKED` | Write was blocked before execution (preflight failure) |
| `FAILED` | Write attempted but failed |

---

## Rollback Plan

Each pending action carries a rollback plan from the prepared write. In v1:

- The rollback plan is **display-only** — it is recorded in the ledger for operator reference
- **Auto-rollback is not implemented in v1**
- To rollback, the operator must manually perform the inverse operation using the rollback plan details

## Post-Write Follow-Up

After an approved posting, run the read-only reconciliation and accounting evidence commands:

```bash
taskframe invoiceops reconcile --invoice-number <number> --json
taskframe invoiceops evidence-pack --invoice-number <number> --write-report --json
```

These follow-up commands do not write rows, do not approve actions, and do not perform rollback. They only collect evidence for review.

---

## Credentials Note

The InvoiceOps Live Sheet Posting Pilot does **not** require real Google credentials for:
- Release verification
- Unit tests
- Approval pack generation
- Posting plan construction
- Preflight checks

Real credentials are only required at the moment of actual `execute` — and only if `dry_run_fallback=False`.

---

## Delegates to Spec 155

All live write execution is delegated to the [Spec 155 Live Side-Effect Approval Execution Model](live_side_effect_approval_execution.md).

`execute_invoiceops_live_sheet_posting()` calls `execute_approved_live_side_effect()` directly — it does not bypass any Spec 155 guardrails.
