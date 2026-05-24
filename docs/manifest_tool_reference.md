# Manifest Tool Reference

> **This file is generated from the runtime tool registry.**
> Do not edit it manually. To update, run:
> ```
> python tools/generate_manifest_tool_reference.py
> ```
> See [manifest_command_reference.md](manifest_command_reference.md) for command syntax.

---

## acct/build_recon_sheet_rows

| Field | Value |
|---|---|
| Namespace | acct |
| Action | build_recon_sheet_rows |
| Side effect | false |
| Requires approval | false |
| Output type | `recon_sheet_rows` |

### Command form

```text
[t:acct/build_recon_sheet_rows -> output_name] reconciliation_result=$inputs.reconciliation_result exception_summary=$inputs.exception_summary
```

### Required arguments

- `reconciliation_result` (str)
- `exception_summary` (str)

### Optional arguments

- `frame_id` (str)

---
## acct/load_invoices

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_invoices |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_invoices` |

### Command form

```text
[t:acct/load_invoices -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## acct/load_ledger

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_ledger |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_ledger` |

### Command form

```text
[t:acct/load_ledger -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## acct/load_orders

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_orders |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_orders` |

### Command form

```text
[t:acct/load_orders -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## acct/load_payments

| Field | Value |
|---|---|
| Namespace | acct |
| Action | load_payments |
| Side effect | false |
| Requires approval | false |
| Output type | `accounting_payments` |

### Command form

```text
[t:acct/load_payments -> output_name] sheet_rows=$inputs.sheet_rows
```

### Required arguments

- `sheet_rows` (str)

---
## business/get_order_context

| Field | Value |
|---|---|
| Namespace | business |
| Action | get_order_context |
| Side effect | false |
| Requires approval | false |
| Output type | `business_order_context` |

### Command form

```text
[t:business/get_order_context -> output_name] order_id=$inputs.order_id
```

### Required arguments

- `order_id` (str)

### Optional arguments

- `runtime_root` (str)

---
## cal/create

| Field | Value |
|---|---|
| Namespace | cal |
| Action | create |
| Side effect | true |
| Requires approval | true |
| Output type | `calendar_create_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:cal/create -> output_name] title=$inputs.title start=$inputs.start end=$inputs.end
```

### Required arguments

- `title` (str)
- `start` (str)
- `end` (str)

### Optional arguments

- `description` (str)
- `location` (str)

---
## cal/next

| Field | Value |
|---|---|
| Namespace | cal |
| Action | next |
| Side effect | false |
| Requires approval | false |
| Output type | `calendar_event_list` |

### Command form

```text
[t:cal/next -> output_name]
```

### Optional arguments

- `max_results` (int)

---
## cal/remove

| Field | Value |
|---|---|
| Namespace | cal |
| Action | remove |
| Side effect | true |
| Requires approval | true |
| Output type | `calendar_remove_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:cal/remove -> output_name] event_id=$inputs.event_id
```

### Required arguments

- `event_id` (str)

---
## cal/search

| Field | Value |
|---|---|
| Namespace | cal |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `calendar_event_list` |

### Command form

```text
[t:cal/search -> output_name]
```

### Optional arguments

- `query` (str)
- `days` (int)
- `time_min` (str)
- `time_max` (str)
- `max_results` (int)

---
## customer/build_status_context

| Field | Value |
|---|---|
| Namespace | customer |
| Action | build_status_context |
| Side effect | false |
| Requires approval | false |
| Output type | `status_context` |

### Command form

```text
[t:customer/build_status_context -> output_name] customer=$inputs.customer order=$inputs.order shipment=$inputs.shipment
```

### Required arguments

- `customer` (str)
- `order` (str)
- `shipment` (str)

---
## customer/extract_order_ref

| Field | Value |
|---|---|
| Namespace | customer |
| Action | extract_order_ref |
| Side effect | false |
| Requires approval | false |
| Output type | `order_ref_result` |

### Command form

```text
[t:customer/extract_order_ref -> output_name] message=$inputs.message
```

### Required arguments

- `message` (str)

---
## customer/order_context

| Field | Value |
|---|---|
| Namespace | customer |
| Action | order_context |
| Side effect | false |
| Requires approval | false |
| Output type | `order_context_result` |

### Command form

```text
[t:customer/order_context -> output_name] customer_id=$inputs.customer_id order_ref=$inputs.order_ref
```

### Required arguments

- `customer_id` (str)
- `order_ref` (str)

---
## customer/prepare_message_action

| Field | Value |
|---|---|
| Namespace | customer |
| Action | prepare_message_action |
| Side effect | true |
| Requires approval | true |
| Output type | `customer_message_action` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:customer/prepare_message_action -> output_name] customer=$inputs.customer channel=$inputs.channel message=$inputs.message
```

### Required arguments

- `customer` (str)
- `channel` (str)
- `message` (str)

---
## customer/read

| Field | Value |
|---|---|
| Namespace | customer |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `customer_read_result` |

### Command form

```text
[t:customer/read -> output_name] customer_id=$inputs.customer_id
```

### Required arguments

- `customer_id` (str)

---
## customer/search

| Field | Value |
|---|---|
| Namespace | customer |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `customer_list` |

### Command form

```text
[t:customer/search -> output_name]
```

### Optional arguments

- `customer_id` (str)
- `name` (str)
- `status` (str)

---
## customer/validate_owns_order

| Field | Value |
|---|---|
| Namespace | customer |
| Action | validate_owns_order |
| Side effect | false |
| Requires approval | false |
| Output type | `ownership_check` |

### Command form

```text
[t:customer/validate_owns_order -> output_name] customer=$inputs.customer order=$inputs.order
```

### Required arguments

- `customer` (str)
- `order` (str)

---
## customer/validate_status_reply

| Field | Value |
|---|---|
| Namespace | customer |
| Action | validate_status_reply |
| Side effect | false |
| Requires approval | false |
| Output type | `reply_validation` |

### Command form

```text
[t:customer/validate_status_reply -> output_name] reply=$inputs.reply order=$inputs.order shipment=$inputs.shipment
```

### Required arguments

- `reply` (str)
- `order` (str)
- `shipment` (str)

---
## file/exists

| Field | Value |
|---|---|
| Namespace | file |
| Action | exists |
| Side effect | false |
| Requires approval | false |
| Output type | `file_exists_result` |

### Command form

```text
[t:file/exists -> output_name] path=$inputs.path
```

### Required arguments

- `path` (str)

### Optional arguments

- `runtime_root` (str)

---
## file/list

| Field | Value |
|---|---|
| Namespace | file |
| Action | list |
| Side effect | false |
| Requires approval | false |
| Output type | `file_list_result` |

### Command form

```text
[t:file/list -> output_name]
```

### Optional arguments

- `path` (str)
- `runtime_root` (str)

---
## file/read_json

| Field | Value |
|---|---|
| Namespace | file |
| Action | read_json |
| Side effect | false |
| Requires approval | false |
| Output type | `file_read_json_result` |

### Command form

```text
[t:file/read_json -> output_name] path=$inputs.path
```

### Required arguments

- `path` (str)

### Optional arguments

- `runtime_root` (str)

---
## file/write_json

| Field | Value |
|---|---|
| Namespace | file |
| Action | write_json |
| Side effect | true |
| Requires approval | true |
| Output type | `file_write_json_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:file/write_json -> output_name] path=$inputs.path data=$inputs.data
```

### Required arguments

- `path` (str)
- `data` (str)

### Optional arguments

- `runtime_root` (str)

---
## g/check

| Field | Value |
|---|---|
| Namespace | g |
| Action | check |
| Side effect | false |
| Requires approval | false |
| Output type | `gmail_check_result` |

### Command form

```text
[t:g/check -> output_name]
```

### Optional arguments

- `max_results` (int)

---
## g/send

| Field | Value |
|---|---|
| Namespace | g |
| Action | send |
| Side effect | true |
| Requires approval | true |
| Output type | `gmail_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:g/send -> output_name] to=$inputs.to subject=$inputs.subject body=$inputs.body
```

### Required arguments

- `to` (str)
- `subject` (str)
- `body` (str)

---
## gb/book

| Field | Value |
|---|---|
| Namespace | gb |
| Action | book |
| Side effect | true |
| Requires approval | true |
| Output type | `gobook_booking_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:gb/book -> output_name] date=$inputs.date time_value=$inputs.time_value court=$inputs.court
```

### Required arguments

- `date` (str)
- `time_value` (str)
- `court` (str)

### Optional arguments

- `confirm` (bool)
- `slowmo` (int)

---
## gb/cancel

| Field | Value |
|---|---|
| Namespace | gb |
| Action | cancel |
| Side effect | true |
| Requires approval | true |
| Output type | `gobook_cancel_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:gb/cancel -> output_name] date=$inputs.date time_value=$inputs.time_value court=$inputs.court
```

### Required arguments

- `date` (str)
- `time_value` (str)
- `court` (str)

### Optional arguments

- `confirm` (bool)
- `slowmo` (int)

---
## gb/list

| Field | Value |
|---|---|
| Namespace | gb |
| Action | list |
| Side effect | false |
| Requires approval | false |
| Output type | `gobook_booking_list` |

### Command form

```text
[t:gb/list -> output_name]
```

### Optional arguments

- `slowmo` (int)

---
## gb/open_courts

| Field | Value |
|---|---|
| Namespace | gb |
| Action | open_courts |
| Side effect | false |
| Requires approval | false |
| Output type | `gobook_open_court_list` |

### Command form

```text
[t:gb/open_courts -> output_name] date=$inputs.date start=$inputs.start end=$inputs.end
```

### Required arguments

- `date` (str)
- `start` (str)
- `end` (str)

### Optional arguments

- `slowmo` (int)

---
## gmail/send

| Field | Value |
|---|---|
| Namespace | gmail |
| Action | send |
| Side effect | true |
| Requires approval | true |
| Output type | `gmail_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:gmail/send -> output_name] to=$inputs.to subject=$inputs.subject body=$inputs.body
```

### Required arguments

- `to` (str)
- `subject` (str)
- `body` (str)

### Optional arguments

- `cc` (str)
- `bcc` (str)
- `attachments` (str)
- `dry_run` (bool)

---
## inventory/filter_reorder_candidates

| Field | Value |
|---|---|
| Namespace | inventory |
| Action | filter_reorder_candidates |
| Side effect | false |
| Requires approval | false |
| Output type | `reorder_candidates` |

### Command form

```text
[t:inventory/filter_reorder_candidates -> output_name] items=$inputs.items
```

### Required arguments

- `items` (str)

---
## inventory/read

| Field | Value |
|---|---|
| Namespace | inventory |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `inventory_record` |

### Command form

```text
[t:inventory/read -> output_name] sku=$inputs.sku
```

### Required arguments

- `sku` (str)

---
## inventory/search_low_stock

| Field | Value |
|---|---|
| Namespace | inventory |
| Action | search_low_stock |
| Side effect | false |
| Requires approval | false |
| Output type | `low_stock_result` |

### Command form

```text
[t:inventory/search_low_stock -> output_name]
```

---
## invoiceops/build_evidence_bundle

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_evidence_bundle |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_report` |

