# Manifest Building Manual

## 1. Plain-English Overview

A manifest is the instruction file for an autonomous business worker. It tells the runtime what task is allowed, which inputs are required, which steps must run, which tools or LLM micro-actions may be used, what validations must pass, and when the worker must stop for approval. The manifest is not free-form prompting: it is a controlled workflow contract that the runtime executes step by step and records in a TaskFrame.

In simple terms: the manifest is the worker's SOP.

## 2. Manifest Anatomy

Canonical shape:

```json
{
  "manifest_id": "customer.message_status_check",
  "name": "Customer Message Status Check",
  "version": 1,
  "trigger": {
    "type": "manual"
  },
  "inputs": [
    {
      "name": "message",
      "required": true
    },
    {
      "name": "customer_id",
      "required": true
    }
  ],
  "steps": [
    {
      "id": "extract_order_ref",
      "command": "[q:extract_order_ref -> order_ref] text=$inputs.message"
    }
  ],
  "validations": [],
  "completion": {
    "success_outputs": ["order_ref"]
  }
}
```

Field purpose:

| Field | Purpose |
| --- | --- |
| `manifest_id` | Unique ID used by the catalog and runtime |
| `name` | Human-readable name |
| `version` | Integer manifest version |
| `trigger` | Manual, event, or scheduled trigger metadata |
| `inputs` | Required runtime inputs |
| `steps` | Ordered commands the worker may execute |
| `validations` | Rules used to prove the outcome is acceptable |
| `completion` | Required outputs or pending actions for success |

## 3. Command Reference

See also: [manifest_command_reference.md](manifest_command_reference.md)

Command types:

- `[q:action -> output]` LLM / semantic micro-action
- `[t:namespace/action -> output]` Deterministic tool action
- `[validate:rule_id]` Run named validation rule
- `[maintenance:action -> output]` Maintenance/report/artifact command

Examples:

```text
[q:extract_order_ref -> order_ref] text=$inputs.message
[q:classify_customer_message -> category] text=$inputs.message
[q:draft_customer_status_reply -> draft_reply] context=$outputs.order_context
[t:customer/read -> customer] customer_id=$inputs.customer_id
[t:order/read -> order] order_ref=$outputs.order_ref.order_ref
[t:shipment/read -> shipment] order_ref=$outputs.order_ref.order_ref
[t:sheet/read_range -> payments_sheet] spreadsheet_id=$inputs.spreadsheet_id range_name=$inputs.payments_range
[validate:customer_owns_order]
[validate:reply_matches_facts]
```

Variable references:

- `$inputs.message`
- `$inputs.customer_id`
- `$outputs.order_ref`
- `$outputs.order_ref.order_ref`
- `$outputs.customer.customer_id`
- `$outputs.order.status`

Rule:

Every step that produces data should write it to an output alias using `-> output_name`.

## 4. Common Workflow Patterns

Read-only workflow

1. Accept inputs
2. Read records
3. Validate facts
4. Produce final output
5. Complete

Approval-gated workflow

1. Accept inputs
2. Read records
3. Build draft action
4. Validate action
5. Stage pending action
6. Stop for approval

Report workflow

1. Read source data
2. Build report model
3. Generate report artifact
4. Generate evidence bundle
5. Complete

Failed validation workflow

1. Input or lookup fails
2. Validation fails
3. Runtime stops
4. No side effect is created
5. Run report explains safe stop

## 5. Validation and Completion Rules

Validations are the difference between a useful autonomous worker and an unsafe chatbot. The LLM may extract or draft, but validation decides whether the result is acceptable.

Validation examples:

```json
{
  "id": "customer_exists",
  "type": "output_field_truthy",
  "output": "customer",
  "field": "customer_id",
  "message": "Customer record must exist."
}
```

```json
{
  "id": "reply_exists",
  "type": "output_exists",
  "output": "draft_reply",
  "message": "Draft reply must be created."
}
```

Completion example:

```json
{
  "success_outputs": ["draft_reply"],
  "success_pending_actions": ["send_customer_message"],
  "allow_pending_approval": true,
  "continue_after_pending": true
}
```

## 6. Side-Effect and Approval Rules

Side-effect classes:

| Type | Examples | Approval |
| --- | --- | --- |
| Read-only | search, read, classify, summarize | No approval |
| Prepare/stage | draft, prepare message, build PO | Usually no live side effect |
| Side effect | send, write, update, delete, submit | Approval required |

