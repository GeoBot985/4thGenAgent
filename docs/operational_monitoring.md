# Operational Monitoring

Operational monitoring is the read-only inspection layer on top of runtime artifacts, TaskFrames, approvals, evidence, tool health, and runtime-store validation. It is meant to help a controlled pilot operator quickly see what is healthy, failed, pending, stuck, or blocked.

## Run Health Classifications

The canonical run-health model uses these classifications:

- `healthy` - completed successfully or no operator action is needed
- `pending` - waiting for approval or input
- `warning` - completed with non-blocking issues
- `failed` - runtime, validation, tool, or completion failure
- `stuck` - the run has not advanced within the stale threshold
- `blocked` - external auth, dependency, or profile-policy problems prevent progress

## Commands

Use:

```bash
taskframe monitor summary
taskframe monitor failed
taskframe monitor pending
taskframe monitor stuck
taskframe monitor blocked
taskframe monitor tools
taskframe monitor report
```

All commands support `--runtime-data-dir`, `--profile`, `--limit`, `--rebuild`, and `--json`.

## Stuck-Run Detection

Stale detection is threshold-based and does not auto-recover anything.

- `RUNNING` older than the configured threshold becomes `stuck`
- `WAITING_FOR_INPUT` older than the configured threshold stays `pending` but gets a stale warning
- `WAITING_FOR_EXECUTE` older than the configured threshold stays `pending` but gets a stale approval warning
- repeated external auth or dependency failures are surfaced as `blocked`

The thresholds are:

```json
{
  "running_stale_minutes": 10,
  "waiting_for_input_stale_hours": 24,
  "waiting_for_execute_stale_days": 7,
  "external_dependency_retry_window_minutes": 30
}
```

## Tool Health

Monitoring reuses the existing safe tool-health snapshot and does not introduce live side effects. The aggregated tool-health status is interpreted as:

- `ready`
- `needs_auth`
- `missing_dependency`
- `misconfigured`
- `failing`
- `disabled_optional`
- `unknown`

For pilot readiness, live reads are only meaningful when the active profile allows them and the relevant read tools are healthy.

## What Monitoring Does Not Do

Monitoring does not:

- retry failed runs automatically
- recover stuck runs automatically
- send alerts or email notifications
- run background daemons
- perform destructive cleanup
- enable live writes, sends, or deletes

## Controlled Pilot Readiness

This layer supports controlled pilot readiness by making failure visibility and runtime discipline explicit. It is not full production monitoring and it does not claim production-grade incident response.

## Pilot Readiness Integration

Operational monitoring is validated as part of the pilot readiness gate. The gate checks:

- Monitoring report can be generated without error
- Monitoring documentation is present

See [pilot_readiness.md](pilot_readiness.md) for the full pilot readiness gate documentation.

## Recovery Cross-Reference

Monitoring and recovery work together:

- monitoring tells the operator which runs are healthy, failed, pending, stuck, or blocked
- recovery tells the operator whether a specific run is retryable or resumable
- both remain dry-run and operator-controlled
