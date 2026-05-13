# Product Boundary

## Positioning

This repository is a manifest-driven autonomous business worker runtime prototype.

It demonstrates:

- TaskFrame audit records
- approval gates
- deterministic validation
- bounded LLM use
- deterministic tool execution
- run-bound evidence reports

It is not positioned as a chatbot, a generic AI assistant, or a loose demo script.

## Scope Map

| Area | In scope |
|---|---|
| Runtime | Manifest execution, validation, TaskFrame state, tool calls, and evidence capture |
| Demo company | Mock business workflows and seeded demo data |
| UI | Operator, Demo, and Inspector presentation |
| Reports | Run-bound HTML and Markdown evidence |
| Optional integrations | RPA and live external tools outside the default RC path |

## What It Is

- Controlled autonomous business work
- Workflow execution defined by manifests
- Runtime state and audit trail captured in TaskFrame
- Deterministic business validation and approval checkpoints
- Business-readable demo stories and run reports

## What It Is Not

- An open-ended chatbot
- A free-form agent that picks arbitrary tools
- A silent side-effect executor
- A model-certified success system
- A pure RPA bot
- Production-ready unsupervised operation
- Live external automation by default
- Arbitrary LLM tool control
- Use of real customer or supplier data by default

## Architecture Boundary

| Layer | Responsibility |
|---|---|
| `runtime/` | Execute manifests, validate outcomes, persist state, and generate run reports |
| `src/` | Build UI-friendly and demo-friendly view models and render the Tkinter console |
| `tools/` | Provide CLI utilities, verification, and operator support |
| `optional_tools/` | Hold optional integration surfaces that are excluded from the default verification path |
| `bits/` | Contain a separate FastAPI/RAG prototype path |

## Demo And Report Boundary

- `src/demo_story_presenter.py` turns runtime state into a business-readable demo story.
- `runtime/run_report.py` turns persisted run data into an audit-style report and evidence bundle.
- `src/operator_ui.py` renders those models and dispatches actions; it does not invent business meaning.

## Why This Matters

The design shows how AI-assisted workers can operate inside business controls:

- defined procedures
- allowed tools
- validation gates
- approval checkpoints
- evidence trails

That is the product boundary this repository is meant to communicate.
