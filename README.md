# TaskFrame Runtime

TaskFrame Runtime is a manifest-driven autonomous business worker runtime for controlled AI-assisted company operations.

It demonstrates how autonomous workers can follow defined procedures, use tools, validate results, pause for approval, and produce audit-ready evidence without giving the LLM open-ended control.

What this project solves:
- controlled execution of business workflows
- deterministic validation before completion
- approval-gated side effects instead of silent action
- run-bound evidence and reports for review and audit

What it is not:
- not a chatbot
- not a general-purpose AI assistant
- not an open-ended agent
- not a loose demo script
- not a pure RPA bot

Quick start:

```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
python -m src.operator_ui
```

The clean release-candidate verification path is:

```powershell
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

Recommended demo workflow:
1. Open the operator UI.
2. Select `Customer Status - Happy Path`.
3. Run the demo and show the business-readable Demo View.
4. Open the run report and point out the step outcomes and pending approval.
5. Select `Customer Status - Missing Customer`.
6. Run the failed validation demo and show the safe stop.
7. Select `Report Generation - Happy Path`.
8. Open the business report and the run report.
9. End with the release verification evidence.

Primary references:
- [Final Portfolio Walkthrough](docs/final_portfolio_walkthrough.md)
- [Current Release Status](docs/current_release_status.md)
- [Release Candidate Verification](docs/release_candidate_verification.md)
- [Release Candidate Evidence Index](docs/release_candidate_evidence_index.md)

## What This Project Is

This project demonstrates controlled autonomous business work.

A runtime executes manifest-defined workflows, records every step in a TaskFrame, applies deterministic validation, pauses for approval before side effects, and produces audit-readable reports for each run.

The LLM is used as a bounded helper for tasks such as extraction, classification, drafting, and summarisation. It does not choose tools freely and it does not certify success.

## What Problem It Solves

It shows how AI-assisted workers can operate inside explicit business controls:

- defined procedures
- allowed tools
- validation gates
- approval checkpoints
- durable evidence trails

That makes the system useful as a productized automation runtime prototype rather than a chatbot or a loose demo script.

## Core Design Principles

- Manifest-driven execution, not open-ended prompting
- TaskFrame as the source of truth for run state, outputs, evidence, validations, and audit
- Bounded LLM usage only where fuzzy interpretation helps
- Deterministic validation decides completion
- Approval gates before side effects
- Run-bound reports and evidence for every demo run
- Optional live integrations stay outside clean-clone verification

## Architecture Overview

Intent or event
-> manifest lookup
-> TaskFrame creation
-> orchestrator / state machine
-> tools / LLM / memory
-> validation / approval gates
-> TaskFrame finalisation and audit

| Block | Meaning |
|---|---|
| Intent / Event | An explicit operator action, scheduled trigger, or external event starts the run. |
| Manifest | Defines the allowed workflow, inputs, steps, and validations. |
| TaskFrame | Holds run state, outputs, evidence, validations, audit events, and approvals. |
| Orchestrator | Executes known workflows; it does not invent business logic. |
| Tools | Deterministic adapters for bounded business operations. |
| LLM | Bounded helper for fuzzy interpretation and drafting only. |
| Validation Gate | Deterministic checks decide completion. |
| Approval Gate | Required before side effects can execute. |
| Reports | Run-bound HTML/Markdown evidence for business review and audit. |

See [docs/product_boundary.md](docs/product_boundary.md) for the product boundary summary and architectural framing.

## Demo Scenarios

The current demo catalog covers four product lanes.

### Customer Status Workflows

Purpose:
- Answer a customer about an order status

What the worker does:
- reads the customer request
- extracts the order reference
- checks customer, order, payment, and shipment records
- drafts a reply
- waits for approval before any live send

Expected result:
- a prepared reply or a safe validation stop

Report / evidence produced:
- a run report showing manifest steps, step outcomes, validations, pending actions, and evidence
- a business report when the scenario is report-generation specific

Scenario examples:
- Happy path
- Missing customer
- Wrong customer/order
- Unsupported intent

This is the Customer Support lane in the portfolio demo set.

### Procurement Workflows

Purpose:
- Prepare a low-stock reorder for approval

What the worker does:
- reads inventory and supplier data
- builds a reorder draft
- stages a supplier message or purchase-order action
- waits for approval before any send or write

Expected result:
- a staged procurement action or a safe stop

Report / evidence produced:
- a run report with step-by-step evidence and approval status

Scenario examples:
- Low-stock reorder
- Approval dry run

This is the Procurement lane in the portfolio demo set.

### Accounting Workflows

Purpose:
- Reconcile payments, orders, invoices, and ledger data

What the worker does:
- loads accounting records
- reconciles mismatches
- prepares exception evidence
- stages reviewable outputs

Expected result:
- a reconciliation summary or a validation failure

Report / evidence produced:
- a run report with validations, outputs, and audit trail

Scenario examples:
- Reconciliation
- Exception handling

This is the Accounting lane in the portfolio demo set.

### Report Generation Workflows

Purpose:
- Produce a business report and a run-bound audit report

What the worker does:
- reads the selected source data
- generates a business report artifact
- produces a run report for the exact frame
- writes an evidence bundle

Expected result:
- a visible business report path
- a run report showing manifest steps, outcomes, validations, evidence, and pending actions

Report / evidence produced:
- business report
- run report
- evidence bundle

Scenario examples:
- Business report
- Run-bound audit report

## Report Types

| Report | Purpose |
|---|---|
| Business report | Output generated by a report-generation workflow |
| Run report | Audit-style report showing manifest steps, step outcomes, validations, evidence, and pending actions |

The Demo screen shows both when relevant:

- `Business report generated` points to the scenario-specific business artifact.
- `Run report generated` points to the audit-style report for the current frame.

## How To Run

Run the supported verification path:

```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

