# Tool Inventory Report

Generated: 2026-05-18T18:29:22Z

Report JSON: D:/Temp/pytest-of-GeorgeC/pytest-1590/test_inventory_includes_toolpa0/runtime_data/tool_inventory/tool_inventory.json
Report Markdown: D:/Temp/pytest-of-GeorgeC/pytest-1590/test_inventory_includes_toolpa0/runtime_data/tool_inventory/tool_inventory.md

## Summary

| Metric | Count |
|---|---:|
| Total tools | 66 |
| Migrated tool-pack tools | 4 |
| Legacy fallback tools | 62 |
| External enabled tools | 0 |
| Total tool packs | 2 |
| Optional disabled tools | 10 |
| Side-effect tools | 15 |
| Live side-effect allowed | 0 |

## Tools

| Tool | Source | Pack | Side Effect | Requires Approval | Live Side Effect | Output Type |
|---|---|---|---:|---:|---:|---|
| acct/build_recon_sheet_rows | legacy_fallback |  | no | no | no | recon_sheet_rows |
| acct/load_invoices | legacy_fallback |  | no | no | no | accounting_invoices |
| acct/load_ledger | legacy_fallback |  | no | no | no | accounting_ledger |
| acct/load_orders | legacy_fallback |  | no | no | no | accounting_orders |
| acct/load_payments | legacy_fallback |  | no | no | no | accounting_payments |
| business/get_order_context | migrated_toolpack | core_business | no | no | no | business_order_context |
| cal/create | legacy_fallback |  | yes | yes | no | calendar_create_result |
| cal/next | legacy_fallback |  | no | no | no | calendar_event_list |
| cal/remove | legacy_fallback |  | yes | yes | no | calendar_remove_result |
| cal/search | legacy_fallback |  | no | no | no | calendar_event_list |
| customer/build_status_context | legacy_fallback |  | no | no | no | status_context |
| customer/extract_order_ref | legacy_fallback |  | no | no | no | order_ref_result |
| customer/order_context | legacy_fallback |  | no | no | no | order_context_result |
| customer/prepare_message_action | legacy_fallback |  | yes | yes | no | customer_message_action |
| customer/read | legacy_fallback |  | no | no | no | customer_read_result |
| customer/search | legacy_fallback |  | no | no | no | customer_list |
| customer/validate_owns_order | legacy_fallback |  | no | no | no | ownership_check |
| customer/validate_status_reply | legacy_fallback |  | no | no | no | reply_validation |
| file/exists | legacy_fallback |  | no | no | no | file_exists_result |
| file/list | legacy_fallback |  | no | no | no | file_list_result |
| file/read_json | legacy_fallback |  | no | no | no | file_read_json_result |
| file/write_json | legacy_fallback |  | yes | yes | no | file_write_json_result |
| g/check | legacy_fallback |  | no | no | no | gmail_check_result |
| g/send | legacy_fallback |  | yes | yes | no | gmail_send_result |
| gb/book | legacy_fallback |  | yes | yes | no | gobook_booking_result |
| gb/cancel | legacy_fallback |  | yes | yes | no | gobook_cancel_result |
| gb/list | legacy_fallback |  | no | no | no | gobook_booking_list |
| gb/open_courts | legacy_fallback |  | no | no | no | gobook_open_court_list |
| inventory/filter_reorder_candidates | legacy_fallback |  | no | no | no | reorder_candidates |
| inventory/read | legacy_fallback |  | no | no | no | inventory_record |
| inventory/search_low_stock | legacy_fallback |  | no | no | no | low_stock_result |
| memory/set | migrated_toolpack | core_memory | yes | yes | no | memory_set_result |
| message/validate_customer_status_reply | legacy_fallback |  | no | no | no | reply_validation |
| message/validate_supplier_reorder_message | legacy_fallback |  | no | no | no | supplier_message_validation |
| messages/read_recent | legacy_fallback |  | no | no | no | messages_read_recent_result |
| order/extract_ref_from_text | legacy_fallback |  | no | no | no | order_ref_lookup |
| order/items_list | legacy_fallback |  | no | no | no | order_item_list |
| order/read | legacy_fallback |  | no | no | no | order_read_result |
| order/search | legacy_fallback |  | no | no | no | order_list |
| order_context/build | legacy_fallback |  | no | no | no | order_context_build_result |
| payment/read_by_order | legacy_fallback |  | no | no | no | payment_record |
| po/build_draft | legacy_fallback |  | no | no | no | draft_po |
| po/check_duplicate_open | legacy_fallback |  | no | no | no | duplicate_po_check |
| po/validate_draft | legacy_fallback |  | no | no | no | po_validation |
| purchase_order/search_open_by_sku | legacy_fallback |  | no | no | no | purchase_order_list |
| q/extract_order_ref | migrated_toolpack | core_llm_micro | no | no | no | order_ref_result |
| recon/match_payments | legacy_fallback |  | no | no | no | reconciliation_result |
| recon/validate_result | legacy_fallback |  | no | no | no | reconciliation_validation |
| report/generate | migrated_toolpack | core_reports | no | no | no | report_result |
| sheet/create | legacy_fallback |  | yes | yes | yes | sheet_create_result |
| sheet/prepare_write_rows | legacy_fallback |  | yes | yes | no | sheet_write_rows_pending |
| sheet/read | legacy_fallback |  | no | no | no | sheet_rows |
| sheet/read_range | legacy_fallback |  | no | no | no | sheet_read_range_result |
| sheet/write | legacy_fallback |  | yes | yes | yes | sheet_write_result |
| sheet/write_rows | legacy_fallback |  | yes | yes | yes | sheet_write_rows_result |
| shipment/read | legacy_fallback |  | no | no | no | shipment_read_result |
| supplier/prepare_message_action | legacy_fallback |  | yes | yes | no | supplier_message_pending_action |
| supplier/read | legacy_fallback |  | no | no | no | supplier_record |
| supplier/search_active | legacy_fallback |  | no | no | no | supplier_list |
| supplier/select_for_sku | legacy_fallback |  | no | no | no | selected_supplier |
| supplier/send_message | legacy_fallback |  | yes | yes | no | supplier_send_result |
| supplier_invoice/read | legacy_fallback |  | no | no | no | supplier_invoice_record |
| test/echo | legacy_fallback |  | no | no | no | test_echo_result |
| wa/read | legacy_fallback |  | no | no | no | whatsapp_messages |
| wa/search | legacy_fallback |  | no | no | no | whatsapp_search_result |
| wa/send | legacy_fallback |  | yes | yes | no | whatsapp_send_result |

## Tool Packs

| Tool Pack | Status | Environments | Classification | Tool Count | Last Check | Lifecycle Report |
|---|---|---|---|---:|---|---|
| demo_echo | UNTESTED | demo, dev, test | optional | 3 | 2026-05-18T18:29:22Z | D:/Temp/pytest-of-GeorgeC/pytest-1590/test_inventory_includes_toolpa0/runtime_data/toolpacks/lifecycle/demo_echo_lifecycle.md |
| google_workspace | UNTESTED | dev, test | optional | 7 | 2026-05-18T18:29:22Z | D:/Temp/pytest-of-GeorgeC/pytest-1590/test_inventory_includes_toolpa0/runtime_data/toolpacks/lifecycle/google_workspace_lifecycle.md |
