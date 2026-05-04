# Architecture Overview

TaskFrame Runtime is built around a simple rule: business behavior belongs in manifests and tools, not in the orchestrator.

The system starts with an operator event or scenario selection. Event routes map the event into a manifest ID and normalized inputs. The manifest defines the steps, validations, and completion criteria for that workflow. The orchestrator remains generic and simply drives the TaskFrame through the manifest.

Tools perform deterministic work such as reading business data, selecting records, building drafts, validating totals, or staging side effects. Bounded LLM calls are used only for fuzzy tasks such as drafting customer wording, supplier wording, or accounting exception summaries. Approval gates prevent side effects from being executed directly. Approved actions are then executed in dry-run mode, preserving safety and auditability.

Every run is captured as a TaskFrame with outputs, validations, tool calls, LLM calls, pending actions, executed actions, audit events, and a report/evidence bundle. This makes the runtime suitable for controlled business automation rather than unconstrained agent behavior.

