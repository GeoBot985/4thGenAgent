# InvoiceOps Posting Approval Pack (Spec 156)

## Overview

The InvoiceOps Posting Approval Pack is a structured document generated for operator review **before** any live InvoiceOps sheet write is approved. It does not approve actions — it provides the information the operator needs to make an informed decision.

**Module:** `runtime/invoiceops_posting_approval_pack.py`

---

## Building an Approval Pack

```python
from runtime.invoiceops_posting_approval_pack import build_invoiceops_posting_approval_pack

pack = build_invoiceops_posting_approval_pack(
    posting_plan=posting_plan,          # Required — from build_invoiceops_live_posting_plan()
    invoice=invoice_dict,               # Optional — enriches checklist
    match_result=match_result_dict,     # Optional — enriches risk summary
    exceptions=list_of_exceptions,      # Optional — enriches checklist
)
```

---

## Approval Pack Shape

```json
{
  "ok": false,
  "invoice_id": "INV-2026-001",
  "invoice_number": "INV-2026-001",
  "supplier_name": "Acme Supplies Ltd",
  "po_number": "PO-2026-042",
  "frame_id": "frame_001",
  "posting_plan_id": "PP-abc123",
  "match_status": "matched",
  "pending_actions": [...],
  "human_summary": "Invoice INV-2026-001 from Acme Supplies Ltd (PO: PO-2026-042) — match status: matched. 1 write(s) eligible for live posting. 1 pending action(s) await operator approval.",
  "risk_summary": ["No significant risks identified."],
  "approval_checklist": [...],
  "rollback_summary": [...],
  "report_refs": ["invoice:INV-2026-001", "posting_plan:PP-abc123"],
  "generated_at": "2026-05-24T10:00:00Z"
}
```

### `ok` field

`ok` is `True` only when all **required** checklist items pass. It does NOT mean actions are approved — it means the checklist is clear for the operator to proceed with their approval decision.

---

## Approval Checklist Items

All 10 items are required. `ok` is `False` if any required item fails.

| # | Item Key | What It Checks |
|---|----------|---------------|
| 1 | `invoice_validated` | invoice_id or invoice_number present |
| 2 | `supplier_matched` | supplier_name or supplier_id present |
| 3 | `po_matched_or_exception_recorded` | po_number exists or PO exception recorded |
| 4 | `receipt_matched_or_exception_recorded` | receipt check passed or missing_receipt exception |
| 5 | `duplicate_check_passed` | No duplicate_invoice exception |
| 6 | `totals_and_tax_checked` | invoice_total or subtotal present |
| 7 | `ledger_rows_balanced` | match_status is matched, exception, or unknown |
| 8 | `rollback_plan_exists` | posting_plan has rollback_plans |
| 9 | `target_sheet_and_range_identified` | posting_plan has write_targets |
| 10 | `live_write_confirmation_required` | Always passes — reminder that typed phrase is required |

Each checklist item shape:

```json
{
  "item": "invoice_validated",
  "passed": true,
  "note": "",
  "required": true
}
```

---

## Risk Summary

The risk summary is a list of human-readable risk statements:

| Condition | Level | Message |
|-----------|-------|---------|
| `match_status == "blocked"` | CRITICAL | Ledger writes are prohibited |
| `match_status == "exception"` | WARNING | Review exceptions before posting |
| High/blocker severity exceptions | HIGH | Per-exception message |
| Blocked writes in plan | INFO | Count of blocked writes |
| No risks | — | "No significant risks identified." |

---

## Rollback Summary

The rollback summary extracts rollback plan metadata from the posting plan:

```json
[
  {
    "rollback_id": "rp_001",
    "target": "invoice_register",
    "rollback_type": "delete_row",
    "safe_to_auto_prepare": false,
    "reason": "Row append — reversible by deletion"
  }
]
```

Rollback is **display-only** in v1. The operator must perform rollback manually.

---

## Human Summary

A single-line plain-English summary of the posting situation, for quick operator scan:

```
Invoice INV-2026-001 from Acme Supplies Ltd (PO: PO-2026-042) — match status: matched.
1 write(s) eligible for live posting. 1 pending action(s) await operator approval.
```

---

## What the Approval Pack Does NOT Do

- It does NOT approve any pending action
- It does NOT change any action status
- It does NOT call any live API
- It does NOT require Google credentials
- It does NOT execute any write
