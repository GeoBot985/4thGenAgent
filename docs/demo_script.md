# Demo Script

## 30-second pitch
Most AI demos prove that a model can talk about work. This project proves that a controlled AI runtime can perform bounded business work with explicit routing, manifest-defined tasks, TaskFrame audit records, validation gates, and approval-controlled side effects.

## Architecture explanation
- The manifest chooses the allowed workflow path.
- The TaskFrame is the runtime case file and audit source of truth.
- Tools are deterministic adapters, not open-ended agents.
- The LLM handles fuzzy sub-tasks only, such as drafting wording.
- Approvals gate side effects before anything can execute.
- Validation determines completion, not model confidence.

## Demo flow
1. Run clean verification.
2. Run the golden demo.
3. Open the operator UI.
4. Inspect the TaskFrame and step timeline.
5. Show a pending approval action.
6. Open the tool health panel.
7. Open the report and release verification artifacts.

## What to point out on screen
- The manifest ID and TaskFrame ID.
- The current state and completed steps.
- The validation summary and evidence/audit paths.
- The pending action summary and dry-run controls.
- The tool capability registry and health status.
- The release verdict and optional RPA exclusion boundary.

## Closing statement
The point of the demo is not that the model can improvise. The point is that the runtime can route work, constrain tools, preserve evidence, and stop before side effects without approval.