### Command form

```text
[t:invoiceops/build_evidence_bundle -> output_name] invoice=$inputs.invoice
```

### Required arguments

- `invoice` (str)

### Optional arguments

- `match_result` (str)
- `exceptions` (str)
- `prepared_writes` (str)

---
## invoiceops/build_exception_action_plan

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_exception_action_plan |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_exception_action_plan` |

### Command form

```text
[t:invoiceops/build_exception_action_plan -> output_name] invoice=$inputs.invoice exceptions=$inputs.exceptions
```

### Required arguments

- `invoice` (str)
- `exceptions` (str)

### Optional arguments

- `fallback_results` (str)

---
## invoiceops/build_exception_report

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_exception_report |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_report` |

### Command form

```text
[t:invoiceops/build_exception_report -> output_name] invoice=$inputs.invoice exceptions=$inputs.exceptions
```

### Required arguments

- `invoice` (str)
- `exceptions` (str)

### Optional arguments

- `action_plan` (str)

---
## invoiceops/build_ledger_posting_summary

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_ledger_posting_summary |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_report` |

### Command form

```text
[t:invoiceops/build_ledger_posting_summary -> output_name] invoice=$inputs.invoice ledger_rows=$inputs.ledger_rows
```

### Required arguments

- `invoice` (str)
- `ledger_rows` (str)

---
## invoiceops/build_live_posting_plan

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_live_posting_plan |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_posting_plan` |

