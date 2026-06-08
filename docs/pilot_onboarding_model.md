# Pilot Onboarding Model — Core Image + Customer Bundle

This document describes how TaskFrame Runtime is delivered to a pilot customer. It is a
**configurable automation core**, not a turnkey app: the engine is identical for every
customer, and each customer's automation — their manifests (procedures) and tool packs
(integrations) — is authored **case by case** as a separate, mounted **bundle**.

It is intentionally **single-tenant**: one deployment per customer. The README's "not a
multi-tenant SaaS" framing is correct and stays. What is added here is the explicit,
repeatable process for configuring one engagement.

---

## 1. The two layers

| | Core image | Customer bundle (mounted) |
|---|---|---|
| **Contents** | runtime, governed API, auth/hardening/audit, built-in `core_*` tool packs, manifest + tool-pack authoring/governance tooling | this customer's manifests, custom tool packs, config profile, enabled-pack list, credentials, runtime state |
| **Built by** | us, once per release | the onboarding engagement, once per customer |
| **Lifecycle** | versioned (`taskframe-runtime:<version>`), identical across customers | evolves with the customer; never rebuilt into the core |
| **Upgrades** | pull a new image; bundle untouched | author/extend in place; core untouched |

**Why the split:** a core upgrade must never risk a customer's authored logic, and one
customer's packs/credentials must never leak into another's deployment. Baking manifests
and packs into per-customer images entangles both and forces a rebuild of every customer
on every core change.

The loader already supports this: tool packs load from an external `base_path` /
`enabled_toolpacks.json`, config resolves via `TASKFRAME_CONFIG_DIR`, runtime state via
`TASKFRAME_RUNTIME_DIR`, and manifests resolve from `config/manifests/` as well as the
built-in `manifests/`.

---

## 2. Customer bundle skeleton

A new customer starts from this template (e.g. `bundles/<customer>/`), mounted into the
core image at `/bundle`:

```
bundles/<customer>/
  config/                         # → TASKFRAME_CONFIG_DIR=/bundle/config
    taskframe.service.json        # active runtime profile (live_execution.enabled=false)
    taskframe.backend.json        # backend auth tokens (env-injected), hardening, CORS
    enabled_toolpacks.json        # which core + custom packs are ON for this customer
    manifests/                    # this customer's *.manifest.json (resolved via config/manifests)
    google/                       # OAuth credentials.json / token.json, if Google tools used
    accounting_google_sheet.json  # if the accounting workflow is used
  tool_packs/                     # this customer's CUSTOM packs (referenced by enabled_toolpacks.json)
    <custom_pack>/
      toolpack.json
      tools.py
      health.py
      README.md
  runtime_data/                   # → TASKFRAME_RUNTIME_DIR; audit, runs, stores (persisted volume)
  .env                            # backend tokens + TASKFRAME_* env (never committed, never in image)
  ONBOARDING.md                   # filled-in record of this engagement (scope, decisions, sign-offs)
```

Container wiring (extends `docker-compose.yml`):

```yaml
    environment:
      TASKFRAME_CONFIG_DIR: "/bundle/config"
      TASKFRAME_RUNTIME_DIR: "/bundle/runtime_data"
      TASKFRAME_PROFILE: "service"
      TASKFRAME_BACKEND_AUTH_CONFIG_PATH: "/bundle/config/taskframe.backend.json"
      # Live execution stays OFF unless an engagement explicitly enables it (Section 6).
      TASKFRAME_ENABLE_LIVE_EXECUTION: "0"
    volumes:
      - ./bundles/<customer>:/bundle
```

> Manifest discovery honors `TASKFRAME_CONFIG_DIR/manifests`, so the bundle's manifests are
> auto-discovered from the mount with no bind sub-mount needed (see `_candidate_manifest_dirs`
> in `src/manifest_workbench.py`).

In practice, use the ready-made overlay rather than hand-writing the above:

```bash
cp -r bundles/_template bundles/acme
cp bundles/acme/.env.example bundles/acme/.env   # fill in strong tokens
CUSTOMER=acme docker compose -f docker-compose.yml -f docker-compose.bundle.yml up -d --build
```

---

## 3. The case-by-case onboarding runbook

Each customer engagement runs these steps. Every step has an existing governance gate —
this process is about *sequencing* them, not inventing new safety.

1. **Scope the workflows.** With the customer, list the procedures to automate (e.g.
   "process supplier invoice", "triage support inbox"). One manifest per procedure.
