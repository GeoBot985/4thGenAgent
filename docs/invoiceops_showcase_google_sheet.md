# InvoiceOps Showcase Google Sheet Guide

## Overview

The showcase creates a Google Sheet workbook that acts as a lightweight bookkeeping control register for the demo.

## Sheet Tabs

| Tab | Purpose |
|-----|---------|
| **Dashboard** | High-level visual summary of the demo run (summary cards, status tables) |
| **Invoices** | Invoice register — one row per processed invoice |
| **PO Register** | Demo purchase orders (seeded before run) |
| **Goods Receipts** | Demo goods receipt records (seeded before run) |
| **Supplier Master** | Demo supplier records (seeded before run) |
| **Match Results** | Three-way match result per invoice |
| **Exceptions** | Exception cases with type and recommended action |
| **Ledger** | Debit/credit posting rows for matched invoices |
| **Posting Ledger** | Live write execution record (idempotency key, hash, status, timestamp) |
| **Reconciliation** | Post-write reconciliation status per invoice |
| **Rollback Plans** | Manual rollback metadata (delete-by-idempotency-key) |
| **Evidence Index** | Source refs, TaskFrames, report paths, evidence links |
| **Demo Run Log** | Timestamped record of each demo execution event |

## Formatting

The sheet is formatted as a business demo workbook:

- Frozen header rows on all tabs
- Bold, coloured headers (blue background)
- Per-tab column widths
- Currency formatting (ZAR) on financial columns
- Date formatting (yyyy-mm-dd) on date columns
- Basic filters on all tabs
- Tab colours (green = master data, blue = posting/ledger, amber = exceptions, red = rollback)
- Conditional formatting for status columns:
  - **matched** → light green
  - **exception** → light amber
  - **blocked** → light red
  - **RECONCILED** → light green
  - **UNRECONCILED** → light red
  - **MANUAL_REVIEW_REQUIRED** → light amber

## Dashboard Summary Cards

| Card | Example Value |
|------|--------------|
| Invoices processed | 8 |
| Matched | 1 |
| Exceptions | 6 |
| Blocked | 1 |
| Live writes performed | 4 |
| Reconciled postings | 1 |
| Manual review required | 7 |
| Total invoice value | ZAR 253,143.25 |

## Column Headers Per Tab

### Invoices
Invoice Number | Invoice Date | Supplier | PO Number | GR Number | Subtotal | VAT | Total | Match Status | Posting Status | Run ID

### Match Results
Invoice Number | Supplier | PO Number | GR Number | Invoice Total | PO Total | Match Status | Exception Type | Scenario

### Exceptions
Invoice Number | Exception Type | Supplier | PO Number | Recommended Action | Scenario

### Ledger
Invoice Number | Entry Type | Account | Debit ZAR | Credit ZAR | Description | Run ID

### Posting Ledger
Idempotency Key | Invoice Number | Target Register | Payload Hash | Execution Status | Timestamp | Run ID

### Reconciliation
Invoice Number | Match Status | Posting Status | Reconciliation Status | Exception Type | Live Write Count

## Setup

To create the sheet:

```bash
python -m src.taskframe_cli invoiceops showcase setup-sheet \
  --profile controlled_live_write \
  --spreadsheet-id "<id>" \
  --confirm "EXECUTE LIVE INVOICEOPS SHOWCASE <id>" \
  --json
```

## Resetting

The sheet can be reset between demo runs using `--reset-sheet`:

```bash
python -m src.taskframe_cli invoiceops showcase run \
  --profile controlled_live_write \
  --spreadsheet-id "<id>" \
  --reset-sheet \
  --confirm "EXECUTE LIVE INVOICEOPS SHOWCASE <id>" \
  --json
```

## Configuration

Store your spreadsheet ID in:

```
~/.taskframe/invoiceops_showcase.json
```

See `config/examples/invoiceops_showcase.example.json` for the full configuration shape.