### Command form

```text
[t:invoiceops/build_live_posting_plan -> output_name] frame_id=$inputs.frame_id
```

### Required arguments

- `frame_id` (str)

### Optional arguments

- `invoice_id` (str)
- `invoice_number` (str)
- `supplier_name` (str)
- `po_number` (str)
- `match_status` (str)
- `prepared_writes` (str)

---
## invoiceops/build_match_report

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_match_report |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_report` |

### Command form

```text
[t:invoiceops/build_match_report -> output_name] invoice=$inputs.invoice match_result=$inputs.match_result
```

### Required arguments

- `invoice` (str)
- `match_result` (str)

---
## invoiceops/build_posting_approval_pack

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_posting_approval_pack |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_approval_pack` |

### Command form

```text
[t:invoiceops/build_posting_approval_pack -> output_name] posting_plan=$inputs.posting_plan
```

### Required arguments

- `posting_plan` (str)

### Optional arguments

- `invoice` (str)
- `match_result` (str)
- `exceptions` (str)

---
## invoiceops/build_rollback_summary

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | build_rollback_summary |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_report` |

### Command form

```text
[t:invoiceops/build_rollback_summary -> output_name] prepared_writes=$inputs.prepared_writes
```

### Required arguments

- `prepared_writes` (str)

---
## invoiceops/check_duplicate_invoice

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | check_duplicate_invoice |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_match_check` |

### Command form

```text
[t:invoiceops/check_duplicate_invoice -> output_name] invoice=$inputs.invoice invoice_register=$inputs.invoice_register
```

### Required arguments

- `invoice` (str)
- `invoice_register` (str)

---
## invoiceops/check_tax

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | check_tax |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_match_check` |

### Command form

```text
[t:invoiceops/check_tax -> output_name] invoice=$inputs.invoice
```

### Required arguments

- `invoice` (str)

---
## invoiceops/check_totals

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | check_totals |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_match_check` |

### Command form

```text
[t:invoiceops/check_totals -> output_name] invoice=$inputs.invoice purchase_order=$inputs.purchase_order
```

### Required arguments

- `invoice` (str)
- `purchase_order` (str)

---
## invoiceops/classify_exceptions

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | classify_exceptions |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_exception_classification` |

### Command form

```text
[t:invoiceops/classify_exceptions -> output_name] match_result=$inputs.match_result invoice=$inputs.invoice
```

### Required arguments

- `match_result` (str)
- `invoice` (str)

---
## invoiceops/evidence_pack

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | evidence_pack |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_accounting_evidence_pack` |

