# Production Readiness Roadmap

This repository has a controlled demo/pilot/service boundary, not a blanket claim of full production readiness.
The roadmap below shows the next hardening steps after the `service` runtime profile.

## Current Boundary

- `demo` remains the safe default for local and portfolio use.
- `pilot` remains the controlled live-read profile.
- `service` is the controlled worker-service deployment profile.
- `live` remains reserved.

## Delivered Hardening

- Spec 151 established the service runtime profile boundary.
- Spec 152 added worker hardening, stale-lock recovery evidence, and the bounded soak harness.
- Spec 153 added the consolidated operational monitoring snapshot and alert-candidate pack.
- Spec 157 added post-write reconciliation and accounting evidence packs for InvoiceOps live posting.
- Spec 158 added the InvoiceOps Live Bookkeeping Showcase Demo Pack: 8 invoice scenarios, live Google Sheets posting under `controlled_live_write` profile, formatted demo workbook, dashboard, and accounting evidence trail.
- Pilot release packaging delivered the on-prem Docker bundle: a self-contained core image (`src.production_backend:app` via uvicorn, non-root, healthcheck, loopback bind, auth on / dev-bypass off, live execution disabled) plus the per-customer bundle overlay (`docker-compose.bundle.yml`, `bundles/_template`, onboarding gate). See [deployment_onprem.md](deployment_onprem.md).
- These changes improve operational evidence and failure recovery without enabling live side effects.

## Next Hardening Specs

1. Live-read proof and live-read governance
2. Live-side-effect governance and approval controls
3. Worker identity propagation and audit coverage
4. Deployment installation boundary
5. Alert delivery and incident workflow integration
6. Broader accounting reconciliation and rollback governance

## Deferred Work

- Windows service or systemd support
- multi-user tenancy
- cloud infrastructure
- production alerting
- long-running soak validation

## Notes

The service profile is the boundary required to harden the runtime without accidentally enabling live side effects or optional browser automation.
It is not a production deployment guarantee.
