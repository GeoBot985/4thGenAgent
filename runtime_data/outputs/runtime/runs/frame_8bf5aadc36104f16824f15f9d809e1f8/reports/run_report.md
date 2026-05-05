# TaskFrame Run Report

## 1. Executive Summary

| Field | Value |
|---|---|
| Frame ID | frame_8bf5aadc36104f16824f15f9d809e1f8 |
| Manifest | accounting.payment_reconciliation |
| State | COMPLETED |
| Outcome | Run completed successfully. |
| Pending Actions | 2 |
| Executed Actions | 2 |
| Errors | 0 |

## 2. Trigger / Event

- Event ID: evt_97b5580148a94dad9d88ffb4282247c5
- Event Type: manual.accounting_payment_reconciliation
- Source: operator_scenario_pack

```json
{
  "event_id": "evt_97b5580148a94dad9d88ffb4282247c5",
  "event_type": "manual.accounting_payment_reconciliation",
  "invoices_range": "CustomerInvoices!A:H",
  "ledger_range": "Ledger!A:I",
  "orders_range": "Orders!A:F",
  "payments_range": "Payments!A:I",
  "recon_exceptions_range": "ReconExceptions!A:M",
  "recon_runs_range": "ReconRuns!A:J",
  "source": "operator_scenario_pack",
  "spreadsheet_id": "demo-sheet-local",
  "tabs": {
    "invoices": "CustomerInvoices!A:H",
    "ledger": "Ledger!A:I",
    "orders": "Orders!A:F",
    "payments": "Payments!A:I",
    "recon_exceptions": "ReconExceptions!A:M",
    "recon_runs": "ReconRuns!A:J"
  }
}
```

## 3. Route and Manifest

- Manifest ID: accounting.payment_reconciliation
- Manifest Name: 
- Step Count: 14
- Validation Count: 8

## 4. Runtime Final State

- Final State: COMPLETED
- Current Step ID: 
- Errors Count: 0

```json
{
  "errors": [],
  "failed_steps": [],
  "final_state": "COMPLETED",
  "message": "Completion gate passed.",
  "missing_executed_actions": [],
  "missing_outputs": [],
  "missing_pending_actions": [],
  "ok": true,
  "status": "COMPLETED",
  "validation_summary": {
    "failed": 0,
    "passed": 8
  }
}
```

## 5. Step Timeline

| # | Step | Kind | Action | Status | Attempts | Result | Error |
|---:|---|---|---|---|---:|---|---|
| 1 | read_payments_sheet | tool | read_range | COMPLETED | 1 | payments_sheet |  |
| 2 | read_orders_sheet | tool | read_range | COMPLETED | 1 | orders_sheet |  |
| 3 | read_invoices_sheet | tool | read_range | COMPLETED | 1 | invoices_sheet |  |
| 4 | read_ledger_sheet | tool | read_range | COMPLETED | 1 | ledger_sheet |  |
| 5 | load_payments | tool | load_payments | COMPLETED | 1 | payments |  |
| 6 | load_orders | tool | load_orders | COMPLETED | 1 | accounting_orders |  |
| 7 | load_invoices | tool | load_invoices | COMPLETED | 1 | invoices |  |
| 8 | load_ledger | tool | load_ledger | COMPLETED | 1 | ledger_entries |  |
| 9 | match_payments | tool | match_payments | COMPLETED | 1 | reconciliation_result |  |
| 10 | validate_reconciliation | tool | validate_result | COMPLETED | 1 | reconciliation_validation |  |
| 11 | draft_exception_summary | llm | draft_reconciliation_exception_summary | COMPLETED | 1 | exception_summary |  |
| 12 | build_recon_sheet_rows | tool | build_recon_sheet_rows | COMPLETED | 1 | recon_sheet_rows |  |
| 13 | stage_recon_run_write | tool | prepare_write_rows | STAGED | 1 | recon_run_write |  |
| 14 | stage_recon_exception_write | tool | prepare_write_rows | STAGED | 1 | recon_exception_write |  |

## 6. LLM Calls

- step_id: draft_exception_summary
  action: draft_reconciliation_exception_summary
  provider: fake
  model: fake
  ok: True
  output_ref: 
  micro_tool: True
## 7. Tool Calls

- step_id: read_payments_sheet
  tool: sheet/read_range
  namespace: sheet
  action: read_range
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: payments_sheet
  ok: True
  error: 
