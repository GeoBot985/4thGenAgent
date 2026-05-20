# Pilot Readiness

> **Controlled pilot readiness only.**
> No full production readiness is claimed.
> No unsupervised live side effects are enabled.

This document describes the controlled pilot readiness gate, what it checks, what evidence it produces, and what remains blocked.

## What Is Pilot Readiness?

The pilot readiness gate determines whether the TaskFrame runtime is suitable for a **controlled, supervised, live-read pilot**. It is not a production readiness claim.

There are three distinct readiness levels:

| Level | What it means |
|---|---|
| **Demo/portfolio readiness** | Safe, fixture-backed demonstrations. No live data. |
| **Controlled pilot readiness** | Limited, supervised, live-read pilots. No live side effects. |
| **Production readiness** | Full production automation. Not yet claimed or enabled. |

## How to Run the Pilot Readiness Gate

```bash
# Show the scorecard
taskframe pilot-readiness

# Show as JSON
taskframe pilot-readiness --json

# Write the full evidence pack to disk
taskframe pilot-readiness --write-pack

# Fail with non-zero exit if gate fails
taskframe pilot-readiness --strict
```

## Scorecard Areas

The pilot readiness scorecard evaluates nine areas with a weighted score:

| Area | Weight |
|---|---|
| Runtime profile safety | 15% |
| Live-read control | 15% |
| Side-effect blocking | 15% |
| Tool governance | 10% |
| Runtime-store integrity | 10% |
| Backup/restore validation | 10% |
| Monitoring visibility | 10% |
| Recovery/idempotency controls | 10% |
| Documentation/evidence | 5% |

**Minimum pass threshold: 80%**

The gate also enforces mandatory checks that can block the gate regardless of the weighted score.

## Mandatory Safety Checks

The gate fails immediately if any of these are true:

- Active/default profile allows live side effects
- Pilot profile allows live side effects
- Live side-effect tools can execute without approval
- Unknown toolpacks can run in pilot mode
- Runtime-store validation fails
- Monitoring report cannot be generated
- Recovery assessment cannot be generated
- Duplicate side-effect protection is missing
- Pilot documentation is missing
- Evidence pack claims production readiness

## What the Evidence Pack Contains

Running `taskframe pilot-readiness --write-pack` writes:

```
runtime_data/pilot_readiness/<timestamp>/
  pilot_readiness_scorecard.json      — weighted scorecard with area scores
  pilot_readiness_report.md           — human-readable report
  pilot_readiness_report.html         — reviewer-facing HTML
  runtime_profile_summary.json        — active and pilot profile configuration
  live_read_preflight.json            — live-read preflight check results
  side_effect_blocking_evidence.json  — proof that blocked actions remain blocked
  tool_governance_report.json         — toolpack governance policy report
  runtime_store_validation.json       — store structure and integrity
  backup_restore_validation.json      — backup command and restore readiness
  monitoring_summary.json             — operational monitoring report
  recovery_idempotency_summary.json   — recovery assessment and idempotency controls
  limitations.md                      — known limitations (human-readable)
  README.md                           — reviewer-facing overview
```

The pack clearly states:
- Controlled pilot readiness only
- No full production readiness claimed
- No unsupervised live side effects enabled

## Live-Read Pilot Mode

In `pilot` mode, the runtime:

- Allows live reads via allowlisted read-only toolpacks (`google_workspace_readonly`)
- Disables all live side effects (sends, writes, deletes, mutations)
- Requires tool governance for every toolpack execution
- Requires explicit credentials (no service account bypass)
- Blocks unknown toolpacks

### Live-Read Preflight

Before a live-read pilot session, run:

```bash
taskframe pilot-readiness --json | python -m json.tool
```

The `live_read_preflight` section reports one of:

| Status | Meaning |
|---|---|
| `ready` | All preflight checks pass |
| `needs_auth` | Credentials or tool health snapshot missing |
| `missing_config` | Required configuration absent |
| `blocked` | Profile not in pilot mode or side effects enabled |

## What Remains Blocked

The following actions are blocked and cannot execute in pilot mode:

- Gmail: send email
- Google Sheets: write range
- Google Calendar: delete or update events
- External systems: create record
- RPA: any live mutation
- Any unknown side-effect tool

Evidence of this blocking is captured in `side_effect_blocking_evidence.json`.

## Known Limitations

See [known_limitations.md](known_limitations.md) for the full list. Pilot-specific limitations include:

| Limitation | Impact |
|---|---|
| No unsupervised production automation | All automation requires operator approval |
| No live writes/sends/deletes | Read-only pilot only |
| No autonomous recovery daemon | Recovery is operator-initiated |
| No production database backend | File-based store; not for concurrent production load |
| No enterprise authentication | Service account only; no SSO or RBAC |
| No multi-user access control | Single-operator model |
| No formal deployment hardening | Local/dev environment only |
| No SLA or alerting system | Manual health monitoring |

## Release Verifier Integration

The release verifier (`taskframe verify`) includes the pilot readiness gate. It:

- Runs the pilot readiness scorecard
- Writes the pilot evidence pack
- Fails if the scorecard output is malformed
- Fails if production readiness is claimed in the evidence pack
- Includes a `pilot_readiness_gate` entry in the release checks output

## Future Production Readiness Work

Pilot readiness is not production readiness. To reach production readiness, future specs would need to address:

- Enterprise authentication and RBAC
- Production database backend
- Formal deployment hardening and environment isolation
- SLA monitoring and automated alerting
- Autonomous recovery with supervised escalation paths
- Multi-user access control and audit separation
