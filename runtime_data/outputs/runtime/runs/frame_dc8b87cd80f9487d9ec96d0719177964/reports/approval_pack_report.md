# Approval Pack Report

Frame ID: frame_dc8b87cd80f9487d9ec96d0719177964
Manifest ID: customer.status_llm_e2e
State: COMPLETED

## Pending Actions
### Action pa_ee2a6cb88b2040758b2126687b7ddc0e
Tool: wa/send
Status: EXECUTED
Risk: external_communication
Human Summary: This action would send a WhatsApp message to "Alex Customer" with message "{'body': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.', 'included_order_ref': True, 'included_status': True, 'invented_compensation': False, 'reply': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.', 'tone': 'professional'}".
Arguments: {'channel': 'whatsapp', 'chat': 'Alex Customer', 'customer': {'customer_id': 'CUST-1001', 'email': 'alex@example.test', 'name': 'Alex', 'preferred_channel': 'whatsapp', 'status': 'active', 'whatsapp_chat': 'Alex Customer'}, 'customer_id': 'CUST-1001', 'draft_po': {}, 'message': {'body': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.', 'included_order_ref': True, 'included_status': True, 'invented_compensation': False, 'reply': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.', 'tone': 'professional'}, 'reply': 'Hi Alex, your order ORD-10042 has shipped and is currently in transit.'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
