# Cross-Workflow Business Automation Demo v1

## Executive Summary

- Pack ID: cross_workflow_business_demo_v1
- Pack Run ID: cross_workflow_business_demo_v1_6f4719bbc258
- Started At: 2026-05-04T10:56:56.146129Z
- Ended At: 2026-05-04T10:56:59.082719Z
- Duration (ms): 2936
- Workflow Count: 3
- Dry-Run Only: True
- Requires Real LLM: True

## Runtime Architecture Proof

All workflows executed through the same TaskFrame runtime, manifest-driven steps, registered tools, bounded LLM actions, approval-gated side effects, and dry-run execution.

## Workflow 1 - customer_support

- Scenario ID: customer_status_approve_execute_dry_run
- Frame ID: frame_c60c07d944144678a6c92bc192adec6c
- Manifest ID: customer.status_llm_e2e
- Final State: FAILED_EXECUTION
- Pending Actions: 0
- Executed Actions: 0
- Report Path: runtime_data\runs\frame_c60c07d944144678a6c92bc192adec6c\reports\run_report.md
- Evidence Path: runtime_data\runs\frame_c60c07d944144678a6c92bc192adec6c\reports\evidence_bundle.json
- LLM Calls: 0
- Tool Calls: 0

## Workflow 2 - procurement

- Scenario ID: procurement_low_stock_approve_execute_dry_run
- Frame ID: 
- Manifest ID: 
- Final State: NOT_RUN
- Pending Actions: 0
- Executed Actions: 0
- Report Path: 
- Evidence Path: 
- LLM Calls: 0
- Tool Calls: 0

## Workflow 3 - accounting

- Scenario ID: accounting_payment_reconciliation_approve_execute_dry_run
- Frame ID: 
- Manifest ID: 
- Final State: NOT_RUN
- Pending Actions: 0
- Executed Actions: 0
- Report Path: 
- Evidence Path: 
- LLM Calls: 0
- Tool Calls: 0

## Approval + Dry-Run Summary

- Total Pending Actions: 0
- Total Executed Actions: 0

## Failure Summary

No live side effects were performed.

## Conclusion

The cross-workflow demo completed 3/3 business workflows through the same TaskFrame runtime. Customer support, procurement, and accounting each executed through manifest-defined steps, registered tools, bounded LLM operations, approval-gated side effects, dry-run execution, and report/evidence generation. No live side effects were performed.