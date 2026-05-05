# Demo Walkthrough

## What this project demonstrates
TaskFrame Runtime is a manifest-driven automation runtime for AI-assisted company operations. It shows how a controlled runtime can route work, execute bounded tools, keep a TaskFrame audit trail, and require validation plus approval before side effects.

## What this project is not
- It is not a chatbot.
- It is not a generic free-form agent demo.
- It is not a personal RPA scraper.
- It is not a demo business toy app.

## Demo prerequisites
- Python 3.11+
- Local demo fixtures and runtime data already seeded by the repo
- Optional browser-backed RPA is not required for the default demo path

## Run clean verification
```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

## Run golden demo
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

## Open operator UI
```powershell
python -m src.operator_ui
```

The console is the operator surface for scenario selection, TaskFrame inspection, tool health, approvals, and reports.

## Walkthrough 1 - Customer Order Status
Open the customer workflow demo and point out:
- the selected manifest
- the active TaskFrame
- the step timeline
- the validation summary
- the pending approval action

Explain that the LLM drafts wording only. The manifest and validations decide whether the reply can progress.

## Walkthrough 2 - Procurement Low-Stock Reorder
Switch to procurement and point out:
- low-stock detection
- deterministic reorder calculations
- supplier selection from demo data
- staged purchase-order messaging
- approval-gated side effects

Explain that the draft message is prepared by the runtime, but sending stays blocked until approval.

## Walkthrough 3 - Accounting Reconciliation
Open accounting and point out:
- reconciliation inputs
- matched and unmatched records
- exception summary output
- validation results
- sheet-write actions staged for approval only

Explain that the runtime records what it would write before anything can be executed.

## Walkthrough 4 - Approval-Gated Action
Show the pending-action area and point out:
- the human-readable action summary
- the approval and dry-run controls
- the TaskFrame state
- the audit trail in the runtime trace

Explain that side effects are never free-run. The approval gate is explicit and auditable.

## Walkthrough 5 - Tool Health Status
Open the tool capability panel and point out:
- tool names and categories
- core versus optional tools
- safe health status
- setup instructions
- read-only test controls

Explain that tools are visible and testable, but default verification uses safe probes only.

## Walkthrough 6 - Audit / Release Verification
Open the release verification report and point out:
- the clean-clone verifier verdict
- the golden demo result
- the optional RPA exclusion boundary
- the artifact links and runtime report paths

Explain that completion is validation-based, not model-certified.

## Known limitations
- Live browser-backed RPA probes require local operator setup and are excluded from clean-clone RC verification.
- Live Google Sheets and Ollama availability depend on the local environment.
