# Portfolio Evidence Pack

## Purpose

The portfolio evidence pack presents TaskFrame as a controlled business automation runtime in a form that is suitable for demos, GitHub, interviews, stakeholder review, and portfolio presentation.

This portfolio pack is evidence for a controlled demo system. It must not be represented as proof of production readiness.

## What It Contains

- An architecture summary
- A demo script
- Workflow proof
- Tool inventory
- Readiness status links
- Screenshot checklist
- Known limitations
- Optional links to the latest story pack and readiness scorecard

## How to Generate It

```powershell
taskframe portfolio-pack
```

Useful options:

- `--json`
- `--open`
- `--no-story-pack`
- `--no-readiness`

## How to Use It in a Demo

Open `index.html` first. It gives a reviewer-facing summary of the runtime, the workflows, the tools, and the current readiness posture.

Then walk through:

1. `architecture.md`
2. `demo_script.md`
3. `workflow_proof.md`
4. `tool_inventory.md`
5. `known_limitations.md`

If the latest story pack and readiness scorecard exist, use them as supporting evidence.

## How It Links to Story and Readiness Evidence

The pack links:

- the latest cross-workflow story pack from Spec 112, when available
- the latest readiness scorecard from Spec 113, when available

These links are optional. The portfolio pack remains valid even when one or both are unavailable, provided it states that clearly.

## Limitations

- This pack documents a controlled portfolio/demo runtime, not production live automation.
- Live side effects are blocked or approval-staged.
- Some workflows use seeded demo data.
- External systems may require credentials.
- RPA is not part of the default release path.
- Production deployment would require security, monitoring, tenancy, and operational hardening.
