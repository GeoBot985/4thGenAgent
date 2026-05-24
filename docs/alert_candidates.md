# Alert Candidates

Alert candidates are local, read-only recommendations produced by the operational monitoring snapshot. They help an operator see what would need attention without sending anything externally.

## Shape

Each alert candidate uses this structure:

```json
{
  "alert_id": "string",
  "severity": "info|warning|error|critical",
  "category": "worker|scheduler|queue|event_source|tool|manifest|safety|recovery|storage",
  "title": "string",
  "message": "string",
  "source_section": "worker",
  "recommended_action": "string",
  "evidence_refs": [],
  "created_at": "ISO-8601"
}
```

## Severity Guidance

- `critical` - the runtime should not be treated as service-ready
- `error` - manual review is needed before relying on the service runtime
- `warning` - degraded but not blocked
- `info` - useful evidence, but not a blocker by itself

## What It Does Not Do

Alert candidates do not:

- send email, Slack, Teams, or webhook notifications
- trigger automatic remediation
- clear locks
- execute live side effects

## Local Reports

The snapshot writes local alert-candidate evidence under `runtime_data/monitoring/`:

- `alert_candidates_latest.json`
- `alert_candidates_latest.md`

This keeps alert preparation local until a later spec adds delivery and incident workflow integration.
