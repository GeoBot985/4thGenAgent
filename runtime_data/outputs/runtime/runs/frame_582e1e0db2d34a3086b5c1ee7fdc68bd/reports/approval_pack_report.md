# Approval Pack Report

Frame ID: frame_582e1e0db2d34a3086b5c1ee7fdc68bd
Manifest ID: accounting.payment_reconciliation
State: COMPLETED

## Pending Actions
### Action pa_3419ec3fb9b8445cbb03b3713cb7c5c0
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconRuns!A:J', 'rows': [['RECON-20260505-071102', '', 1, 1, 4, 2, 1, 1, 'exceptions', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']

### Action pa_10085bde7d13488cac6e5db565411ba8
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconExceptions!A:M', 'rows': [['RECON-20260505-071102', 'EXC-BCE2ABD8', 'already_posted', 'EFT-9001', 'PAY-1001', 'ORD-10042', '', 0.0, 0.0, 'ZAR', 'medium', 'Payment already posted to ledger.', ''], ['RECON-20260505-071102', 'EXC-A4A0883A', 'amount_mismatch', 'EFT-9002', 'PAY-1002', 'ORD-10043', '', 500.0, 450.0, 'ZAR', 'high', 'Payment amount does not match invoice.', ''], ['RECON-20260505-071102', 'EXC-17A9F5E9', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1004', 'ORD-10045', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', ''], ['RECON-20260505-071102', 'EXC-772243B3', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1005', 'ORD-10046', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