2. **Inventory required tools.** For each workflow, list the actions it needs (read sheet,
   send gmail, post ledger row…). Map each to a built-in `core_*` pack or a new custom pack.
3. **Author / scaffold tool packs.** Use the scaffold wizard
   (`docs/toolpack_scaffold_wizard.md`) for new packs. Each pack must pass the contract
   runner and governance checks (`docs/toolpack_contract.md`, `toolpack_governance.md`).
   Register it in `enabled_toolpacks.json`.
4. **Author manifests.** Follow `docs/manifest_building_manual.md` (and the LLM authoring
   guide). Validate under strict contract mode (`docs/manifest_contract_strict_mode.md`)
   and run catalog health (`manifest_catalog_health_repair.md`). Dry-run each manifest.
5. **Wire credentials** (Section 4) — only for the tools the customer actually uses.
6. **Run the governance + readiness gates** (Section 5). All must pass.
7. **Pilot-readiness gate.** `taskframe pilot-readiness --write-pack` ≥ threshold; review
   `docs/pilot_readiness.md`. Confirm `runtime_live_mode: false` on `/api/health`.
8. **Deploy** per `docs/deployment_onprem.md` with the bundle mounted.
9. **Operate.** Monitor health/audit; extend manifests/packs in the bundle as the pilot
   grows — the core image never changes for this.

Record scope, decisions, and sign-offs in the bundle's `ONBOARDING.md`.

---

## 4. Per-tool credential provisioning

Credentials are **per customer**, live in the bundle (never in the image), and are only
provisioned for tools that customer uses:

| Tool family | What's needed | Where it goes |
|---|---|---|
| Backend API auth | strong bearer tokens per role | `.env` → `TASKFRAME_BACKEND_*_TOKEN` |
| Google (Sheets/Gmail/Calendar) | OAuth `credentials.json` + `token.json` | `config/google/` (resolved via config dir) |
| Accounting sheet | sheet identifiers | `config/accounting_google_sheet.json` |
| RPA / browser | user-data + profile dir | bundle path referenced in `taskframe.service.json` |

Default: Google/RPA/live are **disabled** in `taskframe.service.json`. A read-only pilot
needs none of the live credentials.

---

## 5. Governance gates (already in the engine)

The onboarding process leans on existing gates — the design adds no new trust assumptions:

- **Tool packs:** contract runner, `toolpack_governance`, `toolpack_lifecycle`, per-pack
  `health.py`.
- **Manifests:** strict-contract validation, catalog health/repair, dry-run execution,
  authoring-feedback / autofix.
- **Runtime safety:** live side effects blocked by default; backend auth/hardening/audit;
  `pilot-readiness` scorecard with a pass threshold.

The **backend auth boundary is not a substitute for the live-execution guardrails** — both
remain in force for a pilot.

---

## 6. Enabling live actions (only when an engagement asks for it)

A read-only pilot keeps `live_execution.enabled=false` and
`TASKFRAME_ENABLE_LIVE_EXECUTION=0`. Turning on a specific live action (e.g. a sheet write)
is a deliberate, per-engagement decision gated by the existing live-execution approval and
ledger machinery (`docs/live_execution_safety.md`,
`docs/live_side_effect_execution_contract.md`) — never a default, never global.

---

## 7. Status of the open items

All four onboarding gaps are now closed:

- **ONB-GAP-1 — externalize manifest dir.** ✅ Done. `_candidate_manifest_dirs` in
  `src/manifest_workbench.py` honors `TASKFRAME_CONFIG_DIR/manifests`; bundle manifests are
  auto-discovered with no bind sub-mount.
- **ONB-GAP-2 — fence demo vs product content.** ✅ Done. See
  [content_classification.md](content_classification.md). Customer bundles start with an
  empty `config/manifests/` and only safe core packs enabled; demo/smoke content stays in
  the core image for CI/evaluation only.
- **ONB-GAP-3 — bundle template + skeleton.** ✅ Done. `bundles/_template/` plus the
  `docker-compose.bundle.yml` overlay (`CUSTOMER=<name> docker compose -f docker-compose.yml
  -f docker-compose.bundle.yml up`).
- **ONB-GAP-4 — onboarding checklist artifact.** ✅ Done. `bundles/_template/ONBOARDING.md`
  captures scope, enabled packs, credentials, gate results, and sign-off.

Remaining judgement calls for you (not blockers): resolve the `license` field, and decide
per engagement whether `core_llm_micro` / `google_workspace` are in scope.
