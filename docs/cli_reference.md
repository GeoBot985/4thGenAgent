# TaskFrame CLI Reference

`taskframe` is the public command-line entry point for the packaged runtime.

## Commands

### `taskframe ui`

Launches the Tkinter operator console.

- `--runtime-data-dir runtime_data`

Exit codes:
- `0` on normal close
- non-zero if the UI cannot start

### `taskframe demo`

Runs one safe operator demo scenario.

The `cross-workflow-v2` subcommand runs the consolidated cross-workflow business story and writes a story pack under `runtime_data/demo_packs/<pack_run_id>/story_pack/`.

- `--scenario <scenario_id>`
- `--runtime-data-dir runtime_data`
- `--reset-dataset`
- `--report`
- `--local-llm`
- `--json`

Exit codes:
- `0` when the scenario completes successfully
- non-zero on scenario failure

### `taskframe readiness`

Builds the 90% readiness scorecard.

- `--runtime-data-dir runtime_data`
- `--strict`
- `--threshold 90`
- `--open-report`
- `--json`

Exit codes:
- `0` when the scorecard passes or when strict mode is off
- non-zero when strict mode fails

### `taskframe portfolio-pack`

Builds the public-facing portfolio evidence pack.

- `--runtime-data-dir runtime_data`
- `--no-story-pack`
- `--no-readiness`
- `--open`
- `--json`

Exit codes:
- `0` when the portfolio evidence pack is generated successfully
- non-zero when pack generation fails

### `taskframe pilot-readiness`

Runs the controlled pilot readiness gate and scorecard.

- `--runtime-data-dir runtime_data`
- `--write-pack` — write the full pilot evidence pack to disk
- `--strict` — exit non-zero if the scorecard fails
- `--json`

Exit codes:
- `0` when the gate passes or when strict mode is off
- non-zero when strict mode fails or gate is blocked

### `taskframe golden-demo`

Runs the golden demo verification.

Exit codes:
- `0` when the golden demo passes
- non-zero when it fails

### `taskframe verify`

Runs release verification.

- `--mode quick`
- `--mode standard`
- `--mode release`

Suggested test profiles:

```powershell
# Fast local / Claude Code default
python -m pytest tests -m "not slow and not release and not integration and not live" -q

# Standard local confidence run
python -m pytest tests -m "not release and not live" -q

# Full release verification
python tools/run_release_candidate_verification.py --mode release
```

Exit codes:
- `0` when release verification is `READY` or `READY_WITH_KNOWN_LIMITATIONS`
- non-zero when release verification fails

### `taskframe safety-status`

Prints the current live execution safety summary.

- `--runtime-data-dir runtime_data`
- `--json`

Exit codes:
- `0` on success

### `taskframe pending-actions`

Lists pending actions for the active frame or for a specific frame id.

- `--frame-id <frame_id>`
- `--runtime-data-dir runtime_data`
- `--json`

Exit codes:
- `0` on success, including when no pending actions are present

### `taskframe live-preflight`

Shows why one pending action is blocked, dry-run-only, or ready for typed confirmation.

- `--frame-id <frame_id>`
- `--action-id <action_id>`
- `--runtime-data-dir runtime_data`
- `--manifest-dir manifests`
- `--json`

Exit codes:
- `0` when the action reaches live-ready confirmation mode
- non-zero when live execution is blocked

### `taskframe execute-approved`

Executes an approved pending action in dry-run mode by default.

- `--frame-id <frame_id>`
- `--action-id <action_id>`
- `--runtime-data-dir runtime_data`
- `--manifest-dir manifests`
- `--dry-run`
- `--live`
- `--i-understand-live-side-effects`
- `--confirm "<phrase>"`
- `--json`

Exit codes:
- `0` when the dry-run path succeeds
- `0` when the live path succeeds after all guardrails pass
- non-zero when live execution is blocked or the dry-run path fails

Live execution requires `TASKFRAME_ENABLE_LIVE_EXECUTION=1` and a typed confirmation phrase. `--live` alone is insufficient.

**Spec 132 typed confirmation:** The `--confirm` argument must be the literal string `LIVE-EXECUTE`. Any other value (including the frame-scoped phrase) fails with `TYPED_CONFIRMATION_REQUIRED`.

