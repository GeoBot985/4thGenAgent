# Approval Pack Report

Frame ID: frame_9ce7b21146cf4410ab603cf3fb1411c7
Manifest ID: procurement.low_stock_reorder
State: COMPLETED

## Pending Actions
### Action pa_910f5bcf2e8e42769bcf0e9c95d385c5
Tool: supplier/send_message
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "supplier/send_message" with the listed arguments.
Arguments: {'body': 'Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-204552-8B21CE for SKU-1002. Please confirm availability and lead time.', 'draft_po': {'currency': 'ZAR', 'lines': [{'line_total': 4410.0, 'name': 'Keyboard', 'quantity': 21, 'sku': 'SKU-1002', 'unit_cost': 210.0}], 'po_id': 'PO-DRAFT-20260504-204552-8B21CE', 'status': 'draft', 'supplier_id': 'SUP-1001', 'supplier_name': 'Cape Tech Supplies', 'total': 4410.0}, 'message': {'body': 'Good day Cape Tech Supplies, please find draft purchase order PO-DRAFT-20260504-204552-8B21CE for SKU-1002. Please confirm availability and lead time.', 'included_po_id': True, 'included_sku_lines': True, 'included_supplier_name': True, 'invented_terms': False, 'subject': 'Purchase Order PO-DRAFT-20260504-204552-8B21CE', 'tone': 'professional'}, 'subject': 'Purchase Order PO-DRAFT-20260504-204552-8B21CE', 'supplier': {'email': 'orders@capetech.example', 'lead_time_days': 5, 'name': 'Cape Tech Supplies', 'supplier_id': 'SUP-1001'}, 'to': 'orders@capetech.example'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
