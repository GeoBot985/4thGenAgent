# TaskFrame Run Report

## 1. Executive Summary

| Field | Value |
|---|---|
| Frame ID | frame_e8375704f06540e18f362a3adc36c2b9 |
| Manifest | customer.status_llm_e2e |
| State | COMPLETED |
| Outcome | Run completed successfully. |
| Pending Actions | 1 |
| Executed Actions | 1 |
| Errors | 0 |

## 2. Trigger / Event

- Event ID: evt_cfb15e03ed5240aa8ba3d8568e2f4e21
- Event Type: manual.customer_status_llm_e2e
- Source: operator_scenario_pack

```json
{
  "channel": "callcentre",
  "customer_id": "CUST-1001",
  "event_id": "evt_cfb15e03ed5240aa8ba3d8568e2f4e21",
  "event_type": "manual.customer_status_llm_e2e",
  "message": "Where is my order ORD-10042?",
  "source": "operator_scenario_pack"
}
```

## 3. Route and Manifest

- Manifest ID: customer.status_llm_e2e
- Manifest Name: 
- Step Count: 14
- Validation Count: 62

## 4. Runtime Final State

- Final State: COMPLETED
- Current Step ID: 
- Errors Count: 0

```json
{
  "errors": [],
  "failed_steps": [],
  "final_state": "COMPLETED",
  "message": "Completion gate passed.",
  "missing_executed_actions": [],
  "missing_outputs": [],
  "missing_pending_actions": [],
  "ok": true,
  "status": "COMPLETED",
  "validation_summary": {
    "failed": 0,
    "passed": 62
  }
}
```

## 5. Step Timeline

| # | Step | Kind | Action | Status | Attempts | Result | Error |
|---:|---|---|---|---|---:|---|---|
| 1 | extract_order_ref | llm | extract_order_ref | COMPLETED | 1 | order_ref |  |
| 2 | classify_message | llm | classify_customer_message | COMPLETED | 1 | category |  |
| 3 | validate_order_ref | validate | order_ref_has_value | COMPLETED | 1 | None |  |
| 4 | lookup_customer | tool | read | COMPLETED | 1 | customer |  |
| 5 | lookup_order | tool | read | COMPLETED | 1 | order |  |
| 6 | lookup_shipment | tool | read | COMPLETED | 1 | shipment |  |
| 7 | read_payment | tool | read_by_order | COMPLETED | 1 | payment |  |
| 8 | build_order_context | tool | build | COMPLETED | 1 | order_context |  |
| 9 | validate_customer_owns_order | tool | validate_owns_order | COMPLETED | 1 | ownership_check |  |
| 10 | build_status_context | tool | build_status_context | COMPLETED | 1 | status_context |  |
| 11 | draft_reply | llm | draft_customer_status_reply | COMPLETED | 1 | draft_reply |  |
| 12 | check_reply_against_facts | llm | compare_reply_to_facts | COMPLETED | 1 | reply_check |  |
| 13 | validate_status_reply | tool | validate_customer_status_reply | COMPLETED | 1 | reply_validation |  |
| 14 | stage_customer_reply | tool | prepare_message_action | STAGED | 1 | customer_reply_send |  |

## 6. LLM Calls

- step_id: extract_order_ref
  action: extract_order_ref
  provider: fake
  model: fake
  ok: True
  output_ref: 
  micro_tool: True
- step_id: classify_message
  action: classify_customer_message
  provider: fake
  model: fake
  ok: True
  output_ref: 
  micro_tool: True
- step_id: draft_reply
  action: draft_customer_status_reply
  provider: fake
  model: fake
  ok: True
  output_ref: 
  micro_tool: True
- step_id: check_reply_against_facts
  action: compare_reply_to_facts
  provider: fake
  model: fake
  ok: True
  output_ref: 
  micro_tool: True
## 7. Tool Calls

- step_id: lookup_customer
  tool: customer/read
  namespace: customer
  action: read
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: customer
  ok: True
  error: 
- step_id: lookup_order
  tool: order/read
  namespace: order
  action: read
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: order
  ok: True
  error: 