```bash
# Dry-run (default and safe)
taskframe execute-approved --frame-id <frame_id> --action-id <action_id> --dry-run

# Live execution (all gates must pass)
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "LIVE-EXECUTE"
```

### `taskframe gmail-send dry-run`

Validates a pending Gmail send action without calling the Gmail API.

```bash
taskframe gmail-send dry-run --frame-id <frame_id> --action-id <action_id>
```

Exit codes:
- `0` on valid payload
- non-zero when payload validation fails

### `taskframe gmail-send preflight`

Runs the full Spec 132 preflight gate plus the `gmail_send` guardrail for a pending Gmail send.

```bash
taskframe gmail-send preflight --frame-id <frame_id> --action-id <action_id>
```

**Live Gmail send** requires all preflight checks and guardrail checks to pass, plus the `LIVE-EXECUTE` typed confirmation:

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "LIVE-EXECUTE"
```

Gmail live send is blocked in `demo`, `pilot`, `release`, `test`, and `dev` profiles. Only the `live` profile with explicit manifest opt-in may execute a live Gmail send.

### `taskframe sheet-write dry-run`

Validates a pending Sheets write action without calling Google Sheets API.

```bash
taskframe sheet-write dry-run --frame-id <frame_id> --action-id <action_id>
```

Exit codes:
- `0` on valid payload
- non-zero when payload validation fails

### `taskframe sheet-write preflight`

Runs the full Spec 132 preflight gate plus the `sheet_write_rows_guardrail` for a pending Sheets write.

```bash
taskframe sheet-write preflight --frame-id <frame_id> --action-id <action_id>
```

**Live Sheets write** requires all preflight checks and guardrail checks to pass, plus the `LIVE-EXECUTE` typed confirmation:

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "LIVE-EXECUTE"
```

Sheets live write is blocked in `demo`, `pilot`, `release`, `test`, and `dev` profiles. Only the `live` profile with explicit manifest opt-in and a configured allowlist may execute a live Sheets write.

### `taskframe config show`

Prints the active config profile in sanitized form.

Exit codes:
- `0` on success
- non-zero on failure

### `taskframe config paths`

Prints the configuration lookup paths.

Exit codes:
- `0` on success
- non-zero on failure

### `taskframe config init --profile <name>`

Copies an example profile into the user config directory.

Exit codes:
- `0` when initialization succeeds
- non-zero if the file already exists or the example profile cannot be found

### `taskframe manifest-health`

Runs the active manifest catalog health check in report mode by default.

- `--manifest-dir manifests`
- `--runtime-data-dir runtime_data`
- `--no-smoke`
- `--smoke-limit <n>`
- `--strict`
- `--json`

Exit codes:
- report mode: `0` even when failures are found
- strict mode: `0` only when no failures are found

Manifest health modes:

- `taskframe manifest-health` writes the report and exits successfully for operator inspection.
- `taskframe manifest-health --strict --no-smoke` is the release-gate mode and exits non-zero on active catalog failures.
- `taskframe manifest-health --json --no-smoke` prints a compact JSON summary while still writing the report files.

### `taskframe readiness`

Builds the 90% readiness scorecard for the controlled demo/portfolio path.

- `--strict`
- `--threshold <number>`
- `--runtime-data-dir runtime_data`
- `--open-report`
- `--json`

The scorecard writes JSON, Markdown, and HTML reports under `runtime_data/readiness/`.

### `taskframe manifests validate-strict <manifest_path>`

Validates one manifest against the strict contract without running smoke execution.

- `--json`

Exit codes:
- `0` when the manifest passes strict validation
- non-zero when strict validation fails

### `taskframe manifests gallery`

Runs the manifest regression gallery for curated bad, edge-case, and unsafe fixtures.

- `taskframe manifests gallery list`
- `taskframe manifests gallery validate`
- `taskframe manifests gallery run --fixture completion_output_missing`
- `taskframe manifests gallery report`
- `list`
- `validate`
- `run --fixture <fixture_id>`
- `report`
- `--gallery-dir tests/fixtures/manifest_regression_gallery`
- `--runtime-data-dir runtime_data`
- `--no-smoke`
- `--no-autofix`
- `--no-repair-guidance`
- `--json`

For a cheap validation pass, use:

```powershell
taskframe manifests gallery validate --no-smoke --no-autofix --no-repair-guidance
```

Gallery reports are written to `runtime_data/manifest_regression_gallery/`.

### `taskframe version`

Prints the installed runtime version.

Exit codes:
- `0`

### `taskframe tools discover`

Discovers configured tool packs and reports whether they are enabled, valid, and registered.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` on success

### `taskframe tools list`

Lists registered tools, including any external tool-pack tools that are currently enabled.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` on success

### `taskframe tools inspect <tool_or_toolpack_id>`

Inspects one built-in tool or one external tool pack.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` on success
- non-zero when the target cannot be found

### `taskframe tools validate <toolpack_path>`

Validates a tool pack descriptor.

- `--json`

Exit codes:
- `0` when validation passes
- non-zero when validation fails

### `taskframe tools health <toolpack_id>`

Runs the tool pack health check for one pack.

- `--config-path config/enabled_toolpacks.json`
- `--json`

Exit codes:
- `0` when the tool pack is healthy or intentionally disabled
- non-zero when health fails

### `taskframe tools lifecycle <toolpack_path>`

Evaluates the full operator lifecycle for one tool pack and produces a structured readiness report.

- `--env demo|dev|test|release|live`
- `--config-path config/enabled_toolpacks.json`
- `--runtime-data-dir runtime_data`
- `--no-contract` â€” skip contract tests
- `--no-health` â€” skip health checks
- `--no-manifest-smoke` â€” skip example manifest smoke validation
- `--write-report` â€” write JSON and Markdown lifecycle reports
- `--json`

Exit codes:
- `0` when the tool pack is ready or ready with warnings
- non-zero when the pack is invalid, blocked, disabled, or otherwise not ready

### `taskframe tools inventory`

Builds the merged tool inventory report.

- `--runtime-data-dir runtime_data`
- `--json`

Exit codes:
- `0` on success

### `taskframe tools compat-check`

Compares the migrated built-in tool packs with the legacy fallback registry.

- `--json`

Exit codes:
- `0` when compatibility passes
- non-zero when a migrated tool becomes less safe or a required migrated tool is missing

### `taskframe tools scaffold <toolpack_id>`

Generates a new tool pack scaffold.

- `--namespace <namespace>` — tool namespace (defaults to toolpack_id)
- `--tool <action>` — tool action name (defaults to `run`)
- `--safe-read` — generate a safe read-only tool (default)
- `--side-effect` — generate a side-effect tool that requires approval
- `--output-dir tool_packs` — output directory
- `--force` — overwrite existing scaffold
- `--json`

Exit codes:
- `0` when scaffold is created
- non-zero when the pack ID is invalid or the directory exists without `--force`

### `taskframe tools test <toolpack_path>`

Runs contract tests for a tool pack.

- `--runtime-data-dir runtime_data`
- `--no-manifest-smoke` — skip example manifest smoke runs
- `--json`

Exit codes:
- `0` when all contract checks pass
- non-zero when any check fails

Checks: descriptor valid, imports, tool smoke call, result shape, safety policy, health check, manifest smoke.

### `taskframe tools examples <toolpack_path>`

Prints example manifest step commands for each tool in a pack.

- `--json`

Exit codes:
- `0` on success

### `taskframe tools policy [toolpack_id]`

Shows the governance policy for a single tool pack, or all packs if no ID is given.

- `--json`

Exit codes:
- `0` on success

### `taskframe tools enable <toolpack_id>`

Records a governance decision to enable a tool pack in specified environments.

- `--classification <cls>` — required; one of: `core`, `optional`, `experimental`, `high_risk`, `blocked`
- `--env <envs>` — comma-separated environments (default: `dev,test`)
- `--by <name>` — who is enabling the pack (default: `operator`)
- `--reason <text>` — reason for enablement
- `--json`

Exit codes:
- `0` on success
- non-zero if classification or environments are invalid

### `taskframe tools disable <toolpack_id>`

Records a governance decision to disable a tool pack in specified or all environments.

- `--env <envs>` — comma-separated environments to disable (omit to disable in all)
- `--by <name>` — who is disabling the pack
- `--reason <text>` — reason for disabling
- `--json`

Exit codes:
- `0` on success

### `taskframe tools governance-report`

Generates a governance report listing all tool packs by classification and environment, and flags any policy violations.

- `--json`

Exit codes:
- `0` when no violations are found
- non-zero when policy violations exist

### `taskframe profile show`

Shows the active runtime profile, its source, and the safety posture used by the tool runner.

- `--profile <name>` - explicit override for inspection
- `--config-dir <path>` - directory containing `runtime_profile.json`
- `--runtime-data-dir <path>`
- `--json`

### `taskframe profile list`

Lists the built-in runtime profiles and their safety characteristics.

- `--json`

### `taskframe profile check`

Checks the active runtime profile for policy blockers and release-safety boundaries.

- `--profile <name>` - explicit override for inspection
- `--config-dir <path>` - directory containing `runtime_profile.json`
- `--runtime-data-dir <path>`
- `--json`

### `taskframe runtime-store check`

Validates the runtime store layout and reports corrupted or orphaned artifacts without deleting anything.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--json`