- step_id: read_orders_sheet
  tool: sheet/read_range
  namespace: sheet
  action: read_range
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: orders_sheet
  ok: True
  error: 
- step_id: read_invoices_sheet
  tool: sheet/read_range
  namespace: sheet
  action: read_range
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: invoices_sheet
  ok: True
  error: 
- step_id: read_ledger_sheet
  tool: sheet/read_range
  namespace: sheet
  action: read_range
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: ledger_sheet
  ok: True
  error: 
- step_id: load_payments
  tool: acct/load_payments
  namespace: acct
  action: load_payments
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: payments
  ok: True
  error: 
- step_id: load_orders
  tool: acct/load_orders
  namespace: acct
  action: load_orders
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: accounting_orders
  ok: True
  error: 
- step_id: load_invoices
  tool: acct/load_invoices
  namespace: acct
  action: load_invoices
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: invoices
  ok: True
  error: 
- step_id: load_ledger
  tool: acct/load_ledger
  namespace: acct
  action: load_ledger
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: ledger_entries
  ok: True
  error: 
- step_id: match_payments
  tool: recon/match_payments
  namespace: recon
  action: match_payments
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: reconciliation_result
  ok: True
  error: 
- step_id: validate_reconciliation
  tool: recon/validate_result
  namespace: recon
  action: validate_result
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: reconciliation_validation
  ok: True
  error: 
- step_id: build_recon_sheet_rows
  tool: acct/build_recon_sheet_rows
  namespace: acct
  action: build_recon_sheet_rows
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: recon_sheet_rows
  ok: True
  error: 
- step_id: stage_recon_run_write
  tool: sheet/prepare_write_rows
  namespace: sheet
  action: prepare_write_rows
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: recon_run_write
  ok: True
  error: 
- step_id: stage_recon_exception_write
  tool: sheet/prepare_write_rows
  namespace: sheet
  action: prepare_write_rows
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: recon_exception_write
  ok: True
  error: 
- step_id: stage_recon_run_write
  tool: 
  namespace: sheet
  action: prepare_write_rows
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: recon_run_write
  ok: True
  error: 
- step_id: stage_recon_exception_write
  tool: 
  namespace: sheet
  action: prepare_write_rows
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: recon_exception_write
  ok: True
  error: 
## 8. Outputs

### Output: accounting_orders
```json
{
  "count": 5,
  "errors": [],
  "ok": true,
  "orders": [
    {
      "currency": "ZAR",
      "customer_id": "CUST-1001",
      "invoice_id": "INV-10042",
      "order_ref": "ORD-10042",
      "order_status": "invoiced",
      "order_total": 1250.0,
      "source_row": 2
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1002",
      "invoice_id": "INV-10043",
      "order_ref": "ORD-10043",
      "order_status": "invoiced",
      "order_total": 500.0,
      "source_row": 3
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1003",
      "invoice_id": "INV-10044",
      "order_ref": "ORD-10044",
      "order_status": "invoiced",
      "order_total": 300.0,
      "source_row": 4
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1004",
      "invoice_id": "INV-10045",
      "order_ref": "ORD-10045",
      "order_status": "invoiced",
      "order_total": 500.0,
      "source_row": 5
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1005",
      "invoice_id": "INV-10046",
      "order_ref": "ORD-10046",
      "order_status": "invoiced",
      "order_total": 250.0,
      "source_row": 6
    }
  ]
}
```

### Output: exception_summary
```json
{
  "invented_facts": false,
  "key_exceptions": [
    "One payment has an amount mismatch.",
    "One payment reference appears more than once.",
    "One payment appears to already be posted."
  ],
  "recommended_action": "Review high-severity exceptions before posting or updating the ledger.",
  "risk_level": "high",
  "summary": "Payments were reconciled against orders, invoices, and ledger entries. Exceptions require operator review before posting."
}
```

