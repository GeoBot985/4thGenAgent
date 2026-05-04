# TaskFrame Runtime Portfolio Summary

## What It Is
TaskFrame Runtime is a controlled automation runtime for business workflows. It executes manifest-defined workflows through a TaskFrame-centered runtime, deterministic tools, bounded LLM calls, approval gates, dry-run execution, and durable reporting.

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
