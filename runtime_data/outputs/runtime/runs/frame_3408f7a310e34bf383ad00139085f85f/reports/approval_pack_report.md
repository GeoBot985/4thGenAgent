# Approval Pack Report

Frame ID: frame_3408f7a310e34bf383ad00139085f85f
Manifest ID: procurement.low_stock_reorder
State: COMPLETED

## Pending Actions
### Action pa_fec326c6ba2e4568a72a2146e851fea8
Tool: supplier/send_message
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "supplier/send_message" with the listed arguments.
Arguments: {'body': 'Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260505-071102-0E110B for SKU-1002. Please confirm availability and lead time.', 'draft_po': {'currency': 'ZAR', 'lines': [{'line_total': 4410.0, 'name': 'Keyboard', 'quantity': 21, 'sku': 'SKU-1002', 'unit_cost': 210.0}], 'po_id': 'PO-DRAFT-20260505-071102-0E110B', 'status': 'draft', 'supplier_id': 'SUP-1001', 'supplier_name': 'Cape Tech Supplies', 'total': 4410.0}, 'message': {'body': 'Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260505-071102-0E110B for SKU-1002. Please confirm availability and lead time.', 'included_po_id': True, 'included_sku_lines': True, 'included_supplier_name': True, 'invented_terms': False, 'subject': 'Purchase Order PO-DRAFT-20260505-071102-0E110B', 'tone': 'professional'}, 'subject': 'Purchase Order PO-DRAFT-20260505-071102-0E110B', 'supplier': {'email': 'orders@capetech.example', 'lead_time_days': 5, 'name': 'Cape Tech Supplies', 'supplier_id': 'SUP-1001'}, 'to': 'orders@capetech.example'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