- step_id: lookup_shipment
  tool: shipment/read
  namespace: shipment
  action: read
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: shipment
  ok: True
  error: 
- step_id: read_payment
  tool: payment/read_by_order
  namespace: payment
  action: read_by_order
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: payment
  ok: True
  error: 
- step_id: build_order_context
  tool: order_context/build
  namespace: order_context
  action: build
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: order_context
  ok: True
  error: 
- step_id: validate_customer_owns_order
  tool: customer/validate_owns_order
  namespace: customer
  action: validate_owns_order
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: ownership_check
  ok: True
  error: Customer owns order.
- step_id: build_status_context
  tool: customer/build_status_context
  namespace: customer
  action: build_status_context
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: status_context
  ok: True
  error: 
- step_id: validate_status_reply
  tool: message/validate_customer_status_reply
  namespace: message
  action: validate_customer_status_reply
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: reply_validation
  ok: True
  error: 
- step_id: stage_customer_reply
  tool: customer/prepare_message_action
  namespace: customer
  action: prepare_message_action
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: customer_reply_send
  ok: True
  error: 
- step_id: stage_customer_reply
  tool: 
  namespace: customer
  action: prepare_message_action
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: customer_reply_send
  ok: True
  error: 
## 8. Outputs

### Output: business_lookups
```json
{
  "customer": {
    "customer_id": "CUST-1001",
    "email": "alex@example.test",
    "name": "Alex",
    "preferred_channel": "whatsapp",
    "status": "active",
    "whatsapp_chat": "Alex Customer"
  },
  "error": "",
  "facts": [
    "Customer CUST-1001 is Alex.",
    "Order ORD-10042 belongs to CUST-1001.",
    "Order ORD-10042 status is shipped.",
    "Shipment SHIP-9001 status is in_transit."
  ],
  "ok": true,
  "order": {
    "created_date": "2026-04-25",
    "currency": "ZAR",
    "customer_id": "CUST-1001",
    "order_id": "ORD-10042",
    "order_ref": "ORD-10042",
    "status": "shipped",
    "total_amount": 1299.99
  },
  "payment": {},
  "shipment": {
    "carrier": "DemoCourier",
    "estimated_delivery": "2026-05-03",
    "order_ref": "ORD-10042",
    "shipment_id": "SHIP-9001",
    "status": "in_transit",
    "tracking_ref": "TRK-778899"
  }
}
```

### Output: category
```json
{
  "confidence": "high",
  "label": "order_status",
  "reason": "Customer asks where their order is."
}
```

### Output: customer
```json
{
  "customer_id": "CUST-1001",
  "email": "alex@example.test",
  "name": "Alex",
  "preferred_channel": "whatsapp",
  "status": "active",
  "whatsapp_chat": "Alex Customer"
}
```

### Output: customer_reply_send
```json
{
  "approved_execution": true,
  "args": {
    "chat": "Alex Customer",
    "message": {
      "body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
      "included_order_ref": true,
      "included_status": true,
      "invented_compensation": false,
      "reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
      "tone": "professional"
    }
  },
  "dry_run": true,
  "function": "whatsapp_send",
  "tool": "wa/send"
}
```

### Output: draft_reply
```json
{
  "body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
  "included_order_ref": true,
  "included_status": true,
  "invented_compensation": false,
  "reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
  "tone": "professional"
}
```

### Output: order
```json
{
  "created_date": "2026-04-25",
  "currency": "ZAR",
  "customer_id": "CUST-1001",
  "order_id": "ORD-10042",
  "order_ref": "ORD-10042",
  "status": "shipped",
  "total_amount": 1299.99
}
```

