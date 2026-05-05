# TaskFrame Runtime Portfolio Summary

## What It Is
TaskFrame Runtime is a TaskFrame-centered autonomous business automation runtime for AI-assisted company operations. It executes manifest-defined workflows through deterministic tools, bounded LLM calls, approval gates, dry-run execution, and durable reporting.

## What Makes It Different
Most agent demos are unconstrained. This project is designed for auditability and control:
- the orchestrator stays generic
- business behavior lives in manifests and tools
- LLM usage is bounded and explicit
- side effects require approval
- dry-run execution is central
- every run produces reports and evidence

## Technical Highlights
- One runtime across customer support, procurement, and accounting
- TaskFrame as the runtime case file
- Registered tools for deterministic business operations
- Real Ollama demo mode
- Approval-gated side effects
- Cross-workflow demo pack
- Markdown, HTML, and evidence bundle outputs

## Business Workflows Covered
- Customer support order-status workflow
- Procurement low-stock reorder workflow
- Accounting payment reconciliation workflow

## Why It Is Portfolio-Worthy
This repository demonstrates a practical architecture for controlled autonomous work: enough flexibility to handle multiple business domains, but enough structure to remain auditable, safe, and testable.

## Optional RPA Tools
Some browser-backed RPA tools are excluded from the default portfolio path because they depend on local browser state, external authentication, and brittle web UI behavior. These tools are useful for personal automation experiments but are not required for the core business automation runtime.

## Clean Release-Candidate Verification
From a clean clone, the supported RC path is:
```powershell
pytest
python scripts/run_golden_demo.py
python scripts/run_release_verification.py
```

This path uses deterministic demo data and local fixtures. It intentionally excludes optional browser-backed RPA from the default portfolio verification flow.

## Demo Materials
- [Demo Walkthrough](demo_walkthrough.md)
- [Demo Script](demo_script.md)
- [Screenshot Folder](screenshots/)
- [Core Concepts](core_concepts.md)
- [Release Verification](release_candidate_verification.md)
- [Release Artifacts](release_artifacts.md)
