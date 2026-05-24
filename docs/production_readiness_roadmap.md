# Production Readiness Roadmap

This repository has a controlled demo/pilot/service boundary, not a blanket claim of full production readiness.
The roadmap below shows the next hardening steps after the `service` runtime profile.

## Current Boundary

- `demo` remains the safe default for local and portfolio use.
- `pilot` remains the controlled live-read profile.
- `service` is the controlled worker-service deployment profile.
- `live` remains reserved.

## Next Hardening Specs

1. Worker soak testing
2. Observability and service health reporting
3. Live-read proof and live-read governance
4. Live side-effect governance and approval controls
5. Worker identity propagation and audit coverage
6. Deployment installation boundary

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
