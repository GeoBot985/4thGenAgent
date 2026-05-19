# Cross-Workflow Business Automation Demo v2

## What the Demo Shows

This demo presents one controlled business incident flowing across customer support, procurement, and accounting through the same TaskFrame runtime.

## Business Story

The story is an order fulfilment exception. A customer asks about an order, the runtime prepares a response, the operational context moves into procurement and stock handling, and accounting validates the financial side. The story uses seeded data and deterministic workflow steps.

## Runtime Controls

- Manifest-driven execution
- Bounded LLM assistance
- Deterministic validation
- Approval-gated side effects
- Dry-run execution only
- TaskFrame traceability

## What the LLM Does

The LLM is limited to bounded drafting and narrative assistance. It may help with human-readable summaries, but it does not decide workflow outcomes.

## What the LLM Does Not Do

The LLM does not authorize actions, mutate data, perform live writes, or override validation.

## Approval and Dry-Run Safety

All side effects remain approval-gated. Any executed actions in the demo run in dry-run mode only. No live side effects are performed.

## Evidence Pack Contents

The consolidated story pack includes:

- index.md
- index.html
- summary.json
- evidence_manifest.json
- workflow_timeline.json
- screenshots_checklist.md

## How to Run

Use the operator UI or run:

```bash
python -m src.taskframe_cli demo cross-workflow-v2
```

## Known Limitations

This is not production live automation. It is a controlled portfolio demo using seeded data, approval-staged side effects, and dry-run execution only.
