# Approval Pack Report

Frame ID: frame_1a5c52137f474a719f24e40641d7cde0
Manifest ID: procurement.low_stock_reorder
State: COMPLETED

## Pending Actions
### Action pa_7c0ae39217254f54939d3837b63e1d30
Tool: supplier/send_message
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "supplier/send_message" with the listed arguments.
Arguments: {'body': 'Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260505-071509-34E1AB for SKU-1002. Please confirm availability and lead time.', 'draft_po': {'currency': 'ZAR', 'lines': [{'line_total': 4410.0, 'name': 'Keyboard', 'quantity': 21, 'sku': 'SKU-1002', 'unit_cost': 210.0}], 'po_id': 'PO-DRAFT-20260505-071509-34E1AB', 'status': 'draft', 'supplier_id': 'SUP-1001', 'supplier_name': 'Cape Tech Supplies', 'total': 4410.0}, 'message': {'body': 'Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260505-071509-34E1AB for SKU-1002. Please confirm availability and lead time.', 'included_po_id': True, 'included_sku_lines': True, 'included_supplier_name': True, 'invented_terms': False, 'subject': 'Purchase Order PO-DRAFT-20260505-071509-34E1AB', 'tone': 'professional'}, 'subject': 'Purchase Order PO-DRAFT-20260505-071509-34E1AB', 'supplier': {'email': 'orders@capetech.example', 'lead_time_days': 5, 'name': 'Cape Tech Supplies', 'supplier_id': 'SUP-1001'}, 'to': 'orders@capetech.example'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