### Command form

```text
[t:invoiceops/evidence_pack -> output_name]
```

### Optional arguments

- `frame_id` (str)
- `invoice_number` (str)
- `posting_plan_id` (str)
- `runtime_data_dir` (str)
- `profile` (str)
- `fixture_mode` (bool)
- `write_report` (bool)

---
## invoiceops/extract_invoice_fields

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | extract_invoice_fields |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_invoice` |

### Command form

```text
[t:invoiceops/extract_invoice_fields -> output_name] raw_text=$inputs.raw_text
```

### Required arguments

- `raw_text` (str)

### Optional arguments

- `source_ref` (str)

---
## invoiceops/lookup_goods_receipt

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | lookup_goods_receipt |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_match_check` |

### Command form

```text
[t:invoiceops/lookup_goods_receipt -> output_name] invoice=$inputs.invoice receipt_register=$inputs.receipt_register
```

### Required arguments

- `invoice` (str)
- `receipt_register` (str)

---
## invoiceops/lookup_purchase_order

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | lookup_purchase_order |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_match_check` |

### Command form

```text
[t:invoiceops/lookup_purchase_order -> output_name] invoice=$inputs.invoice po_register=$inputs.po_register
```

### Required arguments

- `invoice` (str)
- `po_register` (str)

---
## invoiceops/match_three_way

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | match_three_way |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_match_result` |

### Command form

```text
[t:invoiceops/match_three_way -> output_name] invoice=$inputs.invoice purchase_order=$inputs.purchase_order goods_receipt=$inputs.goods_receipt
```

### Required arguments

- `invoice` (str)
- `purchase_order` (str)
- `goods_receipt` (str)

### Optional arguments

- `invoice_register` (str)

---
## invoiceops/prepare_exception_register_write

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | prepare_exception_register_write |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_prepared_write` |

### Command form

```text
[t:invoiceops/prepare_exception_register_write -> output_name] exceptions=$inputs.exceptions
```

### Required arguments

- `exceptions` (str)

---
## invoiceops/prepare_invoice_register_write

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | prepare_invoice_register_write |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_prepared_write` |

### Command form

```text
[t:invoiceops/prepare_invoice_register_write -> output_name] invoice=$inputs.invoice
```

### Required arguments

- `invoice` (str)

---
## invoiceops/prepare_ledger_write

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | prepare_ledger_write |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_prepared_write` |

### Command form

```text
[t:invoiceops/prepare_ledger_write -> output_name] ledger_rows=$inputs.ledger_rows
```

### Required arguments

- `ledger_rows` (str)

---
## invoiceops/prepare_match_register_write

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | prepare_match_register_write |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_prepared_write` |

### Command form

```text
[t:invoiceops/prepare_match_register_write -> output_name] match_result=$inputs.match_result
```

### Required arguments

- `match_result` (str)

---
## invoiceops/prepare_rollback_plan

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | prepare_rollback_plan |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_rollback_plan` |

### Command form

```text
[t:invoiceops/prepare_rollback_plan -> output_name] prepared_write=$inputs.prepared_write
```

### Required arguments

- `prepared_write` (str)

---
## invoiceops/read_exception_register

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_exception_register |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_sheet_rows` |

### Command form

```text
[t:invoiceops/read_exception_register -> output_name]
```

### Optional arguments

- `spreadsheet_id` (str)
- `fixture_mode` (str)
- `_fixture_dir` (str)

---
## invoiceops/read_invoice_file

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_invoice_file |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_raw_invoice_text` |

### Command form

```text
[t:invoiceops/read_invoice_file -> output_name] path=$inputs.path
```

### Required arguments

- `path` (str)

### Optional arguments

- `runtime_root` (str)

---
## invoiceops/read_invoice_register

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_invoice_register |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_sheet_rows` |

### Command form

```text
[t:invoiceops/read_invoice_register -> output_name]
```

### Optional arguments

- `spreadsheet_id` (str)
- `fixture_mode` (str)
- `_fixture_dir` (str)

---
## invoiceops/read_ledger

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_ledger |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_sheet_rows` |

### Command form

```text
[t:invoiceops/read_ledger -> output_name]
```

### Optional arguments

- `spreadsheet_id` (str)
- `fixture_mode` (str)
- `_fixture_dir` (str)

---
## invoiceops/read_po_register

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_po_register |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_sheet_rows` |

### Command form

```text
[t:invoiceops/read_po_register -> output_name]
```

### Optional arguments

- `spreadsheet_id` (str)
- `fixture_mode` (str)
- `_fixture_dir` (str)

---
## invoiceops/read_receipt_register

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_receipt_register |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_sheet_rows` |

### Command form

```text
[t:invoiceops/read_receipt_register -> output_name]
```

### Optional arguments

- `spreadsheet_id` (str)
- `fixture_mode` (str)
- `_fixture_dir` (str)

---
## invoiceops/read_supplier_master

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | read_supplier_master |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_sheet_rows` |

### Command form

```text
[t:invoiceops/read_supplier_master -> output_name]
```

### Optional arguments

