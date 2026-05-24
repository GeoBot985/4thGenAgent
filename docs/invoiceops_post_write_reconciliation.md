# InvoiceOps Post-Write Reconciliation

This page defines the read-only reconciliation step that follows an approved InvoiceOps live posting.

## Purpose

- Verify that posted register rows match the source TaskFrame and invoice evidence.
- Check the invoice register, match register or exception register, ledger rows, posting ledger entry, and rollback plan link.
- Provide a reviewer-friendly status for matched, exception, and blocked invoice paths.

## Status Model

- `RECONCILED`
- `RECONCILED_WITH_WARNINGS`
- `UNRECONCILED`
- `MISSING_POSTING_EVIDENCE`
- `MANUAL_REVIEW_REQUIRED`
- `BLOCKED`

## Path Summary

- Matched invoices must reconcile invoice, match, ledger, posting ledger, source frame, and rollback plan evidence.
- Exception invoices keep the exception evidence chain intact and should remain on the manual-review path when the transaction is not fully resolved.
- Blocked invoices must not produce improper final ledger rows.

## Read-Only CLI

```bash
taskframe invoiceops reconcile --frame-id <id> --json
taskframe invoiceops reconcile --invoice-number <number> --json
taskframe invoiceops reconcile --posting-plan-id <id> --json
```

Useful options:

- `--runtime-data-dir`
- `--profile`
- `--fixture-mode`
- `--write-report`
- `--json`

## Fixture Mode

Fixture mode lets the command run without Google credentials. It reads local fixture rows and any local posting ledger entries already written to `runtime_data/`.

## After Live Posting

After an approved live posting, run reconciliation using the invoice number, frame id, or posting plan id that was recorded in the posting ledger entry.

## Reports

Reports are written under `runtime_data/invoiceops/reconciliation/` when `--write-report` is supplied.

- `<invoice_number>_reconciliation.json`
- `<invoice_number>_reconciliation.md`

## Safety Statement

This command is read-only. It does not execute writes, approve pending actions, or perform rollback.

