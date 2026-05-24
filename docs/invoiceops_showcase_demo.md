# InvoiceOps Showcase Demo

Spec 158 — InvoiceOps Live Bookkeeping Showcase Demo Pack v1.

## Purpose

The InvoiceOps Showcase Demo is a live, multi-invoice demonstration of the full TaskFrame InvoiceOps bookkeeping automation pipeline.

It shows — in 5–10 minutes — the complete journey from raw invoice through:
- Structured extraction
- Three-way matching (invoice ↔ PO ↔ goods receipt)
- Exception classification
- Controlled live Google Sheets posting
- Post-write reconciliation
- Accounting evidence pack
- Visual dashboard

## Demo Scenario Set

| Invoice | Scenario | Expected Result |
|---------|----------|----------------|
| INV-001 | Clean matched invoice | Posted to invoice, match, and ledger registers |
| INV-002 | Duplicate invoice (re-submission) | Blocked / exception — DUPLICATE_INVOICE |
| INV-003 | Non-existent PO number | Exception — PO_NOT_FOUND |
| INV-004 | Missing goods receipt | Exception — GOODS_RECEIPT_NOT_FOUND |
| INV-005 | Supplier name mismatch | Exception — SUPPLIER_MISMATCH |
| INV-006 | Unit price above PO rate | Exception — PRICE_MISMATCH |
| INV-007 | Quantity billed > received | Exception — QUANTITY_MISMATCH |
| INV-008 | VAT / total arithmetic error | Exception — TAX_TOTAL_MISMATCH |

## Talking Points

- **INV-001**: Clean three-way match. Invoice posts to all registers with full audit trail.
- **INV-002**: Same supplier, same PO, same amounts — duplicate check fires. Invoice blocked.
- **INV-003**: PO number does not exist in register. Invoice cannot proceed without approved PO.
- **INV-004**: Goods not received yet. Three-way match requires GR. Invoice held pending delivery.
- **INV-005**: PO issued to different supplier. Assignment not approved. Manual review required.
- **INV-006**: Banner price 23% above approved PO rate. Invoice blocked pending price authorisation.
- **INV-007**: Invoice claims 50 cases; warehouse signed for 40. Overpayment of 10 cases blocked.
- **INV-008**: VAT arithmetic does not match declared total. Invoice arithmetic error caught before payment.

## Demo Data

Fixture invoice source files live at:

```
fixtures/invoiceops_showcase/invoices/
  INV-001.txt  (clean match)
  INV-002.txt  (duplicate)
  INV-003.txt  (wrong PO)
  INV-004.txt  (missing GR)
  INV-005.txt  (supplier mismatch)
  INV-006.txt  (price mismatch)
  INV-007.txt  (quantity mismatch)
  INV-008.txt  (tax/total mismatch)
```

Seeded master data (suppliers, POs, GRs) is defined in `runtime/invoiceops_showcase_demo.py`.

## Modules

| Module | Purpose |
|--------|---------|
| `runtime/invoiceops_showcase_demo.py` | Core demo orchestrator |
| `runtime/invoiceops_showcase_sheet_formatting.py` | Google Sheets batchUpdate formatting spec |

## Reports

After a run, reports are written to:

```
runtime_data/invoiceops/showcase/
  showcase_demo_latest.json
  showcase_demo_latest.md
  showcase_demo_run_<id>.json
  showcase_demo_run_<id>.md
  showcase_invoice_results_<id>.json
  showcase_live_write_summary_<id>.json
```

## Safety

- Live writes require `controlled_live_write` profile.
- Live writes require typed confirmation: `EXECUTE LIVE INVOICEOPS SHOWCASE <spreadsheet_id>`.
- Each write gets a unique idempotency key and payload hash.
- No automatic rollback — rollback plans are written for manual execution only.
- RPA, Gmail send, and Calendar mutation remain blocked.

## Related Documentation

- [Google Sheet Tab Guide](invoiceops_showcase_google_sheet.md)
- [Live Run Runbook](invoiceops_showcase_live_runbook.md)
- [Live Sheet Posting Pilot (Spec 156)](invoiceops_live_sheet_posting_pilot.md)
- [Post-Write Reconciliation (Spec 157)](invoiceops_post_write_reconciliation.md)