- `spreadsheet_id` (str)
- `fixture_mode` (str)
- `_fixture_dir` (str)

---
## invoiceops/reconcile

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | reconcile |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_reconciliation_result` |

### Command form

```text
[t:invoiceops/reconcile -> output_name]
```

### Optional arguments

- `frame_id` (str)
- `invoice_number` (str)
- `posting_plan_id` (str)
- `runtime_data_dir` (str)
- `profile` (str)
- `fixture_mode` (bool)
- `write_report` (bool)

---
## invoiceops/run_live_posting_preflight

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | run_live_posting_preflight |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_preflight_result` |

### Command form

```text
[t:invoiceops/run_live_posting_preflight -> output_name] posting_plan=$inputs.posting_plan
```

### Required arguments

- `posting_plan` (str)

### Optional arguments

- `frame_id` (str)
- `profile` (str)

---
## invoiceops/search_po_fallback

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | search_po_fallback |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_fallback_result` |

### Command form

```text
[t:invoiceops/search_po_fallback -> output_name] invoice=$inputs.invoice po_register=$inputs.po_register
```

### Required arguments

- `invoice` (str)
- `po_register` (str)

---
## invoiceops/search_receipt_fallback

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | search_receipt_fallback |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_fallback_result` |

### Command form

```text
[t:invoiceops/search_receipt_fallback -> output_name] invoice=$inputs.invoice receipt_register=$inputs.receipt_register
```

### Required arguments

- `invoice` (str)
- `receipt_register` (str)

---
## invoiceops/search_supplier_fallback

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | search_supplier_fallback |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_fallback_result` |

### Command form

```text
[t:invoiceops/search_supplier_fallback -> output_name] invoice=$inputs.invoice supplier_master=$inputs.supplier_master
```

### Required arguments

- `invoice` (str)
- `supplier_master` (str)

---
## invoiceops/validate_invoice_fields

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | validate_invoice_fields |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_invoice_validation` |

### Command form

```text
[t:invoiceops/validate_invoice_fields -> output_name] invoice=$inputs.invoice
```

### Required arguments

- `invoice` (str)

---
## invoiceops/write_posting_report

| Field | Value |
|---|---|
| Namespace | invoiceops |
| Action | write_posting_report |
| Side effect | false |
| Requires approval | false |
| Output type | `invoiceops_report` |

### Command form

```text
[t:invoiceops/write_posting_report -> output_name] posting_plan=$inputs.posting_plan
```

### Required arguments

- `posting_plan` (str)

---
## memory/set

| Field | Value |
|---|---|
| Namespace | memory |
| Action | set |
| Side effect | true |
| Requires approval | true |
| Output type | `memory_set_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:memory/set -> output_name] key=$inputs.key value=$inputs.value
```

### Required arguments

- `key` (str)
- `value` (str)

### Optional arguments

- `runtime_root` (str)

---
## message/validate_customer_status_reply

| Field | Value |
|---|---|
| Namespace | message |
| Action | validate_customer_status_reply |
| Side effect | false |
| Requires approval | false |
| Output type | `reply_validation` |

### Command form

```text
[t:message/validate_customer_status_reply -> output_name] draft_reply=$inputs.draft_reply order_context=$inputs.order_context
```

### Required arguments

- `draft_reply` (str)
- `order_context` (str)

---
## message/validate_supplier_reorder_message

| Field | Value |
|---|---|
| Namespace | message |
| Action | validate_supplier_reorder_message |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_message_validation` |

### Command form

```text
[t:message/validate_supplier_reorder_message -> output_name] supplier_message=$inputs.supplier_message draft_po=$inputs.draft_po
```

### Required arguments

- `supplier_message` (str)
- `draft_po` (str)

---
## messages/read_recent

| Field | Value |
|---|---|
| Namespace | messages |
| Action | read_recent |
| Side effect | false |
| Requires approval | false |
| Output type | `messages_read_recent_result` |

### Command form

```text
[t:messages/read_recent -> output_name] thread_name=$inputs.thread_name
```

### Required arguments

- `thread_name` (str)

### Optional arguments

- `limit` (int)
- `runtime_root` (str)
- `slowmo` (int)
- `keep_open` (bool)
- `browser_user_data_dir` (str)
- `browser_profile_dir` (str)
- `browser_cdp_url` (str)

---
## order/check_payment_status

| Field | Value |
|---|---|
| Namespace | order |
| Action | check_payment_status |
| Side effect | false |
| Requires approval | false |
| Output type | `order_payment_status_result` |

### Command form

```text
[t:order/check_payment_status -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## order/detect_delayed_orders

| Field | Value |
|---|---|
| Namespace | order |
| Action | detect_delayed_orders |
| Side effect | false |
| Requires approval | false |
| Output type | `delayed_orders_result` |

### Command form

```text
[t:order/detect_delayed_orders -> output_name]
```

### Optional arguments

- `days_overdue` (int)
- `runtime_root` (str)

---
## order/execute_release_paid_order

| Field | Value |
|---|---|
| Namespace | order |
| Action | execute_release_paid_order |
| Side effect | true |
| Requires approval | true |
| Output type | `order_release_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/execute_release_paid_order -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `dry_run` (bool)
- `runtime_root` (str)

---
## order/execute_shipment_status_update

| Field | Value |
|---|---|
| Namespace | order |
| Action | execute_shipment_status_update |
| Side effect | true |
| Requires approval | true |
| Output type | `shipment_update_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/execute_shipment_status_update -> output_name] order_ref=$inputs.order_ref shipment_status=$inputs.shipment_status
```

### Required arguments

- `order_ref` (str)
- `shipment_status` (str)

### Optional arguments

- `tracking_ref` (str)
- `dry_run` (bool)
- `runtime_root` (str)

---
## order/execute_stock_reservation

| Field | Value |
|---|---|
| Namespace | order |
| Action | execute_stock_reservation |
| Side effect | true |
| Requires approval | true |
| Output type | `stock_reservation_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/execute_stock_reservation -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `reservation_lines` (str)
- `dry_run` (bool)
- `runtime_root` (str)

