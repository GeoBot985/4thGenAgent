# Tool Pack Governance + Environment Enablement Policy

Every tool pack that runs in the TaskFrame runtime must have a recorded governance decision. This document defines the classification system, environment profiles, and CLI commands for managing tool pack policy.

## Why Governance

Without explicit governance:

- A developer enables an optional pack
- A manifest starts using it
- The demo or release path accidentally depends on it
- High-risk or experimental behavior leaks into default runtime

The governance model ensures that only approved, classified packs can run in restricted environments (demo, release, live).
Runtime enforcement now consumes this policy directly, so governance is not just a CLI/reporting concern.

## Tool Pack Classifications

| Classification | Meaning | Default environments |
|---|---|---|
| `core` | Built-in packs — part of the default runtime | All (demo, dev, test, release, live) |
| `optional` | External or integration packs — safe, but not core | dev, test only by default |
| `experimental` | Packs under active development | dev only |
| `high_risk` | Live side effects, RPA, or dangerous operations | None — must be explicitly enabled per-env |
| `blocked` | Explicitly disabled — may not run anywhere | None |

When in doubt, classify higher risk. It is easy to promote; it is harder to contain a mis-classified pack.

## Environment Profiles

| Environment | Purpose | Restricted? |
|---|---|---|
| `demo` | Safe operator demo — shown to stakeholders | Yes — core and explicitly approved optional only |
| `dev` | Local development | No — all safe classifications allowed |
| `test` | CI and automated testing | No — core and optional allowed |
| `release` | Release candidate verification | Yes — core only by default |
| `live` | Production execution | Yes — core and explicitly approved optional only |

`demo` and `release` are the most restricted environments. `high_risk` and `experimental` packs are never allowed in `demo` or `release` unless a governance violation is explicitly accepted and recorded.

At runtime, discovery does not imply execution permission. The tool runner must evaluate governance before execution, staging, pending-action approval, and live health probes.

## Governance Config

Governance decisions are recorded in `config/toolpack_governance.json`. Each entry records:

- `toolpack_id` — the pack being governed
- `classification` — one of the classifications above
- `enabled_environments` — environments where this pack is active
- `enabled_by` — who recorded the decision
- `enabled_at` — ISO timestamp of the decision
- `reason` — human-readable justification

Example entry:

```json
{
  "toolpack_id": "google_workspace",
  "classification": "optional",
  "enabled_environments": ["dev", "test"],
  "enabled_by": "operator",
  "enabled_at": "2026-05-16T00:00:00+00:00",
  "reason": "Auth not verified for demo/release yet."
}
```

## CLI Reference

### Show policy

```bash
# All packs
taskframe tools policy --json

# One pack
taskframe tools policy google_workspace --json
```

### Enable a pack

```bash
taskframe tools enable my_pack \
  --classification optional \
  --env dev,test \
  --by operator \
  --reason "Safe integration, no live side effects"
```

### Disable a pack

```bash
# Disable in specific environments
taskframe tools disable my_pack --env release,live

# Disable everywhere
taskframe tools disable my_pack --reason "Quarantined — pending security review"
```

### Governance report

```bash
taskframe tools governance-report --json
taskframe tools governance-report
```

The report shows packs by classification and environment, and flags any policy violations. The release verifier runs this check automatically.

## Policy Violations

The following conditions are treated as violations:

- A `high_risk` or `experimental` pack is enabled in `demo` or `release`
- A `blocked` pack has any enabled environments
- A pack in `demo` or `release` is classified `high_risk`, `experimental`, or `blocked`

Violations cause `taskframe tools governance-report` to exit non-zero and fail the release verifier.

## Release Verifier Integration

The release verifier runs `validate_governance_for_release()` which checks:

1. `governance_config_exists` — `config/toolpack_governance.json` is present
2. `no_policy_violations` — no classification/environment conflicts
3. `demo_env_safe` — no unsafe packs in the demo environment
4. `release_env_safe` — no unsafe packs in the release environment

Any failure blocks the release candidate.

## Seeding a New Pack

After scaffolding a new pack, record its governance decision before committing:

```bash
taskframe tools scaffold my_pack --namespace mypkg --tool run --safe-read
taskframe tools enable my_pack --classification optional --env dev,test --reason "Initial scaffold"
taskframe tools governance-report
```

See [toolpack_scaffold_wizard.md](toolpack_scaffold_wizard.md) and [toolpack_contract_testing.md](toolpack_contract_testing.md) for the complete authoring workflow.