Launch the operator console:

```powershell
python -m src.operator_ui
```

Run the golden demo directly:

```powershell
python scripts/run_golden_demo.py
```

## How To Inspect Reports And Evidence

The operator UI surfaces run-bound artifacts for the active frame.

Use the Demo view to:

- create or open the business report when the selected scenario generates one
- create or open the run report for the active frame
- inspect the evidence bundle path shown on the screen

Run reports are persisted under `runtime_data/outputs/reports/` and evidence bundles under `runtime_data/outputs/evidence/`.

Key evidence files:

- [docs/current_release_status.md](docs/current_release_status.md)
- [docs/release_candidate_verification.md](docs/release_candidate_verification.md)
- [docs/release_candidate_evidence_index.md](docs/release_candidate_evidence_index.md)
- [docs/release_evidence_pack.md](docs/release_evidence_pack.md)
- [runtime_data/outputs/reports/golden_demo_report.html](runtime_data/outputs/reports/golden_demo_report.html)
- [runtime_data/outputs/audit/golden_demo_audit.json](runtime_data/outputs/audit/golden_demo_audit.json)

The report and evidence trail are meant to answer:

- what the customer asked
- what the worker checked
- what result the worker prepared
- whether anything was sent automatically
- what approval or validation was required

## Safety Model

- The runtime executes only manifest-defined work.
- The LLM is not allowed to invent workflows or choose arbitrary tools.
- Side effects are staged and gated.
- Validation determines whether a run completed safely.
- Reports are generated from persisted run data, not from live UI state.
- Optional browser-backed RPA tools stay outside the default clean-clone path.

## Current Release Status

See [docs/current_release_status.md](docs/current_release_status.md) for the current verified status, command results, evidence files, and known limitations.

## Known Limitations

- The project is a controlled runtime prototype, not a production deployment.
- Live integrations can be dry-run, fixture-backed, or approval-gated.
- Optional browser-backed RPA tools are excluded from the default clean-clone verification path.
- The demo business dataset is intentionally small and deterministic.
- The UI is designed for operator demonstration and inspection.

## Portfolio Value

This repository demonstrates a practical architecture for controlled autonomous work:

- manifest-driven business procedures
- TaskFrame auditability
- deterministic validation
- approval checkpoints
- bounded LLM use
- run-bound evidence reports
- a clear boundary between runtime logic and presentation logic

That makes it a strong portfolio artifact for productized automation, not a chatbot demo.

## Screenshots

Review the current portfolio screenshots in [docs/screenshots/](docs/screenshots/):

- [01_operator_home.png](docs/screenshots/01_operator_home.png)
- [02_demo_customer_happy_path.png](docs/screenshots/02_demo_customer_happy_path.png)
- [03_demo_customer_pending_approval.png](docs/screenshots/03_demo_customer_pending_approval.png)
- [04_run_report_step_outcomes.png](docs/screenshots/04_run_report_step_outcomes.png)
- [05_demo_customer_failed_validation.png](docs/screenshots/05_demo_customer_failed_validation.png)
- [06_report_generation_demo.png](docs/screenshots/06_report_generation_demo.png)
- [07_business_report_visible_path.png](docs/screenshots/07_business_report_visible_path.png)
- [08_tool_status_panel.png](docs/screenshots/08_tool_status_panel.png)
- [09_release_verification.png](docs/screenshots/09_release_verification.png)

## Repository Structure

| Path | Purpose |
|---|---|
| `runtime/` | Core runtime, TaskFrame, orchestration, tools, validation, and report generation |
| `src/` | Tkinter UI, presenters, scenario/demo orchestration, and report launchers |
| `manifests/` | Manifest-defined workflows and event routes |
| `config/` | Demo configuration and route definitions |
| `scripts/` | Golden demo and release verification scripts |
| `docs/` | Architecture, boundary, demo, screenshots, and release docs |
| `tests/` | Unit, integration, boundary, and verification tests |
| `optional_tools/` | Optional/private tools excluded from the default RC path |
| `runtime_data/` | Seeded demo data and generated artifacts |

## Optional RPA Tools

Browser-backed RPA tools are treated as optional, high-risk, live-environment-dependent adapters. They are excluded from the default portfolio path and from default clean-clone release verification because they depend on local browser state, external authentication, and changing web UIs. They can still support operator-triggered live probes in local mode, but they are not part of the default portfolio demo path.

## Supporting Docs

- [Final Portfolio Walkthrough](docs/final_portfolio_walkthrough.md)
- [Product Boundary](docs/product_boundary.md)
- [Architecture Overview](docs/architecture_overview.md)
- [Demo Walkthrough](docs/demo_walkthrough.md)
- [Portfolio Summary](docs/portfolio_summary.md)
- [Current Release Status](docs/current_release_status.md)
- [Release Evidence Pack](docs/release_evidence_pack.md)
- [Default Demo Boundary](docs/default_demo_boundary.md)
- [Known Limitations](docs/known_limitations.md)
- [Release Verification](docs/release_candidate_verification.md)
- [Release Artifacts](docs/release_artifacts.md)
- [Core Concepts](docs/core_concepts.md)
- [Adding New Tools](docs/adding_new_tools.md)
- [Tool Contract Checklist](docs/tool_contract_checklist.md)

## Runtime Notes

- Ollama can provide the bounded LLM helper used by the customer, procurement, and accounting workflows when a local endpoint is available.
- The accounting demo scenarios default to the local demo sheet id `demo-sheet-local` so they run deterministically without a live Google Sheets connection. Update `config/accounting_google_sheet.json` if you want to point the scenarios at a real spreadsheet.