### Output: invoices
```json
{
  "count": 5,
  "errors": [],
  "invoices": [
    {
      "currency": "ZAR",
      "customer_id": "CUST-1001",
      "due_date": "2026-05-15",
      "invoice_id": "INV-10042",
      "invoice_status": "issued",
      "invoice_total": 1250.0,
      "issued_date": "2026-05-01",
      "order_ref": "ORD-10042",
      "source_row": 2
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1002",
      "due_date": "2026-05-15",
      "invoice_id": "INV-10043",
      "invoice_status": "issued",
      "invoice_total": 500.0,
      "issued_date": "2026-05-01",
      "order_ref": "ORD-10043",
      "source_row": 3
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1003",
      "due_date": "2026-05-15",
      "invoice_id": "INV-10044",
      "invoice_status": "issued",
      "invoice_total": 300.0,
      "issued_date": "2026-05-01",
      "order_ref": "ORD-10044",
      "source_row": 4
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1004",
      "due_date": "2026-05-15",
      "invoice_id": "INV-10045",
      "invoice_status": "issued",
      "invoice_total": 500.0,
      "issued_date": "2026-05-01",
      "order_ref": "ORD-10045",
      "source_row": 5
    },
    {
      "currency": "ZAR",
      "customer_id": "CUST-1005",
      "due_date": "2026-05-15",
      "invoice_id": "INV-10046",
      "invoice_status": "issued",
      "invoice_total": 250.0,
      "issued_date": "2026-05-01",
      "order_ref": "ORD-10046",
      "source_row": 6
    }
  ],
  "ok": true
}
```

### Output: invoices_sheet
```json
{
  "error": "",
  "ok": true,
  "range_name": "CustomerInvoices!A:H",
  "row_count": 6,
  "rows": [
    [
      "invoice_id",
      "order_ref",
      "customer_id",
      "invoice_total",
      "currency",
      "invoice_status",
      "issued_date",
      "due_date"
    ],
    [
      "INV-10042",
      "ORD-10042",
      "CUST-1001",
      "1250.00",
      "ZAR",
      "issued",
      "2026-05-01",
      "2026-05-15"
    ],
    [
      "INV-10043",
      "ORD-10043",
      "CUST-1002",
      "500.00",
      "ZAR",
      "issued",
      "2026-05-01",
      "2026-05-15"
    ],
    [
      "INV-10044",
      "ORD-10044",
      "CUST-1003",
      "300.00",
      "ZAR",
      "issued",
      "2026-05-01",
      "2026-05-15"
    ],
    [
      "INV-10045",
      "ORD-10045",
      "CUST-1004",
      "500.00",
      "ZAR",
      "issued",
      "2026-05-01",
      "2026-05-15"
    ],
    [
      "INV-10046",
      "ORD-10046",
      "CUST-1005",
      "250.00",
      "ZAR",
      "issued",
      "2026-05-01",
      "2026-05-15"
    ]
  ],
  "spreadsheet_id": "demo-sheet-local"
}
```

### Output: ledger_entries
```json
{
  "count": 1,
  "errors": [],
  "ledger_entries": [
    {
      "amount": 1250.0,
      "credit_account": "revenue",
      "currency": "ZAR",
      "debit_account": "bank",
      "ledger_entry_id": "LED-1001",
      "posted_date": "2026-05-04",
      "source_ref": "EFT-9001",
      "source_row": 2,
      "source_type": "payment",
      "status": "posted"
    }
  ],
  "ok": true
}
```

### Output: ledger_sheet
```json
{
  "error": "",
  "ok": true,
  "range_name": "Ledger!A:I",
  "row_count": 2,
  "rows": [
    [
      "ledger_entry_id",
      "source_type",
      "source_ref",
      "debit_account",
      "credit_account",
      "amount",
      "currency",
      "posted_date",
      "status"
    ],
    [
      "LED-1001",
      "payment",
      "EFT-9001",
      "bank",
      "revenue",
      "1250.00",
      "ZAR",
      "2026-05-04",
      "posted"
    ]
  ],
  "spreadsheet_id": "demo-sheet-local"
}
```

### Output: orders_sheet
```json
{
  "error": "",
  "ok": true,
  "range_name": "Orders!A:F",
  "row_count": 6,
  "rows": [
    [
      "order_ref",
      "customer_id",
      "order_total",
      "currency",
      "order_status",
      "invoice_id"
    ],
    [
      "ORD-10042",
      "CUST-1001",
      "1250.00",
      "ZAR",
      "invoiced",
      "INV-10042"
    ],
    [
      "ORD-10043",
      "CUST-1002",
      "500.00",
      "ZAR",
      "invoiced",
      "INV-10043"
    ],
    [
      "ORD-10044",
      "CUST-1003",
      "300.00",
      "ZAR",
      "invoiced",
      "INV-10044"
    ],
    [
      "ORD-10045",
      "CUST-1004",
      "500.00",
      "ZAR",
      "invoiced",
      "INV-10045"
    ],
    [
      "ORD-10046",
      "CUST-1005",
      "250.00",
      "ZAR",
      "invoiced",
      "INV-10046"
    ]
  ],
  "spreadsheet_id": "demo-sheet-local"
}
```

