# InvoiceOps Tool Boundary and Data Contracts

## Overview

InvoiceOps is the subsystem responsible for invoice matching, exception handling, and ledger
preparation within the 4thGenAgent runtime. This document defines the tool boundary rules and
all canonical data contracts used across InvoiceOps tools.

## Tool Boundary Rules

1. **InvoiceOps tools return plain dicts** wrapped in the existing `ToolResult` contract from
   `runtime/models.py`. No new result contract is introduced.

2. **Every InvoiceOps result must include all six ToolResult keys**:
   ```json
   {
     "ok": true,
     "type": "invoiceops_type_name",
     "data": {},
     "evidence": {},
     "error": "",
     "metadata": {}
   }
   ```

3. **Validation helpers** (`validate_*_shape`) return `{"ok": bool, "errors": [], "warnings": []}`.
   They never raise on validation failure; callers inspect `ok` and `errors`.

4. **Dry-run by default.** Every `prepared_write` must have `dry_run=True` unless explicitly
   overridden. `requires_approval=True` is always enforced — the validator errors if it is `False`.

5. **No live side effects** in any InvoiceOps contract or validator. Reads, transformations, and
   prepared writes are all deterministic and side-effect-free.

6. **Stdlib-only validators.** No third-party libraries are used in `invoiceops_contracts.py` or
   `invoiceops_constants.py`.

---

## Canonical Data Contracts

All shapes are validated by the corresponding `validate_*_shape` function in
`runtime/invoiceops_contracts.py`. Constants (enum sets, tolerances) live in
`runtime/invoiceops_constants.py`.

### 1. `invoice`

The canonical representation of a supplier invoice.

| Field | Type | Description |
|---|---|---|
| `invoice_id` | string | Unique identifier for this invoice record |
| `supplier_id` | string | Supplier identifier |
| `supplier_name` | string | Supplier display name |
| `invoice_number` | string | Supplier-assigned invoice number |
| `invoice_date` | YYYY-MM-DD | Date on the invoice |
| `po_number` | string | Linked purchase order number |
| `currency` | string | Currency code (e.g. `ZAR`) |
| `subtotal` | float | Pre-tax total |
| `tax_total` | float | Total tax amount |
| `invoice_total` | float | Grand total; must equal `subtotal + tax_total` |
| `line_items` | list[invoice_line] | One or more line items |

**Invoice line item**

| Field | Type |
|---|---|
| `line_no` | int |
| `description` | string |
| `sku` | string |
| `quantity` | float |
| `unit_price` | float |
| `tax_amount` | float |
| `line_total` | float |

Validator warns when `line_total` differs from both `quantity * unit_price` and
`quantity * unit_price + tax_amount` beyond the numeric tolerance (`0.005`).

---

### 2. `purchase_order`

| Field | Type | Enum values |
|---|---|---|
| `po_number` | string | |
| `supplier_id` | string | |
| `supplier_name` | string | |
| `status` | string | `open`, `part_received`, `closed`, `cancelled` |
| `currency` | string | |
| `po_total` | float | |
| `line_items` | list[po_line] | |

**PO line item**: `line_no` (int), `sku`, `description`, `ordered_quantity`, `unit_price`,
`line_total` (all floats except strings).

---

### 3. `goods_receipt`

| Field | Type | Enum values |
|---|---|---|
| `receipt_id` | string | |
| `po_number` | string | |
| `supplier_id` | string | |
| `receipt_date` | YYYY-MM-DD | |
| `status` | string | `received`, `partial`, `cancelled` |
| `line_items` | list[receipt_line] | |

**Receipt line item**: `line_no` (int), `sku`, `description`, `received_quantity` (float).

---

### 4. `supplier`

| Field | Type | Enum values |
|---|---|---|
| `supplier_id` | string | |
| `supplier_name` | string | |
| `status` | string | `active`, `inactive`, `blocked` |
| `vat_number` | string | |
| `payment_terms` | string | |
| `default_currency` | string | |

---

### 5. `match_result`

