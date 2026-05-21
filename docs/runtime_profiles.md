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

## Live side-effect execution contract (Spec 132)

Spec 132 adds a formal contract for live side-effect execution. The `live` profile remains the only profile that could ever allow live side effects, and only when every check in the preflight gate passes.

Key points:

- Live side effects are disabled by default (`enabled: false` in the policy)
- The `live` profile still blocks live side effects unless `allow_live_side_effects: true` is explicitly set in the profile data
- `demo`, `dev`, `test`, `release`, and `pilot` profiles are unconditionally blocked
- `pilot` mode remains live-read only — it does not allow live writes

See [live_side_effect_execution_contract.md](live_side_effect_execution_contract.md) for the full contract.

## Spec 133 — Gmail send profile restrictions

`gmail/send` is the first live side-effect tool. Its profile restrictions follow the same rules as Spec 132:

- `demo`, `dev`, `test`, `release`, and `pilot` profiles are unconditionally blocked from live Gmail sends.
- `live` profile may allow sending only when manifest explicitly opts in and all preflight checks pass.
- Gmail sending is disabled by default (`enabled: false` in config).

See [live_gmail_send.md](live_gmail_send.md) for the Gmail send tool documentation.

## Spec 134 — Google Sheets write profile restrictions

`sheet/write_rows` is the second live side-effect tool. Its profile restrictions follow the same rules as Spec 132:

- `demo`, `dev`, `test`, `release`, and `pilot` profiles are unconditionally blocked from live Sheets writes.
- `live` profile may allow writes only when manifest explicitly opts in and all preflight checks pass.
- Sheets writing is disabled by default (`enabled: false` in config).
- No demo or pilot profile may enable live Sheets writing by default.
- `pilot` mode remains live-read only — it does not allow live writes to Sheets.

See [live_google_sheets_write.md](live_google_sheets_write.md) for the Sheets write tool documentation.
