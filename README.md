# Automation Agent

TaskFrame-Centered Autonomous Business Automation Runtime

## 30-Second Summary
This project demonstrates controlled AI-assisted business automation without open-ended agent behavior. Work is routed through explicit commands or events, executed through manifest-defined steps, recorded in TaskFrames, validated through deterministic acceptance gates, and paused for approval before side effects. The LLM is used only as a bounded helper for fuzzy tasks such as extraction, drafting, summarisation, and classification.

## What This Project Demonstrates
- A manifest-driven runtime for AI-assisted company operations
- TaskFrame as the source of runtime state, outputs, evidence, validations, and audit
- An orchestrator that executes known workflows without inventing business logic
- Deterministic tools plus bounded LLM steps
- Approval gates before side effects
- Validation-based completion rather than model self-certification

## What This Project Is Not
- Not a chatbot
- Not a free-roaming agent
- Not an RPA scraper
- Not a system where the LLM freely chooses tools
- Not a system where the LLM self-certifies success

The runtime controls the business process. The LLM helps with fuzzy interpretation only.

## Architecture Overview
Intent or event
-> manifest lookup
-> TaskFrame creation
-> orchestrator / state machine
-> tools / LLM / memory
-> validation / acceptance gate
-> TaskFrame finalisation and audit

| Block | Meaning |
|---|---|
| Intent / Event | Explicit operator action, schedule, or external trigger |
| Manifest | Instruction plus validation contract for a workflow |
| TaskFrame | Source of runtime state, outputs, evidence, validations, and audit |
| Orchestrator | Executes known manifests; does not invent workflows |
| Tools | Deterministic adapters for bounded business operations |
| LLM | Bounded helper for fuzzy steps such as extraction and drafting |
| Memory | Durable facts separated from TaskFrame outputs |
| Validation Gate | Determines completion; the LLM cannot self-certify |
| Approval Gate | Required before side effects can execute |

## Core Concepts
See [docs/core_concepts.md](docs/core_concepts.md) for short definitions of TaskFrame, manifest, tool capability, health checks, approval gates, and release verification.

## Demo Workflows
- Customer Support order-status workflow
- Procurement low-stock reorder workflow
- Accounting reconciliation workflow
- Approval-gated action workflow
- Reporting and release verification workflow

Start with the customer workflow, then review procurement, accounting, the pending approval state, the tool health panel, and the final audit/report output.

## Tool Capability / Health Status
The operator UI includes a tool capability and status view. Core tools expose safe read-only health checks. Optional RPA tools expose a separate live-probe path because browser automation can only be meaningfully verified by actually opening the target environment.

- Safe health checks: read-only, always allowed
- Setup guidance: explicit instructions for missing prerequisites
- Live RPA probes: operator-triggered only, never part of clean-clone RC verification
- No health check performs live side effects

## Clean Release-Candidate Verification
From a clean clone:
```powershell
pip install -r requirements.txt
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

The clean RC path uses deterministic demo data and local fixtures. It does not require Playwright, Google Messages login, local browser profiles, or personal ABSA data.

## Golden Demo
Run the deterministic portfolio demo:
```powershell
python scripts/run_golden_demo.py
```

This exercises the default portfolio workflows only:
- customer order status
- procurement low-stock reorder
- accounting reconciliation
- approval-gated action handling
- report and audit generation

## Operator UI
Launch the operator console:
```powershell
python -m src.operator_ui
```

Use it to inspect the active TaskFrame, pending approvals, tool health, and report output.

## Screenshots
Review the current portfolio screenshots in [docs/screenshots/](docs/screenshots/):
- [01_operator_home.png](docs/screenshots/01_operator_home.png)
- [02_scenario_pack.png](docs/screenshots/02_scenario_pack.png)
- [03_taskframe_detail.png](docs/screenshots/03_taskframe_detail.png)
- [04_step_playback.png](docs/screenshots/04_step_playback.png)
- [05_pending_approval.png](docs/screenshots/05_pending_approval.png)
- [06_tool_status_panel.png](docs/screenshots/06_tool_status_panel.png)
- [07_tool_health_details.png](docs/screenshots/07_tool_health_details.png)
- [08_report_output.png](docs/screenshots/08_report_output.png)
- [09_release_verification.png](docs/screenshots/09_release_verification.png)

Related demo docs:
- [Demo Walkthrough](docs/demo_walkthrough.md)
- [Demo Script](docs/demo_script.md)

## Repository Structure
| Path | Purpose |
|---|---|
| `runtime/` | Core runtime, TaskFrame, orchestration, tools, validation |
| `manifests/` | Manifest-defined workflows and event routes |
| `config/` | Demo configuration and route definitions |
| `scripts/` | Golden demo and release verification scripts |
| `docs/` | Architecture, glossary, demo docs, screenshots, release docs |
| `tests/` | Unit, integration, boundary, and verification tests |
| `optional_tools/` | Optional/private tools excluded from the default RC path |
| `runtime_data/` | Seeded demo data and generated artifacts |

## Optional RPA Tools
Browser-backed RPA tools are treated as optional, high-risk, live-environment-dependent adapters. They are excluded from the default portfolio path and from default clean-clone release verification because they depend on local browser state, external authentication, and changing web UIs. They can still support operator-triggered live probes in local mode, but they are not part of the default portfolio demo path.

## Runtime Notes
- Ollama can provide the bounded LLM helper used by the customer, procurement, and accounting workflows when a local endpoint is available.

## Known Limitations
- The current project is a portfolio-grade release candidate, not a production deployment.
- External live integrations are either dry-run, fixture-backed, or approval-gated.
- Optional browser-backed RPA tools are excluded from clean-clone verification.
- The demo business dataset is intentionally small and deterministic.
- The UI is intended for operator demonstration, not enterprise administration.

## Roadmap
1. Release candidate packaging
2. Optional live integration profiles
3. Batch and queue orchestration
4. Scheduler UI
5. External event ingestion
6. Expanded business scenario packs

## Supporting Docs
- [Adding New Tools](docs/adding_new_tools.md)
- [Tool Contract Checklist](docs/tool_contract_checklist.md)
- [Runtime Contracts](docs/runtime_contracts.md)
- [Current Release Status](docs/current_release_status.md)
- [Release Evidence Pack](docs/release_evidence_pack.md)
- [Default Demo Boundary](docs/default_demo_boundary.md)
- [Known Limitations](docs/known_limitations.md)
- [Release Verification](docs/release_candidate_verification.md)
- [Release Artifacts](docs/release_artifacts.md)
- [Core Concepts](docs/core_concepts.md)
- [Portfolio Summary](docs/portfolio_summary.md)