| Field | Type | Enum values |
|---|---|---|
| `match_id` | string | |
| `invoice_id` | string | |
| `invoice_number` | string | |
| `supplier_id` | string | |
| `po_number` | string | |
| `match_status` | string | `matched`, `exception`, `blocked` |
| `checks` | list[check_item] | |
| `exceptions` | list | |
| `ledger_posting_allowed` | bool | |
| `prepared_write_allowed` | bool | |

**Check item**: `check_id` (string), `status` (`pass`, `fail`, `warn`, `not_applicable`),
`expected`, `actual`, `message` (all strings).

---

### 6. `invoice_exception`

| Field | Type | Enum values |
|---|---|---|
| `exception_id` | string | |
| `exception_type` | string | `wrong_po`, `missing_po`, `missing_receipt`, `duplicate_invoice`, `supplier_mismatch`, `amount_mismatch`, `tax_mismatch`, `quantity_mismatch`, `bad_invoice_input` |
| `severity` | string | `low`, `medium`, `high`, `blocker` |
| `invoice_id` | string | |
| `po_number` | string | |
| `message` | string | |
| `recommended_action` | string | |
| `blocking` | bool | |

---

### 7. `ledger_row`

| Field | Type | Enum / constraints |
|---|---|---|
| `ledger_entry_id` | string | |
| `source_type` | string | must be `supplier_invoice` |
| `source_ref` | string | |
| `supplier_id` | string | |
| `invoice_number` | string | |
| `po_number` | string | |
| `debit_account` | string | |
| `credit_account` | string | |
| `amount` | float | |
| `currency` | string | |
| `status` | string | `prepared`, `posted`, `reversed` |

---

### 8. `prepared_write`

| Field | Type | Constraints |
|---|---|---|
| `prepared_write_id` | string | |
| `target` | string | `invoice_register`, `ledger`, `exception_register`, `match_register` |
| `operation` | string | `append`, `update` |
| `rows` | list | |
| `dry_run` | bool | **must be `True`**; validator warns if `False` |
| `requires_approval` | bool | **must be `True`**; validator errors if `False` |
| `rollback_plan` | dict | must be non-empty for write-like operations |

---

### 9. `rollback_plan`

| Field | Type | Enum values |
|---|---|---|
| `rollback_id` | string | |
| `rollback_type` | string | `delete_appended_rows`, `mark_reversed`, `manual_review_required`, `not_applicable` |
| `target` | string | |
| `source_prepared_write_id` | string | |
| `safe_to_auto_prepare` | bool | |
| `steps` | list[rollback_step] | |
| `reason` | string | |

**Rollback step**: `step_no` (int), `action` (string), `target` (string), `data` (dict).

---

### 10. `invoiceops_report`

| Field | Type |
|---|---|
| `report_id` | string |
| `invoice_id` | string |
| `match_status` | string (`matched`, `exception`, `blocked`) |
| `summary` | string |
| `checks` | list |
| `exceptions` | list |
| `prepared_writes` | list |
| `rollback_plans` | list |
| `evidence` | list |

---

### Evidence reference

Every InvoiceOps object that originated from a source document may carry evidence references.

| Field | Type | Constraints |
|---|---|---|
| `evidence_id` | string | |
| `source_type` | string | `pdf`, `text`, `google_sheet`, `fixture`, `tool_output` |
| `source_ref` | string | Path, URL, or identifier of the source |
| `field_path` | string | Dotted path of the extracted field (e.g. `invoice.invoice_number`) |
| `raw_value` | string | The raw extracted string |
| `confidence` | float | `0.0`–`1.0`; `1.0` for deterministic tools |

---

## Numeric Tolerance

Cross-field arithmetic checks (e.g. `invoice_total = subtotal + tax_total`) use a tolerance of
**`0.005`** (half a cent in ZAR). Differences larger than this generate a warning.

---

## Out of Scope (Spec 116)

The following are **not** implemented in Spec 116:

- Invoice PDF reader / OCR
- RAG ingestion or embedding
- Invoice field extraction
- Google Sheets reads or writes
- Duplicate invoice detection
- PO matching logic
- Goods receipt matching
- Live ledger writes
- Manifest integration
- Scenario gallery
