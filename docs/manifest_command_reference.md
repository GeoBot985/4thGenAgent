# Manifest Command Reference

## Command types

`[q:action -> output]`
- LLM / semantic micro-action
- Use for extraction, classification, drafting, summarization, and other bounded language tasks.

`[t:namespace/action -> output]`
- Deterministic tool action
- Use for reads, lookups, structured tool calls, and other runtime-backed operations.

`[validate:rule_id]`
- Run a named validation rule
- Use to prove the result is acceptable before completion or approval.

`[maintenance:action -> output]`
- Maintenance, report, or artifact command
- Use for report generation, evidence packaging, and other maintenance outputs.

## Examples

```text
[q:extract_order_ref -> order_ref] text=$inputs.message
[q:classify_customer_message -> category] text=$inputs.message
[q:draft_customer_status_reply -> draft_reply] context=$outputs.order_context
[t:customer/read -> customer] customer_id=$inputs.customer_id
[t:order/read -> order] order_ref=$outputs.order_ref.order_ref
[t:shipment/read -> shipment] order_ref=$outputs.order_ref.order_ref
[t:sheet/read_range -> payments_sheet] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.payments_range
[validate:customer_owns_order]
[validate:reply_matches_facts]
```

## Variable references

- `$inputs.message`
- `$inputs.customer_id`
- `$outputs.order_ref`
- `$outputs.order_ref.order_ref`
- `$outputs.customer.customer_id`
- `$outputs.order.status`

## Rule

Every step that produces data should write it to an output alias using `-> output_name`.