### Output: order_context
```json
{
  "customer": {
    "customer_id": "CUST-1001",
    "email": "alex@example.test",
    "name": "Alex",
    "preferred_channel": "whatsapp",
    "status": "active",
    "whatsapp_chat": "Alex Customer"
  },
  "error": "",
  "facts": [
    "Customer CUST-1001 is Alex.",
    "Order ORD-10042 belongs to CUST-1001.",
    "Order ORD-10042 status is shipped.",
    "Shipment SHIP-9001 status is in_transit."
  ],
  "ok": true,
  "order": {
    "created_date": "2026-04-25",
    "currency": "ZAR",
    "customer_id": "CUST-1001",
    "order_id": "ORD-10042",
    "order_ref": "ORD-10042",
    "status": "shipped",
    "total_amount": 1299.99
  },
  "payment": {},
  "shipment": {
    "carrier": "DemoCourier",
    "estimated_delivery": "2026-05-03",
    "order_ref": "ORD-10042",
    "shipment_id": "SHIP-9001",
    "status": "in_transit",
    "tracking_ref": "TRK-778899"
  }
}
```

### Output: order_ref
```json
{
  "confidence": "high",
  "order_ref": "ORD-10042",
  "reason": "Detected explicit order reference."
}
```

### Output: ownership_check
```json
{
  "customer_id": "CUST-1001",
  "error": "",
  "message": "Customer owns order.",
  "ok": true,
  "order_customer_id": "CUST-1001",
  "order_ref": "ORD-10042"
}
```

### Output: payment
```json
{
  "args": {
    "order_ref": "ORD-10042"
  },
  "dry_run": true,
  "function": "payment_read_by_order",
  "tool": "payment/read_by_order"
}
```

### Output: reply_check
```json
{
  "matches_facts": true,
  "missing_required_facts": [],
  "ok": true,
  "reason": "Deterministic fake response.",
  "unsupported_claims": []
}
```

### Output: reply_validation
```json
{
  "checks": [],
  "errors": [],
  "facts": [
    "Customer CUST-1001 is Alex.",
    "Order ORD-10042 belongs to CUST-1001.",
    "Order ORD-10042 status is shipped.",
    "Shipment SHIP-9001 status is in_transit."
  ],
  "ok": true,
  "order_context": {
    "customer": {
      "customer_id": "CUST-1001",
      "email": "alex@example.test",
      "name": "Alex",
      "preferred_channel": "whatsapp",
      "status": "active",
      "whatsapp_chat": "Alex Customer"
    },
    "error": "",
    "facts": [
      "Customer CUST-1001 is Alex.",
      "Order ORD-10042 belongs to CUST-1001.",
      "Order ORD-10042 status is shipped.",
      "Shipment SHIP-9001 status is in_transit."
    ],
    "ok": true,
    "order": {
      "created_date": "2026-04-25",
      "currency": "ZAR",
      "customer_id": "CUST-1001",
      "order_id": "ORD-10042",
      "order_ref": "ORD-10042",
      "status": "shipped",
      "total_amount": 1299.99
    },
    "payment": {},
    "shipment": {
      "carrier": "DemoCourier",
      "estimated_delivery": "2026-05-03",
      "order_ref": "ORD-10042",
      "shipment_id": "SHIP-9001",
      "status": "in_transit",
      "tracking_ref": "TRK-778899"
    }
  },
  "reply": {
    "body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
    "included_order_ref": true,
    "included_status": true,
    "invented_compensation": false,
    "reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.",
    "tone": "professional"
  }
}
```

### Output: shipment
```json
{
  "carrier": "DemoCourier",
  "estimated_delivery": "2026-05-03",
  "order_ref": "ORD-10042",
  "shipment_id": "SHIP-9001",
  "status": "in_transit",
  "tracking_ref": "TRK-778899"
}
```

### Output: status_context
```json
{
  "customer": {
    "customer_id": "CUST-1001",
    "email": "alex@example.test",
    "name": "Alex",
    "preferred_channel": "whatsapp",
    "status": "active",
    "whatsapp_chat": "Alex Customer"
  },
  "error": "",
  "facts": [
    "Customer CUST-1001 is Alex.",
    "Order ORD-10042 belongs to CUST-1001.",
    "Order ORD-10042 status is shipped.",
    "Shipment SHIP-9001 status is in_transit."
  ],
  "ok": true,
  "order": {
    "created_date": "2026-04-25",
    "currency": "ZAR",
    "customer_id": "CUST-1001",
    "order_id": "ORD-10042",
    "order_ref": "ORD-10042",
    "status": "shipped",
    "total_amount": 1299.99
  },
  "payment": {},
  "shipment": {
    "carrier": "DemoCourier",
    "estimated_delivery": "2026-05-03",
    "order_ref": "ORD-10042",
    "shipment_id": "SHIP-9001",
    "status": "in_transit",
    "tracking_ref": "TRK-778899"
  }
}
```

