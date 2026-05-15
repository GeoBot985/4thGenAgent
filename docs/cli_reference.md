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

### `taskframe version`

Prints the installed runtime version.

Exit codes:
- `0`

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
