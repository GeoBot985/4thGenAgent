# Content Classification — Product vs Demo

The core image ships a lot of manifests and tool packs. Most are **demo, smoke-test, or
reference** content used for evaluation and CI — **not** customer workflows. This document
draws the line so a customer bundle starts clean and only product-grade, governed content
is enabled for a pilot.

**Governing principle:** a customer bundle starts with an **empty `config/manifests/`** and
enables only the safe core tool packs. Nothing in the core image's `manifests/` is a
customer workflow — those are authored fresh into the bundle per engagement
(see [pilot_onboarding_model.md](pilot_onboarding_model.md)).

---

## Tool packs

| Pack | Class | In clean customer bundle? |
|------|-------|---------------------------|
| `core_business` | core | **Yes** (enabled by default) |
| `core_memory` | core | **Yes** (enabled by default) |
| `core_reports` | core | **Yes** (enabled by default) |
| `core_llm_micro` | core | Optional — only if an LLM provider is configured |
| `google_workspace` | optional / live | Only when a Google workflow is scoped + credentials provisioned |
| `demo_echo` | optional / demo | **No** — evaluation only |

The bundle template's `config/enabled_toolpacks.json` enables the three safe core packs.
`core_llm_micro` and `google_workspace` are opt-in per engagement; `demo_echo` is never
shipped to a customer.

## Manifests (all in the core image — none auto-loaded into a bundle)

| Group | Examples | Class |
|-------|----------|-------|
| Smoke tests | `smoke_*` (~60 files) | CI / internal — never a customer workflow |
| Live demos | `live_gmail_check`, `live_calendar_next`, `live_gobook_open_courts` | Demo of live integration |
| Showcase workflows | `invoiceops*`, `order.*`, `supplier_invoice_match`, `customer_status_llm_e2e`, `llm_*` | Portfolio/demo — a template to author from, not to ship as-is |
| Maintenance utilities | `maintenance_*`, `maintenance.scheduled` | Operational; may be reused as product utilities if the engagement needs them |
| Stubs / config | `event.stub`, `event_routes.json`, `schedules.json` | Scaffolding |

None of these are copied into a customer bundle automatically. Reuse a showcase manifest
only by deliberately copying it into `bundles/<customer>/config/manifests/` and
re-validating it for that customer.

## Why not delete the demo content from the repo?

The smoke and demo manifests/packs are exercised by the test suite and release
verification. They stay in the **core image** (used for evaluation and CI) but are fenced
from **customer bundles** by the bundle defaults above. This keeps CI intact while ensuring
a pilot starts from a clean, governed baseline.