---
## order/extract_ref_from_text

| Field | Value |
|---|---|
| Namespace | order |
| Action | extract_ref_from_text |
| Side effect | false |
| Requires approval | false |
| Output type | `order_ref_lookup` |

### Command form

```text
[t:order/extract_ref_from_text -> output_name] text=$inputs.text
```

### Required arguments

- `text` (str)

---
## order/items_list

| Field | Value |
|---|---|
| Namespace | order |
| Action | items_list |
| Side effect | false |
| Requires approval | false |
| Output type | `order_item_list` |

### Command form

```text
[t:order/items_list -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## order/prepare_release_paid_order

| Field | Value |
|---|---|
| Namespace | order |
| Action | prepare_release_paid_order |
| Side effect | true |
| Requires approval | true |
| Output type | `order_release_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/prepare_release_paid_order -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## order/prepare_shipment_status_update

| Field | Value |
|---|---|
| Namespace | order |
| Action | prepare_shipment_status_update |
| Side effect | true |
| Requires approval | true |
| Output type | `shipment_update_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/prepare_shipment_status_update -> output_name] order_ref=$inputs.order_ref shipment_status=$inputs.shipment_status
```

### Required arguments

- `order_ref` (str)
- `shipment_status` (str)

### Optional arguments

- `tracking_ref` (str)
- `runtime_root` (str)

---
## order/prepare_stock_reservation

| Field | Value |
|---|---|
| Namespace | order |
| Action | prepare_stock_reservation |
| Side effect | true |
| Requires approval | true |
| Output type | `stock_reservation_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:order/prepare_stock_reservation -> output_name] order_ref=$inputs.order_ref items=$inputs.items
```

### Required arguments

- `order_ref` (str)
- `items` (str)

### Optional arguments

- `runtime_root` (str)

---
## order/read

| Field | Value |
|---|---|
| Namespace | order |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `order_read_result` |

### Command form

