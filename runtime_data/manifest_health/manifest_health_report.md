# Manifest Health Report

Generated: 2026-05-24T09:51:55.983820Z

Verdict: HEALTHY

## Summary

| Metric | Count |
|---|---:|
| Total manifests | 19 |
| Healthy | 0 |
| Warnings | 0 |
| Failed | 0 |
| Repairable | 9 |
| Manual fix required | 0 |
| Critical | 0 |

## Manifest Results

| Health | Manifest | Validation | Smoke | Repairable | Top Findings | Next Action |
|---|---|---|---|---:|---|---|
| SMOKE_SKIPPED | customer.status_llm_e2e | PASS | SKIPPED | 3 | input_declared_but_not_used, input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | invoiceops.process_supplier_invoice_v1 | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | llm.classify_customer_message | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | llm.customer_status_reply | PASS | SKIPPED | 2 | input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | llm.extract_order_ref | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.cleanup_dry_run | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.artifact_index_rebuild | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.report_failed_runs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.report_live_packs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | maintenance.report_pending_runs | PASS | SKIPPED | 0 |  | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | order.detect_delayed | PASS | SKIPPED | 1 | input_declared_but_not_used, event_trigger_without_route_note | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | order.release_paid | PASS | SKIPPED | 1 | input_declared_but_not_used, event_trigger_without_route_note | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | order.reserve_stock | PASS | SKIPPED | 1 | input_declared_but_not_used, event_trigger_without_route_note | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | order.update_shipment_status | PASS | SKIPPED | 1 | input_declared_but_not_used, event_trigger_without_route_note | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | order.validate_new | PASS | SKIPPED | 1 | input_declared_but_not_used, event_trigger_without_route_note | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | supplier_invoice.match_to_po_receipt | PASS | SKIPPED | 1 | input_declared_but_not_used, event_trigger_without_route_note | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | accounting.payment_reconciliation | PASS | SKIPPED | 0 | event_trigger_without_route_note | Run smoke test manually with sample inputs. |
| SMOKE_SKIPPED | customer.message_status_check | PASS | SKIPPED | 3 | input_declared_but_not_used, input_declared_but_not_used, input_declared_but_not_used | Open Auto-Fix Preview. |
| SMOKE_SKIPPED | procurement.low_stock_reorder | PASS | SKIPPED | 0 | event_trigger_without_route_note | Run smoke test manually with sample inputs. |
