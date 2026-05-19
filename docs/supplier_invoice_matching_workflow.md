# Supplier Invoice Matching Workflow

This workflow implements a deterministic three-way match between:

- supplier invoice
- purchase order
- goods receipt

It is designed for accounting operations where invoices must be checked before any ledger posting is staged.

## Flow

1. Read the invoice.
2. Read the purchase order.
3. Read receipts for the PO.
4. Check for duplicate invoice number.
5. Run deterministic three-way matching.
6. Draft a bounded exception summary with the LLM helper.
7. Build the exception report.
8. Stage match-run write rows.
9. Stage ledger rows only when the invoice matches.

## Tool set

- `supplier_invoice/read`
- `po/read`
- `receipt/read_by_po`
- `supplier_invoice/check_duplicate`
- `supplier_invoice/match_three_way`
- `draft_supplier_invoice_exception_summary`
- `supplier_invoice/build_exception_report`
- `supplier_invoice/prepare_match_run_write`
- `supplier_invoice/prepare_ledger_write`
- `supplier_invoice/execute_ledger_write`

## Exception codes

Common deterministic exception codes include:

- `PO_NOT_FOUND`
- `RECEIPT_NOT_FOUND`
- `SUPPLIER_MISMATCH`
- `UNKNOWN_SKU`
- `QUANTITY_MISMATCH`
- `RECEIPT_MISMATCH`
- `PRICE_MISMATCH`
- `LINE_TOTAL_MISMATCH`
- `TAX_MISMATCH`
- `TOTAL_MISMATCH`
- `DUPLICATE_INVOICE`

## Approval and dry-run behaviour

- Match-run and ledger writes are approval-gated.
- No live writes are performed.
- Dry-run execution stages pending actions and produces an evidence bundle.
- Exception invoices stage the match-run write but do not stage ledger posting.

## Evidence expectations

The report bundle should include:

- invoice record
- purchase order record
- receipt record(s)
- duplicate check
- deterministic match result
- exception report
- staged pending actions
- dry-run approval/execution output

## Known limitation

This workflow is intentionally dry-run only. It does not post to a live ledger.
