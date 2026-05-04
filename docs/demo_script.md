# Cross-Workflow Demo Script

## Demo Objective
Show that one TaskFrame runtime can execute three different business workflows with manifest-driven logic, bounded LLM usage, approval gates, dry-run execution, and auditable outputs.

## Prerequisites
- Python 3.11+
- Ollama running locally
- `granite3.3:8b` available
- Accounting Google Sheet config present

## 5-Minute Demo Path
1. Open the architecture diagram.
2. Open the operator UI.
3. Run the customer support scenario.
4. Run the procurement scenario.
5. Run the accounting scenario.

## 10-Minute Demo Path
1. Show the architecture diagram and explain the runtime layers.
2. Open the operator UI and point out scenario selection, approval controls, and report panels.
3. Run the customer support approval flow.
4. Run the procurement approval flow.
5. Run the accounting approval flow.
6. Run the cross-workflow demo pack.
7. Open the generated report and evidence bundle for each lane.

## Suggested Narration
- This is not a free-form agent.
- The orchestrator is generic.
- Business logic lives in manifests and tools.
- The LLM only drafts bounded text.
- Side effects are approval-gated.
- Dry-run execution is the default safety mode.
- Every run produces reports and evidence.

## Expected Outputs
- TaskFrame state transitions
- Pending actions and approval pack
- Executed dry-run actions
- Markdown and HTML reports
- Evidence bundle JSON
- Cross-workflow aggregate report

## Troubleshooting
- If a scenario fails, check the failure summary in the report.
- If accounting fails, confirm the Google Sheet config includes a spreadsheet ID.
- If LLM preflight fails, confirm Ollama is running and `granite3.3:8b` is available.

