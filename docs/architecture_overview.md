# Architecture Overview

TaskFrame Runtime is a manifest-driven autonomous business worker runtime for AI-assisted company operations.

The central rule is simple:

- business behavior belongs in manifests and tools
- presentation behavior belongs in `src/`
- runtime execution stays controlled, auditable, and deterministic where it matters

Intent / Event
    ->
Manifest Lookup
    ->
TaskFrame Creation
    ->
Orchestrator / State Machine
    ->
Tools / LLM / Memory
    ->
Validation / Approval Gates
    ->
TaskFrame Finalisation / Audit

| Block | Required explanation |
|---|---|
| Intent / Event | An explicit operator action, scheduled trigger, or external event starts the run. |
| Manifest Lookup | The runtime resolves the request to a manifest that defines allowed steps and validations. |
| TaskFrame Creation | A TaskFrame is created to hold run state, outputs, evidence, validations, and audit trail. |
| Orchestrator / State Machine | The orchestrator executes known manifests and state transitions; it does not invent workflows. |
| Tools / LLM / Memory | Tools are deterministic adapters, the LLM is a bounded helper, and memory stores durable facts separate from TaskFrame outputs. |
| Validation / Acceptance Gate | Deterministic checks decide completion and approval gates control side effects. |
| TaskFrame Finalisation / Audit | The run is closed with a durable audit trail, evidence bundle, and run report. |

## Controlled LLM Use

The LLM is used for bounded tasks such as:

- extraction
- classification
- drafting
- summarisation

It is not allowed to choose arbitrary tools or certify the final outcome.

## Run-Bound Evidence

Reports and evidence are generated from persisted run data, not from the live UI state.

- `runtime/run_report.py` builds run reports and evidence bundles
- `src/demo_story_presenter.py` builds the business-readable Demo view model
- `src/operator_ui.py` renders widgets and calls actions, but does not build business meaning

## Approval Gate

Side effects are staged as pending actions and must pass an approval gate before they can execute. This keeps live sends, writes, and other external actions visible and operator-controlled.

## Order Management Workflow Lane

The order management lane (Spec 110) adds five manifest-driven workflows for
validating new orders, reserving stock, releasing paid orders, detecting delayed
shipments, and updating shipment status. All business logic lives in
`runtime/order_management_tools.py` and the five manifests in `manifests/`.
The orchestrator is unchanged — no order logic was added to it. Side-effect
operations (stock reservation, order release, shipment update) follow the
standard prepare/execute approval pattern: prepare tools stage pending actions;
execute tools run with `dry_run=True` and require operator approval before any
mutation is simulated. See [docs/order_management_workflows.md](order_management_workflows.md).

## Optional RPA Tools

Browser-backed RPA tools are treated as optional, high-risk, live-environment-dependent adapters. They are excluded from default clean-clone release verification because they depend on local browser state, external authentication, and changing web UIs. They can still support operator-triggered live probes in local mode, but they are not part of the default portfolio demo path.

## Boundary Summary

- `runtime/` owns execution, persistence, validation, tool routing, and reporting
- `runtime/persistence_backends/` owns the persistence backend contract plus filesystem and SQLite implementations
- `runtime/event_queue_contract.py` defines the Spec 137 durable queue record shape and status constants
- `runtime/event_queue_runner.py` processes PENDING queue items into TaskFrames (always dry-run)
- `runtime/operator_queue_panel.py` provides read-only queue data for the operator UI
- `runtime/event_sources/` owns the Spec 139 external event source polling framework (adapters, polling engine, state, contract)
- `src/operator_event_sources_panel.py` provides read-only event source data for the operator UI
- `runtime/worker/` owns the Spec 140 local worker supervisor (worker_contract, worker_lock, worker_engine)
- `src/operator_worker_panel.py` provides read-only worker status and cycle history for the operator UI
- `src/` owns UI presentation and view-model construction
- `tools/` owns CLI utilities and release verification
- `optional_tools/` owns optional integration surfaces
- `bits/` contains a separate FastAPI/RAG prototype path

See [docs/product_boundary.md](product_boundary.md) for the product framing in one place.