## 9. Evidence

Evidence count: 1
- step_id: build_status_context
  source: 
  record_id: 
  data: {"datasets": [], "kind": "business_lookup", "step_id": "build_status_context"}
## 10. Validations

| Validation ID | Type | OK | Message | Step | Data |
|---|---|---|---|---|---|
| extract_order_ref_order_ref | llm_micro_tool_schema | ok |  |  | {"order_ref": "ORD-10042"} |
| extract_order_ref_confidence | llm_micro_tool_schema | ok |  |  | {"confidence": "high"} |
| extract_order_ref_reason | llm_micro_tool_schema | ok |  |  | {"reason": "Detected explicit order reference."} |
| extract_order_ref_confidence_allowed | llm_micro_tool_schema | ok |  |  | {"confidence": "high"} |
| extract_order_ref_format | llm_micro_tool_schema | ok |  |  | {"order_ref": "ORD-10042"} |
| classify_customer_message_label | llm_micro_tool_schema | ok |  |  | {"label": "order_status"} |
| classify_customer_message_confidence | llm_micro_tool_schema | ok |  |  | {"confidence": "high"} |
| classify_customer_message_reason | llm_micro_tool_schema | ok |  |  | {"reason": "Customer asks where their order is."} |
| classify_customer_message_label_allowed | llm_micro_tool_schema | ok |  |  | {"label": "order_status"} |
| classify_customer_message_confidence_allowed | llm_micro_tool_schema | ok |  |  | {"confidence": "high"} |
| classify_customer_message_label_legacy_allowed | llm_micro_tool_schema | ok |  |  | {"label": "order_status"} |
| order_ref_has_value | output_has_fields | ok | Output has fields: order_ref |  | {"fields": ["order_ref", "confidence", "reason"], "output": "order_ref"} |
| draft_customer_status_reply_reply | llm_micro_tool_schema | ok |  |  | {"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit."} |
| draft_customer_status_reply_tone | llm_micro_tool_schema | ok |  |  | {"tone": "professional"} |
| draft_customer_status_reply_included_order_ref | llm_micro_tool_schema | ok |  |  | {"included_order_ref": true} |
| draft_customer_status_reply_included_status | llm_micro_tool_schema | ok |  |  | {"included_status": true} |
| draft_customer_status_reply_invented_compensation | llm_micro_tool_schema | ok |  |  | {"invented_compensation": false} |
| draft_customer_status_reply_tone_allowed | llm_micro_tool_schema | ok |  |  | {"tone": "professional"} |
| draft_customer_status_reply_compensation | llm_micro_tool_schema | ok |  |  | {"invented_compensation": false} |
| draft_customer_status_reply_forbidden_claims | llm_micro_tool_schema | ok |  |  | {"reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit."} |
| compare_reply_to_facts_ok | llm_micro_tool_schema | ok |  |  | {"ok": true} |
| compare_reply_to_facts_matches_facts | llm_micro_tool_schema | ok |  |  | {"matches_facts": true} |
| compare_reply_to_facts_unsupported_claims | llm_micro_tool_schema | ok |  |  | {"unsupported_claims": []} |
| compare_reply_to_facts_missing_required_facts | llm_micro_tool_schema | ok |  |  | {"missing_required_facts": []} |
| compare_reply_to_facts_reason | llm_micro_tool_schema | ok |  |  | {"reason": "Deterministic fake response."} |
| compare_reply_to_facts_fact_check | llm_micro_tool_schema | ok |  |  | {"matches_facts": true, "missing_required_facts": [], "ok": true, "reason": "Deterministic fake response.", "unsupported_claims": []} |
| no_errors | no_errors | ok | No runtime errors. |  | {} |
| order_ref_has_value | output_has_fields | ok | Output has fields: order_ref |  | {"fields": ["order_ref", "confidence", "reason"], "output": "order_ref"} |
| order_ref_confidence_ok | output_field_in | ok | Output field is allowed: order_ref.confidence |  | {"field": "confidence", "output": "order_ref", "value": "high", "values": ["high", "medium"]} |
| category_is_order_status | output_field_equals | ok | Output field matches: category.label |  | {"field": "label", "output": "category", "value": "order_status"} |
| customer_exists | output_has_fields | ok | Output has fields: customer |  | {"fields": ["customer_id", "name", "preferred_channel"], "output": "customer"} |
| order_exists | output_has_fields | ok | Output has fields: order |  | {"fields": ["order_ref", "customer_id", "status", "created_date", "total_amount"], "output": "order"} |
| shipment_exists | output_has_fields | ok | Output has fields: shipment |  | {"fields": ["order_ref", "shipment_id", "status", "carrier", "tracking_ref", "estimated_delivery"], "output": "shipment"} |
| order_belongs_to_customer | output_field_equals | ok | Output field matches: order.customer_id |  | {"field": "customer_id", "output": "order", "value": "CUST-1001"} |
| shipment_matches_order | output_field_equals | ok | Output field matches: shipment.order_ref |  | {"field": "order_ref", "output": "shipment", "value": "ORD-10042"} |
| status_context_exists | output_exists | ok | Output exists: status_context |  | {"output": "status_context"} |
| draft_reply_includes_order_ref | output_field_equals | ok | Output field matches: draft_reply.included_order_ref |  | {"field": "included_order_ref", "output": "draft_reply", "value": true} |
| draft_reply_includes_status | output_field_equals | ok | Output field matches: draft_reply.included_status |  | {"field": "included_status", "output": "draft_reply", "value": true} |
| draft_reply_has_no_compensation | output_field_equals | ok | Output field matches: draft_reply.invented_compensation |  | {"field": "invented_compensation", "output": "draft_reply", "value": false} |
| reply_check_ok | output_field_equals | ok | Output field matches: reply_check.ok |  | {"field": "ok", "output": "reply_check", "value": true} |
| reply_check_matches_facts | output_field_equals | ok | Output field matches: reply_check.matches_facts |  | {"field": "matches_facts", "output": "reply_check", "value": true} |
| reply_check_no_unsupported_claims | output_field_equals | ok | Output field matches: reply_check.unsupported_claims |  | {"field": "unsupported_claims", "output": "reply_check", "value": []} |
| reply_validation_exists | output_exists | ok | Output exists: reply_validation |  | {"output": "reply_validation"} |
| customer_reply_pending | pending_action_exists | ok | Pending action exists. |  | {"output": "customer_reply_send", "tool": "wa/send"} |
| no_errors | no_errors | ok | No runtime errors. |  | {} |
| order_ref_has_value | output_has_fields | ok | Output has fields: order_ref |  | {"fields": ["order_ref", "confidence", "reason"], "output": "order_ref"} |
| order_ref_confidence_ok | output_field_in | ok | Output field is allowed: order_ref.confidence |  | {"field": "confidence", "output": "order_ref", "value": "high", "values": ["high", "medium"]} |
| category_is_order_status | output_field_equals | ok | Output field matches: category.label |  | {"field": "label", "output": "category", "value": "order_status"} |
| customer_exists | output_has_fields | ok | Output has fields: customer |  | {"fields": ["customer_id", "name", "preferred_channel"], "output": "customer"} |
| order_exists | output_has_fields | ok | Output has fields: order |  | {"fields": ["order_ref", "customer_id", "status", "created_date", "total_amount"], "output": "order"} |
| shipment_exists | output_has_fields | ok | Output has fields: shipment |  | {"fields": ["order_ref", "shipment_id", "status", "carrier", "tracking_ref", "estimated_delivery"], "output": "shipment"} |
| order_belongs_to_customer | output_field_equals | ok | Output field matches: order.customer_id |  | {"field": "customer_id", "output": "order", "value": "CUST-1001"} |
| shipment_matches_order | output_field_equals | ok | Output field matches: shipment.order_ref |  | {"field": "order_ref", "output": "shipment", "value": "ORD-10042"} |
| status_context_exists | output_exists | ok | Output exists: status_context |  | {"output": "status_context"} |
| draft_reply_includes_order_ref | output_field_equals | ok | Output field matches: draft_reply.included_order_ref |  | {"field": "included_order_ref", "output": "draft_reply", "value": true} |
| draft_reply_includes_status | output_field_equals | ok | Output field matches: draft_reply.included_status |  | {"field": "included_status", "output": "draft_reply", "value": true} |
| draft_reply_has_no_compensation | output_field_equals | ok | Output field matches: draft_reply.invented_compensation |  | {"field": "invented_compensation", "output": "draft_reply", "value": false} |
| reply_check_ok | output_field_equals | ok | Output field matches: reply_check.ok |  | {"field": "ok", "output": "reply_check", "value": true} |
| reply_check_matches_facts | output_field_equals | ok | Output field matches: reply_check.matches_facts |  | {"field": "matches_facts", "output": "reply_check", "value": true} |
| reply_check_no_unsupported_claims | output_field_equals | ok | Output field matches: reply_check.unsupported_claims |  | {"field": "unsupported_claims", "output": "reply_check", "value": []} |
| reply_validation_exists | output_exists | ok | Output exists: reply_validation |  | {"output": "reply_validation"} |
| customer_reply_pending | pending_action_exists | ok | Pending action exists. |  | {"output": "customer_reply_send", "tool": "wa/send"} |

