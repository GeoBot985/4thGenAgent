# InvoiceOps Accounting Evidence Pack

This page defines the evidence bundle built after post-write reconciliation.

## Purpose

- Gather the source invoice evidence, extraction evidence, matching evidence, posting evidence, reconciliation evidence, rollback evidence, and audit trail into one reviewer-facing pack.
- Keep the pack read-only so it can support audit review without mutating accounting state.

## Sections

- `invoice_source`
- `extraction`
- `validation`
- `matching`
- `posting`
- `reconciliation`
- `rollback`
- `audit_trail`

## Read-Only CLI

```bash
taskframe invoiceops evidence-pack --frame-id <id> --json
taskframe invoiceops evidence-pack --invoice-number <number> --write-report --json
taskframe invoiceops evidence-pack --posting-plan-id <id> --json
```

Useful options:

- `--runtime-data-dir`
- `--profile`
- `--fixture-mode`
- `--write-report`
- `--json`

## Fixture Mode

Fixture mode uses local fixture rows and local posting ledger entries only. It does not require Google credentials.

## After Live Posting

After an approved posting, use the invoice number or frame id that was recorded in the posting ledger. The pack should explain what was posted, what reconciled, and what still needs review.

## Reports

Reports are written under `runtime_data/invoiceops/accounting_evidence/` when `--write-report` is supplied.

- `<invoice_number>_accounting_evidence_pack.json`
- `<invoice_number>_accounting_evidence_pack.md`

## Safety Statement

This command is read-only. It does not execute writes, approve pending actions, or perform rollback.

