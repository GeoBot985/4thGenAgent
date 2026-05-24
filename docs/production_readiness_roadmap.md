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
- These changes improve operational evidence and failure recovery without enabling live side effects.

## Next Hardening Specs

1. Observability and service health reporting
2. Live-read proof and live-read governance
3. Live-side-effect governance and approval controls
4. Worker identity propagation and audit coverage
5. Deployment installation boundary

## Deferred Work

- Docker packaging
- Windows service or systemd support
- multi-user tenancy
- cloud infrastructure
- production alerting
- long-running soak validation

## Notes

The service profile is the boundary required to harden the runtime without accidentally enabling live side effects or optional browser automation.
It is not a production deployment guarantee.
