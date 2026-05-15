# Default Demo Boundary

This document freezes what belongs in the default clean-clone RC path and what does not.

## Included in Default RC

- Customer workflow
- Procurement workflow
- Accounting workflow
- Approval gate
- Dry-run execution
- Report generation
- Audit evidence
- Runtime contract inspection

## Excluded From Default RC

- Optional RPA tools
- Live WhatsApp or Gmail sending
- Live browser automation
- Live execution from the default demo path
- Unbounded LLM tool choice
- Production credentials
- Real customer or supplier data

## Rule

Optional tools may exist in the repo, but they must not be imported or required by the default RC verification path.
The default release candidate remains manifest-driven, TaskFrame-centered, approval-gated, and validation-based.

Adding a tool does not automatically add it to the default RC path.

A new tool is excluded from the default RC path unless:

- it is needed by the golden demo
- it has safe health checks
- it has deterministic tests
- it does not require live credentials for default verification
- it does not enable live side effects by default
- it keeps live execution behind explicit safety guardrails and confirmation