Rule:

A manifest must not silently execute side effects. Side-effect steps must create pending actions and stop for approval unless explicitly allowed by live execution policy.

Live execution policy example:

```json
{
  "live_execution": {
    "enabled": false,
    "allowed_tools": [],
    "requires_approval": true
  }
}
```

## 7. How to Test a Manifest in the Workbench

1. Open Manifest Workbench
2. Select a manifest
3. Click Validate manifest
4. Fill generated input fields or paste Raw JSON input override
5. Keep fixture mode enabled for external read tools unless testing live credentials
6. Click Run dry-run test
7. Inspect the Dry-run Execution Panel
8. Select each step in the Step List Panel
9. Review Step result inspector
10. Click Create/open run report

Expected states:

| State | Meaning |
| --- | --- |
| `COMPLETED` | Workflow finished successfully |
| `WAITING_FOR_EXECUTE` | Pending action created and approval required |
| `FAILED_VALIDATION` | Business rule or fixture validation stopped the workflow |
| `FAILED_EXECUTION` | Tool/runtime error stopped execution |

## 8. Worked Examples

Example A - LLM classify message

```json
{
  "manifest_id": "llm.classify_customer_message",
  "name": "LLM Classify Customer Message",
  "version": 1,
  "trigger": {"type": "manual"},
  "inputs": [{"name": "message", "required": true}],
  "steps": [
    {
      "id": "classify_message",
      "command": "[q:classify_customer_message -> category] text=$inputs.message"
    }
  ],
  "validations": [
    {
      "id": "category_exists",
      "type": "output_exists",
      "output": "category",
      "message": "Classification output must exist."
    }
  ],
  "completion": {
    "success_outputs": ["category"]
  }
}
```

Example B - Customer order status

Abbreviated flow:

`extract order ref -> classify -> read customer -> read order -> read shipment -> build context -> draft reply -> validate -> stage message`

Example C - Accounting reconciliation

Abbreviated flow:

`read payment sheet -> read orders sheet -> load records -> reconcile -> prepare recon writes -> stop for approval`

## 9. Frontier LLM Authoring Guide

See also: [manifest_llm_authoring_guide.md](manifest_llm_authoring_guide.md)

When generating a manifest:

1. Do not invent tools.
2. Use only commands listed in the command reference or existing tool registry.
3. Every required input must appear in `inputs`.
4. Every produced value must have an output alias.
5. Later steps must reference prior outputs through `$outputs`.
6. Add validations for required business facts.
7. Add completion rules that match the intended final state.
8. Side effects must be staged and approval-gated.
9. Failed validation must stop safely.
10. Do not rely on chat history. The TaskFrame outputs are the data pipe.

Required output format for LLM-generated manifest:

1. Manifest JSON
2. Test input JSON
3. Expected outcome summary
4. Workbench test checklist

LLM build procedure:

1. Identify task type
2. Identify trigger
3. Define required inputs
4. Select allowed tools or LLM micro-actions
5. Build step sequence
6. Add validations
7. Add completion rules
8. Check side-effect policy
9. Produce test input JSON
10. Predict expected Workbench result

LLM self-check checklist:

- Is every command valid?
- Does every output alias exist before it is referenced?
- Are required inputs complete?
- Does every side effect require approval?
- Can failed lookup or validation stop safely?
- Does completion require the right output or pending action?
- Can this run in dry-run mode?
- Is the manifest specific enough for the runtime and not relying on model judgment?

## 10. Pre-Commit Checklist

Before committing a manifest:

- [ ] Manifest validates in Workbench
- [ ] Required input fields render correctly
- [ ] Dry-run test completes or fails for the expected reason
- [ ] Step outputs are visible
- [ ] Failed paths stop safely
- [ ] Pending actions are approval-gated
- [ ] Run report opens and explains step outcomes
- [ ] No live external dependency is required for default tests
- [ ] No unsupported tool or command is invented

## 11. Saving New Manifests

1. Click New manifest.
2. Edit manifest JSON.
3. Validate manifest.
4. Add test inputs.
5. Run dry-run test.
6. Fix errors.
7. Save manifest.
8. Reload catalog.
9. Re-run from saved manifest.

Warning: Do not save manifests that require live external credentials for default portfolio tests unless fixture mode is available.
