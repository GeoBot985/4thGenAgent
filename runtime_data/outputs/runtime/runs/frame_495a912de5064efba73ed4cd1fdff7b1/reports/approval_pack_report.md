# Approval Pack Report

Frame ID: frame_495a912de5064efba73ed4cd1fdff7b1
Manifest ID: accounting.payment_reconciliation
State: COMPLETED

## Pending Actions
### Action pa_c23188bc686e4862912b5424919fc759
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconRuns!A:J', 'rows': [['RECON-20260504-201743', '', 1, 1, 4, 2, 1, 1, 'exceptions', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']

### Action pa_6c3cf90bf5554dcb894a3f98c5125ad0
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconExceptions!A:M', 'rows': [['RECON-20260504-201743', 'EXC-678D93F1', 'already_posted', 'EFT-9001', 'PAY-1001', 'ORD-10042', '', 0.0, 0.0, 'ZAR', 'medium', 'Payment already posted to ledger.', ''], ['RECON-20260504-201743', 'EXC-68439257', 'amount_mismatch', 'EFT-9002', 'PAY-1002', 'ORD-10043', '', 500.0, 450.0, 'ZAR', 'high', 'Payment amount does not match invoice.', ''], ['RECON-20260504-201743', 'EXC-E24C57C3', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1004', 'ORD-10045', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', ''], ['RECON-20260504-201743', 'EXC-154FC6AC', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1005', 'ORD-10046', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