### Output: payments
```json
{
  "count": 5,
  "errors": [],
  "ok": true,
  "payments": [
    {
      "amount": 1250.0,
      "currency": "ZAR",
      "customer_id": "CUST-1001",
      "order_ref": "ORD-10042",
      "payment_date": "2026-05-04",
      "payment_id": "PAY-1001",
      "payment_ref": "EFT-9001",
      "source": "bank",
      "source_row": 2,
      "status": "received"
    },
    {
      "amount": 450.0,
      "currency": "ZAR",
      "customer_id": "CUST-1002",
      "order_ref": "ORD-10043",
      "payment_date": "2026-05-04",
      "payment_id": "PAY-1002",
      "payment_ref": "EFT-9002",
      "source": "bank",
      "source_row": 3,
      "status": "received"
    },
    {
      "amount": 300.0,
      "currency": "ZAR",
      "customer_id": "CUST-1003",
      "order_ref": "ORD-10044",
      "payment_date": "2026-05-04",
      "payment_id": "PAY-1003",
      "payment_ref": "EFT-9003",
      "source": "bank",
      "source_row": 4,
      "status": "received"
    },
    {
      "amount": 500.0,
      "currency": "ZAR",
      "customer_id": "CUST-1004",
      "order_ref": "ORD-10045",
      "payment_date": "2026-05-04",
      "payment_id": "PAY-1004",
      "payment_ref": "EFT-9005",
      "source": "bank",
      "source_row": 5,
      "status": "received"
    },
    {
      "amount": 250.0,
      "currency": "ZAR",
      "customer_id": "CUST-1005",
      "order_ref": "ORD-10046",
      "payment_date": "2026-05-04",
      "payment_id": "PAY-1005",
      "payment_ref": "EFT-9005",
      "source": "bank",
      "source_row": 6,
      "status": "received"
    }
  ]
}
```

### Output: payments_sheet
```json
{
  "error": "",
  "ok": true,
  "range_name": "Payments!A:I",
  "row_count": 6,
  "rows": [
    [
      "payment_id",
      "payment_ref",
      "order_ref",
      "customer_id",
      "amount",
      "currency",
      "payment_date",
      "status",
      "source"
    ],
    [
      "PAY-1001",
      "EFT-9001",
      "ORD-10042",
      "CUST-1001",
      "1250.00",
      "ZAR",
      "2026-05-04",
      "received",
      "bank"
    ],
    [
      "PAY-1002",
      "EFT-9002",
      "ORD-10043",
      "CUST-1002",
      "450.00",
      "ZAR",
      "2026-05-04",
      "received",
      "bank"
    ],
    [
      "PAY-1003",
      "EFT-9003",
      "ORD-10044",
      "CUST-1003",
      "300.00",
      "ZAR",
      "2026-05-04",
      "received",
      "bank"
    ],
    [
      "PAY-1004",
      "EFT-9005",
      "ORD-10045",
      "CUST-1004",
      "500.00",
      "ZAR",
      "2026-05-04",
      "received",
      "bank"
    ],
    [
      "PAY-1005",
      "EFT-9005",
      "ORD-10046",
      "CUST-1005",
      "250.00",
      "ZAR",
      "2026-05-04",
      "received",
      "bank"
    ]
  ],
  "spreadsheet_id": "demo-sheet-local"
}
```

### Output: recon_exception_write
```json
{
  "dry_run": true,
  "message": "Google Sheet write dry-run completed.",
  "mode": "append",
  "ok": true,
  "range_name": "ReconExceptions!A:M",
  "row_count": 4,
  "spreadsheet_id": "demo-sheet-local",
  "written": false
}
```

### Output: recon_run_write
```json
{
  "dry_run": true,
  "message": "Google Sheet write dry-run completed.",
  "mode": "append",
  "ok": true,
  "range_name": "ReconRuns!A:J",
  "row_count": 1,
  "spreadsheet_id": "demo-sheet-local",
  "written": false
}
```

