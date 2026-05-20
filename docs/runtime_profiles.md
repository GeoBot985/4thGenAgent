# Runtime Profiles

TaskFrame separates execution safety from config loading. Runtime profiles decide whether the runtime can use fixtures, run dry-run by default, read live data, or stage and execute live side effects.

The safe default profile is `demo`.

## Resolution Order

Runtime profile selection uses this order:

1. explicit CLI argument
2. environment variable
3. user config file
4. safe internal default (`demo`)

The environment variable is `TASKFRAME_PROFILE`. `TASKFRAME_ENV` is kept as a legacy alias.

## Canonical Profile Contract

Each runtime profile exposes an inspectable contract with fields such as:

- `profile`
- `environment`
- `fixture_mode`
- `dry_run_default`
- `allow_live_reads`
- `allow_live_side_effects`
- `require_tool_governance`
- `allowed_toolpacks`
- `blocked_tool_classes`
- `llm_provider`
- `requires_credentials`
- `evidence_required`

The runtime also records whether the profile is reserved or blocked.

## Profiles

| Profile | Purpose | Fixture Mode | Live Reads | Live Side Effects | Notes |
| --- | --- | --- | --- | --- | --- |
| `demo` | Safe portfolio/demo mode | Yes | No | No | Default runtime profile |
| `dev` | Local development | Yes | Optional | No | Diagnostics can be relaxed, but live writes stay blocked |
| `test` | Deterministic test mode | Yes | No | No | Fixture-backed automated runs |
| `release` | Release verification | Yes | No | No | Strict gates, no live execution |
| `pilot` | Controlled live-read mode | No | Yes | No | Pilot mode allows allowlisted read-only toolpacks only |
| `live` | Reserved future production profile | No | Yes | No | Blocked unless a future override explicitly enables it |

## Safety Boundaries

- Default execution remains safe and dry-run by default.
- `pilot` allows controlled live reads only.
- Live side effects are not production-enabled.
- Unknown toolpacks stay blocked outside the narrow dev workflow.
- Tool governance and evidence remain required across all active profiles.

## CLI

Use these commands to inspect the active profile:

```bash
taskframe profile show
taskframe profile list
taskframe profile check
```

JSON output is available for all three commands.

## Operator Guidance

- Use `demo` for portfolio demos and default local runs.
- Use `pilot` only when the toolpack and credential boundary have been deliberately allowlisted.
- Treat `live` as reserved until a later spec explicitly enables it.

## Pilot Readiness Gate

The `pilot` profile is validated by the pilot readiness gate:

```bash
taskframe pilot-readiness
taskframe pilot-readiness --write-pack
```

The gate checks:
- Profile safety (no live side effects in default or pilot profile)
- Live-read control (explicit enable, no unknown toolpacks)
- Side-effect blocking evidence
- Tool governance, store integrity, monitoring, and recovery

See [pilot_readiness.md](pilot_readiness.md) for full documentation of the pilot readiness gate.
