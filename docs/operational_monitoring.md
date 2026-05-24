# Operational Monitoring

Operational monitoring is the read-only runtime snapshot layer for TaskFrame. It consolidates worker status, worker hardening, soak evidence, scheduler state, queue state, event-source state, recovery state, tool health, manifest health, live-safety status, pending-action risk, runtime profile safety, and storage health into one operator-facing report.

## Snapshot Status

The consolidated snapshot uses four overall statuses:

- `HEALTHY` - no blockers and no high-severity alert candidates
- `DEGRADED` - warnings exist, but service operation can continue
- `ATTENTION_REQUIRED` - manual review is needed before relying on service mode
- `BLOCKED` - the runtime should not run as a controlled service

## Snapshot Commands

Use:

```bash
taskframe monitor snapshot --profile service --json
taskframe monitor snapshot --profile service --write-report --json
taskframe monitor alerts --profile service --json
```

The snapshot and alert commands are read-only. They do not run worker cycles, clear locks, execute pending actions, or send alerts.

## Sections

The snapshot includes these sections:

- `service_preflight`
- `worker`
- `worker_hardening`
- `worker_soak`
- `scheduler`
- `queue`
- `event_sources`
- `recovery`
- `tool_health`
- `manifest_health`
- `live_safety`
- `pending_actions`
- `runtime_profile`
- `storage`

Each section reports:

- `ok`
- `status`
- `summary`
- `details`
- `warnings`
- `errors`

## What It Checks

The snapshot is designed to answer one question: can this runtime be configured and started as a controlled worker service without accidentally enabling live side effects or unsafe external tools?

It checks:

- service preflight readiness
- worker identity presence
- stale or duplicate worker lock risk
- queue, scheduler, and event-source health
- manifest health and tool health
- recovery risk for failed TaskFrames
- pending-action live-read risk
- runtime profile safety
- storage integrity

## What It Does Not Do

Operational monitoring does not:

- send email, Slack, Teams, or webhook alerts
- run Prometheus/Grafana integrations
- auto-remediate anything
- auto-clear stale locks
- execute live writes or live sends
- start background daemons

## Production Readiness Boundary

This snapshot improves the evidence boundary for production-style operation, but it does not claim full production readiness. The runtime still keeps live side effects blocked in service mode and relies on explicit operator review for alert candidates.

See [alert_candidates.md](alert_candidates.md) for the alert-candidate model.
