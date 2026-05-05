# Runtime Contracts

This document freezes the core runtime shapes that future specs must respect.

## TaskFrame Contract

The canonical TaskFrame is the runtime case file for a single execution. It carries the trigger, parsed inputs, step execution state, outputs, evidence, pending actions, executed actions, validation records, errors, tool calls, LLM calls, audit events, and completion outcome.

### Required Fields

| Field | Purpose | Required | Notes |
|---|---|---|---|
| `frame_id` | Unique runtime task identifier | Yes | Used for reload, approval, and audit |
| `manifest_id` | Selected manifest | Yes | Must not change during a run |
| `state` | Current lifecycle state | Yes | Must be one of the approved runtime states |
| `outputs` | Runtime output pipe | Yes | Later steps read from here |
| `pending_actions` | Staged side effects | Yes | Must require approval |
| `executed_actions` | Approved executed side effects | Yes | Dry-run or live execution record |
| `audit` | Ordered event trail | Yes | Must record significant transitions |

### Canonical Structure

```json
{
  "frame_id": "",
  "manifest_id": "",
  "state": "",
  "trigger": {},
  "raw_input": "",
  "inputs": {},
  "steps": [],
  "current_step_id": "",
  "step_results": [],
  "outputs": {},
  "evidence": [],
  "pending_actions": [],
  "executed_actions": [],
  "validations": [],
  "errors": [],
  "tool_calls": [],
  "llm_calls": [],
  "audit": [],
  "completion_gate_result": {},
  "final_response": ""
}
```

The repo stores step runtime data in `steps`, outputs in `outputs`, evidence in `evidence`, and terminal runtime data in `completion_gate_result` and `final_response`.
Any `step_results` wording in reports should be treated as a derived view over the persisted step runtime data.

### Approved Lifecycle States

`CREATED`, `VALIDATING`, `READY`, `RUNNING`, `WAITING_FOR_INPUT`, `WAITING_FOR_EXECUTE`, `EXECUTING_PENDING`, `VERIFYING`, `COMPLETED`, `COMPLETED_NO_DATA`, `FAILED_VALIDATION`, `FAILED_EXECUTION`, `FAILED_COMPLETION`, `CANCELLED`, `EXPIRED`

## Manifest Contract

A manifest is the instruction plus validation contract for a workflow. No manifest means no execution.

### Required Fields

`manifest_id`, `name`, `version`, `trigger`, `inputs`, `steps`, `validations`, `completion`, `live_execution`

### Step Shape

Each manifest step uses:

`id`, `command`, `when`, `retry`, `timeout_seconds`

### Completion Shape

```json
{
  "success_outputs": ["draft_reply"],
  "success_pending_actions": ["sent_reply"],
  "allow_pending_approval": true,
  "acceptable_empty_outputs": ["unread_mail"]
}
```

The orchestrator executes the manifest; it does not invent new business logic.

## Event Route Contract

Event routes bind an explicit event to a manifest. Events do not execute directly.

### Required Fields

`route_id`, `source`, `event_type`, `manifest_id`, `input_map`, `enabled`

### Rule

Events resolve to manifests. Manifests create TaskFrames. TaskFrames drive execution.

## ToolResult Contract

Tools return structured results. The orchestrator records tool calls, and the LLM does not execute tools directly.

### Standard Shape

`ok`, `type`, `data`, `evidence`, `error`, `metadata`, `raw`

The result must be machine-readable and audit-friendly. The runtime stores tool call records separately from tool outputs.

## Tool Contract

Tools are deterministic capability adapters.

A tool must be registered, health-checkable, and callable only through manifest-defined steps. Tool calls are recorded in `TaskFrame.tool_calls`.

Side-effect tools must stage `PendingAction` records before execution. Live side effects require approval, manifest allowlist, tool allowlist, runtime live mode, and guardrail success.

See [Adding New Tools](adding_new_tools.md) for the onboarding flow and [Tool Contract Checklist](tool_contract_checklist.md) for the copy/paste checklist used in future specs.

## PendingAction Contract

Pending actions stage side effects before execution.

### Standard Shape

`action_id`, `step_id`, `tool`, `namespace`, `action`, `action_type`, `output_alias`, `args`, `body`, `status`, `side_effect`, `requires_approval`, `created_at`, `approved_by`, `approved_at`, `approval_reason`, `rejected_by`, `rejected_at`, `rejection_reason`, `executed_at`, `dry_run`, `live`, `live_side_effect`, `guardrail`, `result_type`, `last_error`

### Approved Statuses

`PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTING`, `EXECUTED`, `FAILED`

Side effects must be staged before execution. Approval changes PendingAction status. Execution changes PendingAction status and writes `executed_actions`.

## LLM Call Contract

The LLM is a bounded helper, not a controller.

### Allowed Roles

`extract`, `classify`, `summarise`, `draft`, `compare`, `explain exception`

### Forbidden Roles

`choose arbitrary tools`, `invent workflow`, `self-certify completion`, `execute side effects`, `override manifest scope`, `silently change task scope`

### Record Shape

The repo records LLM calls with fields such as `step_id`, `action`, `prompt`, `system`, `raw_output`, `parsed_output`, `ok`, `error`, `provider`, `model`, and `timestamp`. In spec language these correspond to the raw and parsed response fields. Some adapters also include `error_type`, `args`, `result_type`, and `output_alias`.

## Live Execution Policy Contract

Live execution requires all of the following:

- `runtime_live_mode` must be true
- `ToolRunner` must not be in dry-run mode
- the TaskFrame must be in an executable approval state
- the PendingAction must be `APPROVED`
- the manifest must allow the tool
- the tool registry must allow live side effects
- the guardrail must pass
- the audit trail must record policy and guardrail checks

Default RC must not execute live side effects.