### Output: recon_sheet_rows
```json
{
  "ok": true,
  "recon_exception_rows": [
    [
      "RECON-20260504-201604",
      "EXC-ECBF0EB8",
      "already_posted",
      "EFT-9001",
      "PAY-1001",
      "ORD-10042",
      "",
      0.0,
      0.0,
      "ZAR",
      "medium",
      "Payment already posted to ledger.",
      ""
    ],
    [
      "RECON-20260504-201604",
      "EXC-87E2CD8E",
      "amount_mismatch",
      "EFT-9002",
      "PAY-1002",
      "ORD-10043",
      "",
      500.0,
      450.0,
      "ZAR",
      "high",
      "Payment amount does not match invoice.",
      ""
    ],
    [
      "RECON-20260504-201604",
      "EXC-F60249CF",
      "duplicate_payment_ref",
      "EFT-9005",
      "PAY-1004",
      "ORD-10045",
      "",
      0.0,
      0.0,
      "ZAR",
      "high",
      "Duplicate payment reference.",
      ""
    ],
    [
      "RECON-20260504-201604",
      "EXC-0EECDB81",
      "duplicate_payment_ref",
      "EFT-9005",
      "PAY-1005",
      "ORD-10046",
      "",
      0.0,
      0.0,
      "ZAR",
      "high",
      "Duplicate payment reference.",
      ""
    ]
  ],
  "recon_run_id": "RECON-20260504-201604",
  "recon_run_rows": [
    [
      "RECON-20260504-201604",
      "",
      1,
      1,
      4,
      2,
      1,
      1,
      "exceptions",
      ""
    ]
  ]
}
```

### Output: reconciliation_result
```json
{
  "exceptions": [
    {
      "actual_amount": 0.0,
      "currency": "ZAR",
      "exception_id": "EXC-ECBF0EB8",
      "exception_type": "already_posted",
      "expected_amount": 0.0,
      "invoice_id": "",
      "message": "Payment already posted to ledger.",
      "order_ref": "ORD-10042",
      "payment_id": "PAY-1001",
      "payment_ref": "EFT-9001",
      "severity": "medium"
    },
    {
      "actual_amount": 450.0,
      "currency": "ZAR",
      "exception_id": "EXC-87E2CD8E",
      "exception_type": "amount_mismatch",
      "expected_amount": 500.0,
      "invoice_id": "",
      "message": "Payment amount does not match invoice.",
      "order_ref": "ORD-10043",
      "payment_id": "PAY-1002",
      "payment_ref": "EFT-9002",
      "severity": "high"
    },
    {
      "actual_amount": 0.0,
      "currency": "ZAR",
      "exception_id": "EXC-F60249CF",
      "exception_type": "duplicate_payment_ref",
      "expected_amount": 0.0,
      "invoice_id": "",
      "message": "Duplicate payment reference.",
      "order_ref": "ORD-10045",
      "payment_id": "PAY-1004",
      "payment_ref": "EFT-9005",
      "severity": "high"
    },
    {
      "actual_amount": 0.0,
      "currency": "ZAR",
      "exception_id": "EXC-0EECDB81",
      "exception_type": "duplicate_payment_ref",
      "expected_amount": 0.0,
      "invoice_id": "",
      "message": "Duplicate payment reference.",
      "order_ref": "ORD-10046",
      "payment_id": "PAY-1005",
      "payment_ref": "EFT-9005",
      "severity": "high"
    }
  ],
  "matched": [
    {
      "already_posted": false,
      "amount": 300.0,
      "currency": "ZAR",
      "invoice_id": "INV-10044",
      "order_ref": "ORD-10044",
      "payment_id": "PAY-1003",
      "payment_ref": "EFT-9003",
      "status": "matched"
    }
  ],
  "ok": true,
  "payments_checked": 5,
  "recon_run_id": "RECON-20260504-201604",
  "summary": {
    "already_posted_count": 1,
    "amount_mismatch_count": 1,
    "duplicate_count": 2,
   
...<truncated>...
```

### Output: reconciliation_validation
```json
{
  "checks": [
    {
      "id": "summary_counts_match",
      "message": "Summary counts match result lists.",
      "ok": true
    }
  ],
  "errors": [],
  "ok": true
}
```

## 9. Evidence

No evidence records were attached to this TaskFrame.
## 10. Validations

