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

- `--scenario <scenario_id>`
- `--runtime-data-dir runtime_data`
- `--reset-dataset`
- `--report`
- `--local-llm`
- `--json`

Exit codes:
- `0` when the scenario completes successfully
- non-zero on scenario failure

### `taskframe golden-demo`

Runs the golden demo verification.

Exit codes:
- `0` when the golden demo passes
- non-zero when it fails

### `taskframe verify`

Runs release verification.

- `--full`
- `--quick` placeholder; the current implementation runs the full verification set

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

### `taskframe runtime profile`

Shows the resolved runtime environment and governance profile used by the tool runner.

- `--json`

### `taskframe runtime governance-check <tool_key>`

Evaluates runtime governance for a tool key such as `customer/read` or `gmail/search`.

- `--env <demo|dev|test|release|live>`
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


## Google Workspace tool pack

- `taskframe tools discover`
- `taskframe tools list`
- `taskframe tools inspect gmail/list_unread`
- `taskframe tools inspect toolpack:google_workspace`
- `taskframe tools validate tool_packs/google_workspace/toolpack.json`
- `taskframe tools health google_workspace`
- `taskframe tools lifecycle tool_packs/demo_echo/toolpack.json --env dev`

The tool pack is optional and read-only. Default demo paths do not require Google credentials.
