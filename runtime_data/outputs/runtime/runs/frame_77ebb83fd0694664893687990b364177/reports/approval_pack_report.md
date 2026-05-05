# Approval Pack Report

Frame ID: frame_77ebb83fd0694664893687990b364177
Manifest ID: accounting.payment_reconciliation
State: COMPLETED

## Pending Actions
### Action pa_85a84a36f1944327bca0ad58abae1c8f
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconRuns!A:J', 'rows': [['RECON-20260505-065425', '', 1, 1, 4, 2, 1, 1, 'exceptions', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']

### Action pa_b7ac5d2226014183babff4f4e4c054ce
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconExceptions!A:M', 'rows': [['RECON-20260505-065425', 'EXC-3DB56F93', 'already_posted', 'EFT-9001', 'PAY-1001', 'ORD-10042', '', 0.0, 0.0, 'ZAR', 'medium', 'Payment already posted to ledger.', ''], ['RECON-20260505-065425', 'EXC-3E66DFF7', 'amount_mismatch', 'EFT-9002', 'PAY-1002', 'ORD-10043', '', 500.0, 450.0, 'ZAR', 'high', 'Payment amount does not match invoice.', ''], ['RECON-20260505-065425', 'EXC-3DD21515', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1004', 'ORD-10045', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', ''], ['RECON-20260505-065425', 'EXC-9CCC4A13', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1005', 'ORD-10046', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
