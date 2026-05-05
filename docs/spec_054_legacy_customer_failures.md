# Spec 054 Legacy Customer Failures

## Event Workflow Demo Pack

- `tests/test_event_workflow_demo_pack.py::EventWorkflowDemoPackTests::test_demo_does_not_execute_pending_action`
  - Reason: legacy demo runner hit an outdated customer path without test-only LLM injection.
  - Legacy path used: `src/operator_demo_runner.py` selection `customer_message_status_check`.
  - Replacement/current path: tool-driven customer workflow with pytest-gated fake LLM adapter.
  - Decision: migrate.

- `tests/test_event_workflow_demo_pack.py::EventWorkflowDemoPackTests::test_demo_runner_completes_successfully`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py` selection `customer_message_status_check`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_event_workflow_demo_pack.py::EventWorkflowDemoPackTests::test_taskframe_state_and_pending_action_remain`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py` selection `customer_message_status_check`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

## LLM Manifest Execution

- `tests/test_llm_manifest_execution.py::LLMManifestExecutionTests::test_llm_customer_status_reply_manifest_completes_with_fake_adapter`
  - Reason: `llm.customer_status_reply` still referenced an obsolete `customer/order_context` argument shape.
  - Legacy path used: `manifests/llm_customer_status_reply.manifest.json`.
  - Replacement/current path: tool-driven customer lookups plus current order context build.
  - Decision: migrate.

## Customer Workflow Demo

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_missing_order_id_fails_validation`
  - Reason: legacy customer workflow resolved through outdated manifest shape.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest with deterministic order ref extraction.
  - Decision: migrate.

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_unknown_order_fails_validation`
  - Reason: same legacy path.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest.
  - Decision: migrate.

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_workflow_creates_draft_and_pending_action`
  - Reason: same legacy path.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest.
  - Decision: migrate.

- `tests/test_customer_message_workflow.py::CustomerMessageWorkflowTests::test_wrong_customer_fails_validation`
  - Reason: same legacy path.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest.
  - Decision: migrate.

## Negative Customer Scenarios

- `tests/test_negative_customer_status_scenarios.py::NegativeCustomerStatusScenarioTests::test_unsupported_intent_fails_before_order_status_reply`
  - Reason: legacy negative customer flow still used old demo/manifest shape.
  - Legacy path used: `customer.message_status_check`.
  - Replacement/current path: current tool-driven manifest with validation-based failure.
  - Decision: migrate.

## Operator Demo Execution

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_demo_run_reaches_pending_approval`
  - Reason: demo runner was not aligned with the current customer workflow path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_demo_runner_executes_customer_status_demo_dry_run`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_snapshot_after_demo_run_preserves_pending_action_state`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

- `tests/test_operator_demo_execution.py::OperatorDemoExecutionTests::test_staged_whatsapp_demo_returns_pending_action_pack`
  - Reason: same legacy demo path.
  - Legacy path used: `src/operator_demo_runner.py`.
  - Replacement/current path: current tool-driven customer manifest.
  - Decision: migrate.

