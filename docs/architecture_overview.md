# Architecture Overview

TaskFrame Runtime is a manifest-driven automation runtime for AI-assisted company operations. The central rule is simple: business behavior belongs in manifests and tools, not in the orchestrator.

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
Validation / Acceptance Gate
    ->
TaskFrame Finalisation / Audit

| Block | Required explanation |
|---|---|
| Intent / Event | An explicit operator action, scheduled trigger, or external event starts the run. |
| Manifest Lookup | The runtime resolves the request to a manifest that defines allowed steps and validations. |
| TaskFrame Creation | A TaskFrame is created to hold the run state, outputs, evidence, validations, and audit trail. |
| Orchestrator / State Machine | The orchestrator executes known manifests and state transitions; it does not invent workflows. |
| Tools / LLM / Memory | Tools are deterministic adapters, the LLM is a bounded helper, and memory stores durable facts separate from TaskFrame outputs. |
| Validation / Acceptance Gate | Deterministic checks decide completion. The LLM cannot self-certify success. |
| TaskFrame Finalisation / Audit | The run is closed with a durable audit trail and evidence bundle. |

## Approval Gate
Side effects are staged as pending actions and must pass an approval gate before they can execute. This keeps live sends, writes, and other external actions visible and operator-controlled.

## Optional RPA Tools
Browser-backed RPA tools are treated as optional, high-risk, live-environment-dependent adapters. They are excluded from default clean-clone release verification because they depend on local browser state, external authentication, and changing web UIs. They can still support operator-triggered live probes in local mode, but they are not part of the default portfolio demo path.