```text
[t:order/read -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## order/search

| Field | Value |
|---|---|
| Namespace | order |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `order_list` |

### Command form

```text
[t:order/search -> output_name]
```

### Optional arguments

- `customer_id` (str)
- `order_ref` (str)
- `status` (str)

---
## order/validate_new

| Field | Value |
|---|---|
| Namespace | order |
| Action | validate_new |
| Side effect | false |
| Requires approval | false |
| Output type | `order_validation_result` |

### Command form

```text
[t:order/validate_new -> output_name] customer_id=$inputs.customer_id items=$inputs.items
```

### Required arguments

- `customer_id` (str)
- `items` (str)

### Optional arguments

- `runtime_root` (str)

---
## order_context/build

| Field | Value |
|---|---|
| Namespace | order_context |
| Action | build |
| Side effect | false |
| Requires approval | false |
| Output type | `order_context_build_result` |

### Command form

```text
[t:order_context/build -> output_name] customer=$inputs.customer order=$inputs.order shipment=$inputs.shipment
```

### Required arguments

- `customer` (str)
- `order` (str)
- `shipment` (str)

### Optional arguments

- `payment` (str)

---
## payment/read_by_order

| Field | Value |
|---|---|
| Namespace | payment |
| Action | read_by_order |
| Side effect | false |
| Requires approval | false |
| Output type | `payment_record` |

### Command form

```text
[t:payment/read_by_order -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## po/build_draft

| Field | Value |
|---|---|
| Namespace | po |
| Action | build_draft |
| Side effect | false |
| Requires approval | false |
| Output type | `draft_po` |

### Command form

```text
[t:po/build_draft -> output_name] supplier=$inputs.supplier candidates=$inputs.candidates
```

### Required arguments

- `supplier` (str)
- `candidates` (str)

---
## po/check_duplicate_open

| Field | Value |
|---|---|
| Namespace | po |
| Action | check_duplicate_open |
| Side effect | false |
| Requires approval | false |
| Output type | `duplicate_po_check` |

### Command form

```text
[t:po/check_duplicate_open -> output_name] candidates=$inputs.candidates
```

### Required arguments

- `candidates` (str)

---
## po/read

| Field | Value |
|---|---|
| Namespace | po |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `purchase_order_result` |

### Command form

```text
[t:po/read -> output_name] po_ref=$inputs.po_ref
```

### Required arguments

- `po_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## po/validate_draft

| Field | Value |
|---|---|
| Namespace | po |
| Action | validate_draft |
| Side effect | false |
| Requires approval | false |
| Output type | `po_validation` |

### Command form

```text
[t:po/validate_draft -> output_name] draft_po=$inputs.draft_po
```

### Required arguments

- `draft_po` (str)

---
## purchase_order/search_open_by_sku

| Field | Value |
|---|---|
| Namespace | purchase_order |
| Action | search_open_by_sku |
| Side effect | false |
| Requires approval | false |
| Output type | `purchase_order_list` |

### Command form

```text
[t:purchase_order/search_open_by_sku -> output_name] sku=$inputs.sku
```

### Required arguments

- `sku` (str)

---
## q/extract_order_ref

| Field | Value |
|---|---|
| Namespace | q |
| Action | extract_order_ref |
| Side effect | false |
| Requires approval | false |
| Output type | `order_ref_result` |

### Command form

```text
[t:q/extract_order_ref -> output_name] text=$inputs.text
```

### Required arguments

- `text` (str)

---
## receipt/read_by_po

| Field | Value |
|---|---|
| Namespace | receipt |
| Action | read_by_po |
| Side effect | false |
| Requires approval | false |
| Output type | `goods_receipt_result` |

### Command form

```text
[t:receipt/read_by_po -> output_name] po_ref=$inputs.po_ref
```

### Required arguments

- `po_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## recon/match_payments

| Field | Value |
|---|---|
| Namespace | recon |
| Action | match_payments |
| Side effect | false |
| Requires approval | false |
| Output type | `reconciliation_result` |

### Command form

```text
[t:recon/match_payments -> output_name] payments=$inputs.payments orders=$inputs.orders invoices=$inputs.invoices ledger_entries=$inputs.ledger_entries
```

### Required arguments

- `payments` (str)
- `orders` (str)
- `invoices` (str)
- `ledger_entries` (str)

---
## recon/validate_result

| Field | Value |
|---|---|
| Namespace | recon |
| Action | validate_result |
| Side effect | false |
| Requires approval | false |
| Output type | `reconciliation_validation` |

### Command form

```text
[t:recon/validate_result -> output_name] reconciliation_result=$inputs.reconciliation_result
```

### Required arguments

- `reconciliation_result` (str)

---
## report/generate

| Field | Value |
|---|---|
| Namespace | report |
| Action | generate |
| Side effect | false |
| Requires approval | false |
| Output type | `report_result` |

### Command form

```text
[t:report/generate -> output_name] frame_id=$inputs.frame_id
```

### Required arguments

- `frame_id` (str)

### Optional arguments

- `runtime_data_dir` (str)

---
## sheet/create

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | create |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_create_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/create -> output_name] title=$inputs.title
```

### Required arguments

- `title` (str)

---
## sheet/prepare_write_rows

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | prepare_write_rows |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_write_rows_pending` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/prepare_write_rows -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name rows=$inputs.rows
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)
- `rows` (str)

### Optional arguments

- `mode` (str)

---
## sheet/read

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `sheet_rows` |

### Command form

```text
[t:sheet/read -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)

---
## sheet/read_range

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | read_range |
| Side effect | false |
| Requires approval | false |
| Output type | `sheet_read_range_result` |

### Command form

```text
[t:sheet/read_range -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)

---
## sheet/write

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | write |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_write_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/write -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name values_json=$inputs.values_json
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)
- `values_json` (str)

### Optional arguments

- `mode` (str)

---
## sheet/write_rows

| Field | Value |
|---|---|
| Namespace | sheet |
| Action | write_rows |
| Side effect | true |
| Requires approval | true |
| Output type | `sheet_write_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:sheet/write_rows -> output_name] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.range_name rows=$inputs.rows
```

### Required arguments

- `spreadsheet_id` (str)
- `range_name` (str)
- `rows` (str)

### Optional arguments

- `write_mode` (str)
- `expected_headers` (str)
- `source_ref` (str)
- `dry_run` (bool)

---
## shipment/read

| Field | Value |
|---|---|
| Namespace | shipment |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `shipment_read_result` |

### Command form

```text
[t:shipment/read -> output_name] order_ref=$inputs.order_ref
```

### Required arguments

- `order_ref` (str)

---
## supplier/prepare_message_action

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | prepare_message_action |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_message_pending_action` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier/prepare_message_action -> output_name] supplier=$inputs.supplier draft_po=$inputs.draft_po message=$inputs.message
```

### Required arguments

- `supplier` (str)
- `draft_po` (str)
- `message` (str)

---
## supplier/read

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_record` |

### Command form

```text
[t:supplier/read -> output_name] supplier_id=$inputs.supplier_id
```

### Required arguments

- `supplier_id` (str)

---
## supplier/search_active

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | search_active |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_list` |

### Command form

```text
[t:supplier/search_active -> output_name]
```