Passed validations: 62
Failed validations: 0
## 11. Approval / Side-Effect Status

Pending Action Count: 1
Executed Action Count: 0
### Pending Action: pa_bff3966ba72043ae931ecd5689f825d9
| Field | Value |
|---|---|
| Tool | wa/send |
| Status | EXECUTED |
| Risk | external_communication |
| Requires Approval | True |
| Output Alias | customer_reply_send |
Human Summary: This action would send a WhatsApp message to "Alex Customer" with message "{'body': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.', 'included_order_ref': True, 'included_status': True, 'invented_compensation': False, 'reply': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.', 'tone': 'professional'}".
Arguments: {"channel": "whatsapp", "chat": "Alex Customer", "customer": {"customer_id": "CUST-1001", "email": "alex@example.test", "name": "Alex", "preferred_channel": "whatsapp", "status": "active", "whatsapp_chat": "Alex Customer"}, "customer_id": "CUST-1001", "draft_po": {}, "message": {"body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.", "included_order_ref": true, "included_status": true, "invented_compensation": false, "reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.", "tone": "professional"}, "reply": "Hi Alex, your order ORD-10042 has shipped and is currently in transit."}
Guardrails: ["Requires explicit approval before execution.", "UI live execution is disabled in this spec.", "Dry-run mode only."]

## 12. Failure Summary

No failure for this run.
## 13. Artifact Index

| Artifact | Path |
|---|---|
| TaskFrame JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\taskframe.json |
| Summary JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\summary.json |
| Outputs JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\outputs.json |
| Audit JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\audit.json |
| Run Report Markdown | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\run_report.md |
| Run Report HTML | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\run_report.html |
| Approval Pack Report Markdown | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\approval_pack_report.md |
| Approval Pack Report HTML | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\approval_pack_report.html |
| Failure Report Markdown | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\failure_report.md |
| Failure Report HTML | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\failure_report.html |
| Evidence Bundle JSON | D:\Projects\4thGenAgent\runtime_data\outputs\runtime\runs\frame_e8375704f06540e18f362a3adc36c2b9\reports\evidence_bundle.json |
## 14. Raw References

- Frame ID: frame_e8375704f06540e18f362a3adc36c2b9
- Manifest ID: customer.status_llm_e2e
- Runtime Data Dir: D:\Projects\4thGenAgent\runtime_data\outputs\runtime
- Generated At: 2026-05-05T07:04:08Z
- Report Version: operator_run_report_v1