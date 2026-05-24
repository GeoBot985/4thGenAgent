# Service Runtime Profile

The `service` runtime profile defines how TaskFrame can run as a controlled worker service.
It is intended for deployment-style execution, not as proof of full production readiness.

## Purpose

The profile provides a safe boundary for worker service operations:

- explicit environment selection
- worker identity metadata
- dry-run by default
- tool governance required
- evidence required
- live reads blocked
- live side effects blocked
- optional RPA blocked

## How It Differs

| Profile | Purpose | Notes |
| --- | --- | --- |
| `demo` | Default local demo path | Safe portfolio/demo mode |
| `pilot` | Controlled live-read profile | Allowlisted read-only toolpacks only |
| `service` | Controlled worker service profile | Deployment boundary, still safe by default |
| `live` | Reserved live profile | Not enabled for general use |

The `service` profile is more deployment-oriented than `demo` or `pilot`, but it still blocks live side effects and unsafe tool classes.
It is not the same as the reserved `live` profile.

## Worker Identity

Service mode requires a worker identity record with:

- `worker_id`
- `worker_role`
- `environment`
- `operator_id`
- `approval_authority`
- `runtime_instance_id`

`runtime_instance_id` is generated if it is missing.
`worker_id` is required for the service profile to pass preflight.

## Preflight

Run the service preflight before starting a worker cycle:

```bash
taskframe service preflight --profile service --json
```

Preflight checks:

- profile exists and is not `live`
- dry-run is the default
- live reads are blocked
- live side effects are blocked
- tool governance is required
- evidence is required
- worker identity is present and valid
- runtime data directory is writable
- manifest catalog loads
- tool registry loads
- event routes load
- optional RPA is blocked
- no unknown external toolpacks are enabled
- config does not point credentials at the repository root

Preflight writes:

- `runtime_data/service/service_preflight_latest.json`
- `runtime_data/service/service_preflight_latest.md`

## Status

Read the current service state with:

```bash
taskframe service status --profile service --json
```

Status reports:

- active profile and environment
- runtime data directory
- worker identity
- live-read and live-side-effect status
- enabled toolpacks
- last worker cycle, if available
- latest monitoring snapshot, if available
- latest recovery summary, if available

Status writes:

- `runtime_data/service/service_status_latest.json`

## Run Once

Run one bounded worker cycle only after preflight passes:

```bash
taskframe service run-once --profile service --json
```

`run-once`:

- calls the existing bounded worker cycle
- refuses unsafe service configuration
- keeps live side effects disabled
- records a service-cycle artifact
- includes worker identity in the cycle output

Run-once writes:

- `runtime_data/service/service_cycle_latest.json`

## Why This Is Not Full Production Readiness

The service profile creates the deployment/runtime boundary, but it does not add:

- Docker or VM deployment
- Windows service or systemd installation
- live side-effect execution
- live send/write approval execution
- multi-user SaaS tenancy
- cloud infrastructure
- real alerting
- long soak testing

Those belong to later hardening specs.
