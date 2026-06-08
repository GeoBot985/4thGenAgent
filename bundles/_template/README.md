# Customer Bundle Template

This directory is the starting point for a **single customer engagement**. Copy it to
`bundles/<customer>/` and fill it in during onboarding. The bundle holds everything that is
specific to one customer; the core image stays identical across all customers.

See [docs/pilot_onboarding_model.md](../../docs/pilot_onboarding_model.md) for the full model
and [docs/deployment_onprem.md](../../docs/deployment_onprem.md) for deployment.

## Create a new customer bundle

```bash
cp -r bundles/_template bundles/acme
cp bundles/acme/.env.example bundles/acme/.env   # then fill in strong tokens
```

## Layout

```
config/
  taskframe.service.json     active runtime profile — live execution OFF by default
  taskframe.backend.json     backend auth tokens (env-injected), hardening, CORS
  enabled_toolpacks.json     which core + custom tool packs are ON for this customer
  manifests/                 this customer's *.manifest.json (auto-discovered)
  google/                    OAuth credentials.json / token.json, if Google tools used
tool_packs/                  this customer's CUSTOM packs (referenced by enabled_toolpacks.json)
runtime_data/                audit, runs, stores — persisted (mount as a volume)
.env                         backend tokens + TASKFRAME_* env (never commit; never bake into image)
ONBOARDING.md                the record of this engagement (scope, decisions, sign-offs)
```

## Run it

The bundle mounts into the core image at `/bundle`. From the repo root:

```bash
CUSTOMER=acme docker compose -f docker-compose.yml -f docker-compose.bundle.yml up -d --build
```

The override sets `TASKFRAME_CONFIG_DIR=/bundle/config` and
`TASKFRAME_RUNTIME_DIR=/bundle/runtime_data`, so the engine discovers this customer's
manifests, packs, config, and credentials from the mounted bundle — nothing is baked in.

## Safety defaults

- `live_execution.enabled = false` and `TASKFRAME_ENABLE_LIVE_EXECUTION=0` — read-only pilot.
- Backend auth is ON; no dev bypass.
- Enabling any live action is a deliberate, per-engagement decision — see the onboarding model, Section 6.