---
## supplier/select_for_sku

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | select_for_sku |
| Side effect | false |
| Requires approval | false |
| Output type | `selected_supplier` |

### Command form

```text
[t:supplier/select_for_sku -> output_name] candidates=$inputs.candidates
```

### Required arguments

- `candidates` (str)

---
## supplier/send_message

| Field | Value |
|---|---|
| Namespace | supplier |
| Action | send_message |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier/send_message -> output_name] to=$inputs.to subject=$inputs.subject body=$inputs.body
```

### Required arguments

- `to` (str)
- `subject` (str)
- `body` (str)

### Optional arguments

- `draft_po` (str)
- `dry_run` (str)
- `runtime_root` (str)

---
## supplier_invoice/build_exception_report

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | build_exception_report |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_exception_report_result` |

### Command form

```text
[t:supplier_invoice/build_exception_report -> output_name] invoice=$inputs.invoice purchase_order=$inputs.purchase_order receipts=$inputs.receipts match_result=$inputs.match_result
```

### Required arguments

- `invoice` (str)
- `purchase_order` (str)
- `receipts` (str)
- `match_result` (str)

### Optional arguments

- `exception_summary` (str)
- `runtime_root` (str)

---
## supplier_invoice/check_duplicate

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | check_duplicate |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_duplicate_check_result` |

### Command form

```text
[t:supplier_invoice/check_duplicate -> output_name] supplier_id=$inputs.supplier_id supplier_invoice_number=$inputs.supplier_invoice_number
```

### Required arguments

- `supplier_id` (str)
- `supplier_invoice_number` (str)

### Optional arguments

- `invoice_ref` (str)
- `runtime_root` (str)

---
## supplier_invoice/execute_ledger_write

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | execute_ledger_write |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_invoice_ledger_write_execution_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier_invoice/execute_ledger_write -> output_name] ledger_rows=$inputs.ledger_rows
```

### Required arguments

- `ledger_rows` (str)

### Optional arguments

- `dry_run` (str)
- `runtime_root` (str)

---
## supplier_invoice/match_three_way

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | match_three_way |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_match_result` |

### Command form

```text
[t:supplier_invoice/match_three_way -> output_name] invoice=$inputs.invoice purchase_order=$inputs.purchase_order receipts=$inputs.receipts
```

### Required arguments

- `invoice` (str)
- `purchase_order` (str)
- `receipts` (str)

### Optional arguments

- `tolerance_amount` (float)
- `tolerance_percent` (float)
- `runtime_root` (str)

---
## supplier_invoice/prepare_ledger_write

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | prepare_ledger_write |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_invoice_ledger_write_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier_invoice/prepare_ledger_write -> output_name] invoice=$inputs.invoice match_result=$inputs.match_result
```

### Required arguments

- `invoice` (str)
- `match_result` (str)

### Optional arguments

- `runtime_root` (str)

---
## supplier_invoice/prepare_match_run_write

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | prepare_match_run_write |
| Side effect | true |
| Requires approval | true |
| Output type | `supplier_invoice_match_write_prepare_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:supplier_invoice/prepare_match_run_write -> output_name] match_result=$inputs.match_result
```

### Required arguments

- `match_result` (str)

### Optional arguments

- `runtime_root` (str)

---
## supplier_invoice/read

| Field | Value |
|---|---|
| Namespace | supplier_invoice |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `supplier_invoice_result` |

### Command form

```text
[t:supplier_invoice/read -> output_name] invoice_ref=$inputs.invoice_ref
```

### Required arguments

- `invoice_ref` (str)

### Optional arguments

- `runtime_root` (str)

---
## test/echo

| Field | Value |
|---|---|
| Namespace | test |
| Action | echo |
| Side effect | false |
| Requires approval | false |
| Output type | `test_echo_result` |

### Command form

```text
[t:test/echo -> output_name]
```

### Optional arguments

- `message` (str)
- `event_id` (str)

---
## wa/read

| Field | Value |
|---|---|
| Namespace | wa |
| Action | read |
| Side effect | false |
| Requires approval | false |
| Output type | `whatsapp_messages` |

### Command form

```text
[t:wa/read -> output_name] chat=$inputs.chat
```

### Required arguments

- `chat` (str)

### Optional arguments

- `limit` (int)

---
## wa/search

| Field | Value |
|---|---|
| Namespace | wa |
| Action | search |
| Side effect | false |
| Requires approval | false |
| Output type | `whatsapp_search_result` |

### Command form

```text
[t:wa/search -> output_name] chat=$inputs.chat
```

### Required arguments

- `chat` (str)

---
## wa/send

| Field | Value |
|---|---|
| Namespace | wa |
| Action | send |
| Side effect | true |
| Requires approval | true |
| Output type | `whatsapp_send_result` |

> **Safety note:** This tool stages or performs a side effect and must be approval-gated before execution.

### Command form

```text
[t:wa/send -> output_name] chat=$inputs.chat
```

### Required arguments

- `chat` (str)

### Optional arguments

- `message` (str)
- `file_path` (str)
- `caption` (str)
- `kind` (str)

---