### `taskframe runtime-store index`

Rebuilds the runtime store index from the current artifacts.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--json`

### `taskframe runtime-store backup`

Creates a zip backup under `runtime_data/backups/` with a backup manifest.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--json`

### `taskframe runtime-store restore`

Validates and extracts a backup into a separate target folder. It never overwrites active `runtime_data`.

- `--backup <path>`
- `--target <path>`
- `--validate-only`
- `--manifest-dir <path>`
- `--json`

### `taskframe runtime-store retention-plan`

Builds a dry-run retention plan for derived runtime-store artifacts.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--json`

### `taskframe runtime-store cleanup`

Runs the retention workflow in dry-run mode only. Destructive cleanup is not enabled here.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--dry-run`
- `--json`

### `taskframe monitor summary`

Shows the operational health summary for indexed runs.

- `--runtime-data-dir <path>`
- `--profile <name>`
- `--limit <n>`
- `--rebuild`
- `--json`

### `taskframe monitor failed`

Lists failed runs from the monitoring index.

- `--runtime-data-dir <path>`
- `--profile <name>`
- `--limit <n>`
- `--rebuild`
- `--json`

### `taskframe monitor pending`

Lists pending approval and waiting runs from the monitoring index.

### `taskframe monitor stuck`

Lists stale `RUNNING` frames from the monitoring index.

### `taskframe monitor blocked`

Lists blocked runs caused by external auth, dependency, or profile-policy issues.

### `taskframe monitor tools`

Shows aggregated tool-health status without live side effects.

### `taskframe monitor report`

Writes JSON, Markdown, and HTML operational-health reports under `runtime_data/monitoring/`.

- `--runtime-data-dir <path>`
- `--profile <name>`
- `--limit <n>`
- `--rebuild`
- `--json`

### `taskframe recover assess`

Assesses whether a failed, interrupted, or stale TaskFrame is retryable or resumable.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--profile <name>`
- `--dry-run`
- `--json`

### `taskframe recover retry-step`

Assesses a single failed step for safe retry. This command stays dry-run by default.

- `--step <step_id>`
- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--profile <name>`
- `--dry-run`
- `--json`

### `taskframe recover resume`

Assesses whether a TaskFrame can resume from the last safe point. This command stays dry-run by default.

- `--runtime-data-dir <path>`
- `--manifest-dir <path>`
- `--profile <name>`
- `--dry-run`
- `--json`

### `taskframe runtime profile`

Legacy alias for profile inspection. Prefer `taskframe profile show`.

- `--json`

### `taskframe runtime governance-check <tool_key>`

Evaluates runtime governance for a tool key such as `customer/read` or `gmail/search`.

- `--env <demo|dev|test|release|pilot|live>`
- `--dry-run`
- `--live-requested`
- `--operation <name>`
- `--json`

### `taskframe safety-pack`

Builds the safety verification pack and live-blocked evidence report.

- `--runtime-data-dir runtime_data`
- `--manifest-dir manifests`
- `--no-demo` — use static analysis only, skip demo scenario runs
- `--output-dir <dir>` — override output directory
- `--json`

Exit codes:
- `0` when all safety claims PASS
- non-zero when any claim fails

