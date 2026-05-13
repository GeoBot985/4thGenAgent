# Demo Script

## Opening

This is TaskFrame Runtime, a manifest-driven autonomous business worker runtime for controlled AI-assisted company operations.

It is not a chatbot controlling tools freely. The workflow is selected through a manifest. Each step writes to a TaskFrame, validations decide whether the worker may continue, and side effects are staged for approval instead of being sent automatically.

## Architecture Explanation

- The manifest defines the allowed workflow path.
- The TaskFrame is the runtime case file and audit source of truth.
- Tools are deterministic adapters, not open-ended agents.
- The LLM handles bounded subtasks such as extraction and drafting.
- Approvals gate side effects before anything can execute.
- Validation determines completion, not model confidence.

## Happy-Path Customer Demo

I will start with the customer status workflow.

I select `Customer Status - Happy Path`, run the demo, and show the Demo View.

The important points are:

- the customer request is visible in plain English
- the worker checklist explains what was checked
- the prepared reply is visible
- the approval decision is explicit
- the run report can be opened from the same screen

The message is drafted, but it is not sent automatically. The runtime waits at the approval gate.

## Failed-Validation Demo

Next I switch to `Customer Status - Missing Customer`.

This shows the safety behavior:

- the worker stops safely
- no customer message is prepared
- no live send occurs
- the report explains why the workflow stopped

That is the control boundary: the runtime does not invent success when validation fails.

## Report / Evidence Demo

Then I move to `Report Generation - Happy Path`.

This demonstrates the reporting layer:

- the business report path is visible
- the run report path is visible
- the report artifact can be opened directly
- the run report shows step outcomes, validations, evidence, and pending actions

This is the clearest example of the product boundary: the runtime produces a business artifact and a run-bound audit artifact for the exact frame.

## Safety Model

- The runtime executes only manifest-defined work.
- The LLM is bounded to helper tasks.
- Side effects are never free-run.
- Validation decides whether a run can continue.
- Reports are derived from persisted run data.

## Closing Pitch

The point of the demo is not that the model can improvise. The point is that the runtime can route work, constrain tools, preserve evidence, and stop before side effects without approval.
