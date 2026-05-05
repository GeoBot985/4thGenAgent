# TaskFrame Run Report

## 1. Executive Summary

| Field | Value |
|---|---|
| Frame ID | frame_a8359d873cfe4e0eac8c7cd6458ba960 |
| Manifest | accounting.payment_reconciliation |
| State | FAILED_VALIDATION |
| Outcome | Run failed safely. No side effect should be executed unless explicitly recorded. |
| Pending Actions | 0 |
| Executed Actions | 0 |
| Errors | 1 |

## 2. Trigger / Event

- Event ID: evt_2b3036eaf31d4ccd8502e823b442978b
- Event Type: manual.accounting_payment_reconciliation
- Source: operator_scenario_pack

```json
{
  "event_id": "evt_2b3036eaf31d4ccd8502e823b442978b",
  "event_type": "manual.accounting_payment_reconciliation",
  "invoices_range": "CustomerInvoices!A:H",
  "ledger_range": "Ledger!A:I",
  "orders_range": "Orders!A:F",
  "payments_range": "Payments!A:I",
  "recon_exceptions_range": "ReconExceptions!A:M",
  "recon_runs_range": "ReconRuns!A:J",
  "source": "operator_scenario_pack",
  "spreadsheet_id": "",
  "tabs": {
    "invoices": "CustomerInvoices!A:H",
    "ledger": "Ledger!A:I",
    "orders": "Orders!A:F",
    "payments": "Payments!A:I",
    "recon_exceptions": "ReconExceptions!A:M",
    "recon_runs": "ReconRuns!A:J"
  }
}
```

## 3. Route and Manifest

- Manifest ID: accounting.payment_reconciliation
- Manifest Name: 
- Step Count: 14
- Validation Count: 0

## 4. Runtime Final State

- Final State: FAILED_VALIDATION
- Current Step ID: 
- Errors Count: 1

```json
null
```

## 5. Step Timeline

| # | Step | Kind | Action | Status | Attempts | Result | Error |
|---:|---|---|---|---|---:|---|---|
| 1 | read_payments_sheet | tool | read_range | FAILED <<< FAILURE | 1 | payments_sheet | SPREADSHEET_ID_REQUIRED |
| 2 | read_orders_sheet | tool | read_range | PENDING | 0 | orders_sheet |  |
| 3 | read_invoices_sheet | tool | read_range | PENDING | 0 | invoices_sheet |  |
| 4 | read_ledger_sheet | tool | read_range | PENDING | 0 | ledger_sheet |  |
| 5 | load_payments | tool | load_payments | PENDING | 0 | payments |  |
| 6 | load_orders | tool | load_orders | PENDING | 0 | accounting_orders |  |
| 7 | load_invoices | tool | load_invoices | PENDING | 0 | invoices |  |
| 8 | load_ledger | tool | load_ledger | PENDING | 0 | ledger_entries |  |
| 9 | match_payments | tool | match_payments | PENDING | 0 | reconciliation_result |  |
| 10 | validate_reconciliation | tool | validate_result | PENDING | 0 | reconciliation_validation |  |
| 11 | draft_exception_summary | llm | draft_reconciliation_exception_summary | PENDING | 0 | exception_summary |  |
| 12 | build_recon_sheet_rows | tool | build_recon_sheet_rows | PENDING | 0 | recon_sheet_rows |  |
| 13 | stage_recon_run_write | tool | prepare_write_rows | PENDING | 0 | recon_run_write |  |
| 14 | stage_recon_exception_write | tool | prepare_write_rows | PENDING | 0 | recon_exception_write |  |

## 6. LLM Calls

No LLM calls were recorded.
## 7. Tool Calls

- step_id: read_payments_sheet
  tool: sheet/read_range
  namespace: sheet
  action: read_range
  live: False
  dry_run: True
  side_effect: False
  requires_approval: False
  output_alias: payments_sheet
  ok: False
  error: SPREADSHEET_ID_REQUIRED
## 8. Outputs

No outputs were recorded.
## 9. Evidence

No evidence records were attached to this TaskFrame.
## 10. Validations

No validations were recorded.
## 11. Approval / Side-Effect Status

No side-effect actions were staged or executed.
## 12. Failure Summary

- State: FAILED_VALIDATION
- failed_step_id: read_payments_sheet
- Failed Step: read_payments_sheet
- failure_type: validation_failed
- Failure Type: validation_failed
- failure_message: SPREADSHEET_ID_REQUIRED
- Failure Message: SPREADSHEET_ID_REQUIRED
- Operator Explanation: The runtime blocked the reply because spreadsheet_id_required
- Pending Actions: 0
- Executed Actions: 0
- Safe To Retry: False

### Failed Validations
- : SPREADSHEET_ID_REQUIRED

### Runtime Errors
- {'data': {'error_type': 'ToolFunctionError', 'function': 'sheet_read_range', 'step_id': 'read_payments_sheet', 'tag': 'transient', 'tool': 'sheet/read_range'}, 'message': 'SPREADSHEET_ID_REQUIRED', 'timestamp': '2026-05-04T20:28:35Z', 'type': 'live_tool_execution_failed'}
## 13. Artifact Index

| Artifact | Path |
|---|---|
| TaskFrame JSON | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\taskframe.json |
| Summary JSON | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\summary.json |
| Outputs JSON | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\outputs.json |
| Audit JSON | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\audit.json |
| Run Report Markdown | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\run_report.md |
| Run Report HTML | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\run_report.html |
| Approval Pack Report Markdown | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\approval_pack_report.md |
| Approval Pack Report HTML | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\approval_pack_report.html |
| Failure Report Markdown | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\failure_report.md |
| Failure Report HTML | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\failure_report.html |
| Evidence Bundle JSON | runtime_data\outputs\runtime\runs\frame_a8359d873cfe4e0eac8c7cd6458ba960\reports\evidence_bundle.json |
## 14. Raw References

- Frame ID: frame_a8359d873cfe4e0eac8c7cd6458ba960
- Manifest ID: accounting.payment_reconciliation
- Runtime Data Dir: runtime_data\outputs\runtime
- Generated At: 2026-05-04T20:28:35Z
- Report Version: operator_run_report_v1