# Approval Pack Report

Frame ID: frame_31dd88cfabd14152a0661a64d184afff
Manifest ID: accounting.payment_reconciliation
State: COMPLETED

## Pending Actions
### Action pa_4176116df71e4ea38fab41d82c78ea49
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconRuns!A:J', 'rows': [['RECON-20260504-200156', '', 1, 1, 4, 2, 1, 1, 'exceptions', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']

### Action pa_afe9b97571884d22995a6bebbe319ab5
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconExceptions!A:M', 'rows': [['RECON-20260504-200156', 'EXC-7064AF1B', 'already_posted', 'EFT-9001', 'PAY-1001', 'ORD-10042', '', 0.0, 0.0, 'ZAR', 'medium', 'Payment already posted to ledger.', ''], ['RECON-20260504-200156', 'EXC-5B76C3AC', 'amount_mismatch', 'EFT-9002', 'PAY-1002', 'ORD-10043', '', 500.0, 450.0, 'ZAR', 'high', 'Payment amount does not match invoice.', ''], ['RECON-20260504-200156', 'EXC-32D5FB9C', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1004', 'ORD-10045', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', ''], ['RECON-20260504-200156', 'EXC-9F155204', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1005', 'ORD-10046', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