| Validation ID | Type | OK | Message | Step | Data |
|---|---|---|---|---|---|
| draft_reconciliation_exception_summary_summary | llm_micro_tool_schema | ok |  |  | {"summary": "Payments were reconciled against orders, invoices, and ledger entries. Exceptions require operator review before posting."} |
| draft_reconciliation_exception_summary_risk_level | llm_micro_tool_schema | ok |  |  | {"risk_level": "high"} |
| draft_reconciliation_exception_summary_key_exceptions | llm_micro_tool_schema | ok |  |  | {"key_exceptions": ["One payment has an amount mismatch.", "One payment reference appears more than once.", "One payment appears to already be posted."]} |
| draft_reconciliation_exception_summary_recommended_action | llm_micro_tool_schema | ok |  |  | {"recommended_action": "Review high-severity exceptions before posting or updating the ledger."} |
| draft_reconciliation_exception_summary_invented_facts | llm_micro_tool_schema | ok |  |  | {"invented_facts": false} |
| draft_reconciliation_exception_summary_risk_level_allowed | llm_micro_tool_schema | ok |  |  | {"risk_level": "high"} |
| draft_reconciliation_exception_summary_invented_facts | llm_micro_tool_schema | ok |  |  | {"invented_facts": false} |
| draft_reconciliation_exception_summary_risk_level | llm_micro_tool_schema | ok |  |  | {"risk_level": "high"} |

Passed validations: 8
Failed validations: 0
## 11. Approval / Side-Effect Status

Pending Action Count: 2
Executed Action Count: 0
### Pending Action: pa_f1c15f85251746deb819a528764e1f29
| Field | Value |
|---|---|
| Tool | sheet/write_rows |
| Status | EXECUTED |
| Risk | side_effect_unknown |
| Requires Approval | True |
| Output Alias | recon_run_write |
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {"dry_run": true, "mode": "append", "range_name": "ReconRuns!A:J", "rows": [["RECON-20260504-201604", "", 1, 1, 4, 2, 1, 1, "exceptions", ""]], "spreadsheet_id": "demo-sheet-local"}
Guardrails: ["Requires explicit approval before execution.", "UI live execution is disabled in this spec.", "Dry-run mode only."]

### Pending Action: pa_76e3ed0f8b4b40a89acac67f11b59316
| Field | Value |
|---|---|
| Tool | sheet/write_rows |
| Status | EXECUTED |
| Risk | side_effect_unknown |
| Requires Approval | True |
| Output Alias | recon_exception_write |
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {"dry_run": true, "mode": "append", "range_name": "ReconExceptions!A:M", "rows": [["RECON-20260504-201604", "EXC-ECBF0EB8", "already_posted", "EFT-9001", "PAY-1001", "ORD-10042", "", 0.0, 0.0, "ZAR", "medium", "Payment already posted to ledger.", ""], ["RECON-20260504-201604", "EXC-87E2CD8E", "amount_mismatch", "EFT-9002", "PAY-1002", "ORD-10043", "", 500.0, 450.0, "ZAR", "high", "Payment amount does not match invoice.", ""], ["RECON-20260504-201604", "EXC-F60249CF", "duplicate_payment_ref", "EFT-9005", "PAY-1004", "ORD-10045", "", 0.0, 0.0, "ZAR", "high", "Duplicate payment reference.", ""], ["RECON-20260504-201604", "EXC-0EECDB81", "duplicate_payment_ref", "EFT-9005", "PAY-1005", "ORD-10046", "", 0.0, 0.0, "ZAR", "high", "Duplicate payment reference.", ""]], "spreadsheet_id": "demo-sheet-local"}
Guardrails: ["Requires explicit approval before execution.", "UI live execution is disabled in this spec.", "Dry-run mode only."]

## 12. Failure Summary

No failure for this run.
## 13. Artifact Index

| Artifact | Path |
|---|---|
| TaskFrame JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\taskframe.json |
| Summary JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\summary.json |
| Outputs JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\outputs.json |
| Audit JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\audit.json |
| Run Report Markdown | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\run_report.md |
| Run Report HTML | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\run_report.html |
| Approval Pack Report Markdown | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\approval_pack_report.md |
| Approval Pack Report HTML | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\approval_pack_report.html |
| Failure Report Markdown | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\failure_report.md |
| Failure Report HTML | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\failure_report.html |
| Evidence Bundle JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_8bf5aadc36104f16824f15f9d809e1f8\reports\evidence_bundle.json |
## 14. Raw References

- Frame ID: frame_8bf5aadc36104f16824f15f9d809e1f8
- Manifest ID: accounting.payment_reconciliation
- Runtime Data Dir: D:\Projects\4thGenAgent\runtime_data\outputs\runtime
- Generated At: 2026-05-04T20:16:04Z
- Report Version: operator_run_report_v1