Output files:
- `runtime_data/safety_verification/safety_verification_pack.json`
- `runtime_data/safety_verification/safety_verification_pack.md`
- `runtime_data/safety_verification/live_blocked_evidence.json`
- `runtime_data/safety_verification/live_blocked_evidence.md`
- `docs/safety_verification_pack.md`
- `docs/live_blocked_evidence_report.md`

---

## Optional RPA commands

### `taskframe rpa status`

Shows optional RPA tool status without running any live probe or browser check.

Prints:

- whether optional RPA is enabled or disabled
- whether Playwright is installed
- the active profile
- whether a live probe has run

Exit codes:
- `0` always

### `taskframe rpa health`

Checks optional RPA tool health. Default behaviour is to report RPA as disabled with no live probe.

- `--enable-rpa` — enable dependency and config checks (Playwright, package, profile)
- `--live-probe` — run a live browser probe (requires `--enable-rpa`)

Exit codes:
- `0` in default (disabled) mode
- `0` with `--enable-rpa` when all dependencies are present
- `1` with `--enable-rpa` when dependencies are missing
- `1` when `--live-probe` is supplied without `--enable-rpa`

Usage:

```bash
taskframe rpa health                               # Disabled (default)
taskframe rpa health --enable-rpa                  # Dependency checks only
taskframe rpa health --enable-rpa --live-probe     # Full live probe (local setup required)
taskframe rpa health --live-probe                  # ERROR: requires --enable-rpa
```

### `taskframe rpa docs`

Prints the path to `docs/optional_rpa.md` and a short summary.

Exit codes:
- `0`


## Durable Event Queue (`taskframe queue`)

Manage and inspect the Spec 137 durable event queue.

### `taskframe queue status`

Show queue health: backend, counts by status, oldest pending item.

```bash
taskframe queue status
taskframe queue status --json
```

### `taskframe queue list`

List durable queue records, optionally filtered by status.

```bash
taskframe queue list
taskframe queue list --status PENDING
taskframe queue list --status FAILED_RETRYABLE --limit 20 --json
```

### `taskframe queue enqueue-fixture <fixture_name>`

Enqueue a safe local fixture event. Available fixtures: `customer_status`, `order_status`, `system_health`.

```bash
taskframe queue enqueue-fixture customer_status
```

### `taskframe queue process-next`

Claim and process one PENDING item into a TaskFrame (dry-run only).

```bash
taskframe queue process-next
taskframe queue process-next --worker-id my-worker --json
```

### `taskframe queue process-batch`

Process up to `--limit` PENDING items.

```bash
taskframe queue process-batch --limit 10
```

### `taskframe queue retry <queue_id>`

Re-queue a `FAILED_RETRYABLE` item back to `PENDING`.

```bash
taskframe queue retry abc123...
```

### `taskframe queue cancel <queue_id>`

Cancel a non-terminal queue item.

```bash
taskframe queue cancel abc123... --reason "Stale test fixture"
```

### `taskframe queue dead-letter`

List all `DEAD_LETTER` items.

```bash
taskframe queue dead-letter
taskframe queue dead-letter --json
```

### `taskframe queue recover-stale`

Recover stale `CLAIMED`/`PROCESSING` items (older than `--stale-timeout-minutes`, default 15).

```bash
taskframe queue recover-stale
taskframe queue recover-stale --stale-timeout-minutes 30
```

---

## Google Workspace tool pack

- `taskframe tools discover`
- `taskframe tools list`
- `taskframe tools inspect gmail/list_unread`
- `taskframe tools inspect toolpack:google_workspace`
- `taskframe tools validate tool_packs/google_workspace/toolpack.json`
- `taskframe tools health google_workspace`
- `taskframe tools lifecycle tool_packs/demo_echo/toolpack.json --env dev`

The tool pack is optional and read-only. Default demo paths do not require Google credentials.

---

## Event Source Polling (Spec 139)

```bash
taskframe event-sources status
taskframe event-sources list-sources
taskframe event-sources show-source <source_id>
taskframe event-sources health-check <source_id>
taskframe event-sources create-fixture <source_id>
taskframe event-sources poll <source_id>
taskframe event-sources poll-enabled --limit 10
taskframe event-sources enable <source_id>
taskframe event-sources disable <source_id>
taskframe event-sources history --limit 20
```

See [docs/external_event_source_polling.md](external_event_source_polling.md) for the full guide.
