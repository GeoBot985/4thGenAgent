# Approval Pack Report

Frame ID: frame_89e455721b314b679a9697a7ca12f9d2
Manifest ID: accounting.payment_reconciliation
State: COMPLETED

## Pending Actions
### Action pa_e343a9569df94bb587f60c27d0fa97ba
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconRuns!A:J', 'rows': [['RECON-20260505-070914', '', 1, 1, 4, 2, 1, 1, 'exceptions', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']

### Action pa_c186656e6f0a45838667b24685983ce4
Tool: sheet/write_rows
Status: EXECUTED
Risk: side_effect_unknown
Human Summary: This action would execute tool "sheet/write_rows" with the listed arguments.
Arguments: {'dry_run': True, 'mode': 'append', 'range_name': 'ReconExceptions!A:M', 'rows': [['RECON-20260505-070914', 'EXC-26A5AD95', 'already_posted', 'EFT-9001', 'PAY-1001', 'ORD-10042', '', 0.0, 0.0, 'ZAR', 'medium', 'Payment already posted to ledger.', ''], ['RECON-20260505-070914', 'EXC-F550BA48', 'amount_mismatch', 'EFT-9002', 'PAY-1002', 'ORD-10043', '', 500.0, 450.0, 'ZAR', 'high', 'Payment amount does not match invoice.', ''], ['RECON-20260505-070914', 'EXC-AE7250DD', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1004', 'ORD-10045', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', ''], ['RECON-20260505-070914', 'EXC-6F86EBBE', 'duplicate_payment_ref', 'EFT-9005', 'PAY-1005', 'ORD-10046', '', 0.0, 0.0, 'ZAR', 'high', 'Duplicate payment reference.', '']], 'spreadsheet_id': 'demo-sheet-local'}
Guardrails: ['Requires explicit approval before execution.', 'UI live execution is disabled in this spec.', 'Dry-run mode only.']
