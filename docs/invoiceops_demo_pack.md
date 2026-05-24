# InvoiceOps Demo Pack

This demo pack shows the InvoiceOps manifest running end to end in safe fixture mode.

## Purpose

- Prove the Spec 125 manifest can process invoice inputs without live Google Sheets writes.
- Show the happy path, blocked paths, exception paths, and rollback metadata in one deterministic gallery.
- Provide a readable regression pack for operators and reviewers.

## Scenarios

- `happy_path_matched`
- `wrong_po`
- `missing_po`
- `missing_receipt`
- `duplicate_invoice`
- `supplier_mismatch`
- `price_mismatch`
- `quantity_mismatch`
- `bad_invoice_text`
- `rollback_required_case`

## Expected Business Behaviour

- Happy path invoices match and prepare dry-run writes for the invoice register, match register, and ledger.
- Wrong PO, missing PO, missing receipt, duplicate invoice, supplier mismatch, and quantity mismatch stop safely and route to exception handling.
- Price mismatch produces an exception path with prepared dry-run writes and rollback metadata.
- Bad invoice text fails validation safely before any write preparation.
- Rollback-required cases always include rollback plans on prepared writes.

## Expected Safety Behaviour

- No scenario performs a live Google Sheets write.
- Prepared writes remain metadata only.
- Approval execution is not part of this pack.
- Rollback execution is not part of this pack.

## Evidence Outputs

- Invoice source evidence
- Extraction evidence
- Matching evidence
- Exception evidence
- Prepared write evidence
- Rollback evidence
- Match, exception, ledger, rollback, and evidence bundle reports
- Post-write reconciliation and accounting evidence pack reports for approved postings

## What Is Intentionally Not Live

- Google Sheets writes
- Approval execution
- Rollback execution
- Manifest creation
- UI changes
- HTML/Markdown rendering beyond the report text already produced by the tools

## Read-Only Post-Write Checks

The demo pack is separate from the post-write reconciliation flow. After live posting, use the reconciliation and accounting evidence pack commands to verify the posted rows without mutating accounting state.

## How To Run

The gallery is exposed as a deterministic Python runner and pytest coverage.

### Pytest

```bash
pytest tests/test_invoiceops_regression_gallery.py -q
```

### Direct runner

```bash
python -c "from runtime.invoiceops_gallery import run_invoiceops_gallery; import json; print(json.dumps(run_invoiceops_gallery(), indent=2))"
```

Gallery outputs are written under `runtime_data/invoiceops_demo_outputs/` when the runner is executed.
