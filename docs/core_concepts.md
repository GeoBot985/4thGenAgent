# Core Concepts

## TaskFrame
The TaskFrame is the runtime case file for a single run. It stores inputs, outputs, evidence, validations, tool calls, LLM calls, pending actions, and audit events. It is the source of truth for what happened during execution.

## Manifest
A manifest defines the workflow instructions, allowed steps, validation rules, and completion conditions. It is both the instruction contract and the acceptance contract for a run. The orchestrator executes the manifest; it does not invent new business logic.

## ToolResult
A ToolResult is the structured output returned by a tool adapter. It records what the tool did, what it observed, and any error or status details. ToolResults are designed to be deterministic and easy to audit.

## Pending Action
A pending action is a side effect that has been prepared but not executed. It keeps the operation visible, inspectable, and approval-gated. Pending actions help prevent accidental live writes or sends.

## Approval Gate
The approval gate is the operator control point for side effects. Nothing sensitive should execute until the action is reviewed and approved. This keeps the runtime safe even when a workflow has prepared a live operation.

## Validation Gate
The validation gate decides whether a run is complete. It checks outputs and evidence against the manifest contract and runtime facts. The LLM cannot self-certify completion.

## Bounded LLM Step
A bounded LLM step uses the model for a narrow task such as extraction, drafting, summarisation, or classification. The model does not choose the workflow or bypass validations. Its output is always constrained by the runtime.

## Tool Capability
Tool capability is the metadata that says what a tool is for, whether it is core or optional, what setup it needs, and whether it has side-effect risk. This makes the tool layer visible and explainable in the operator UI.

## Health Check
A health check is a safe read-only probe that verifies whether a tool is usable. Health checks should not send, write, delete, or otherwise mutate external systems. They are used to show readiness without introducing risk.

## Live RPA Probe
A live RPA probe is an operator-triggered browser-backed check for optional RPA tools. It opens the target environment read-only and verifies that the session and surface are usable. It is excluded from clean-clone release verification because it depends on local browser state and authentication.

## Golden Demo
The golden demo is the deterministic portfolio run that exercises the core business workflows. It produces reports, audit artifacts, and release-candidate outputs using only the default demo path. It is the main proof that the runtime works in a clean clone.

## Release Verification
Release verification is the clean-clone check that confirms the repo still runs as intended. It validates the default tool registry, scenario pack, golden demo, release artifacts, and documentation alignment. Known limitations are recorded, but default functionality must still pass.
