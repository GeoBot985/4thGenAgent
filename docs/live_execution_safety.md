# Live Execution Safety

TaskFrame defaults to dry-run execution.

Live execution is intentionally hard to trigger. It requires all of the following:

- `TASKFRAME_ENABLE_LIVE_EXECUTION=1`
- an approved pending action
- a TaskFrame in `WAITING_FOR_EXECUTE` or `EXECUTING_PENDING`
- manifest opt-in for live execution
- the manifest allowing the exact tool
- a tool spec that allows live side effects
- a passing live guardrail
- relevant tool health that is not failing
- typed confirmation that exactly matches the generated confirmation phrase

## Default behaviour

The default portfolio demo does not perform live side effects.

Dry-run is the normal path for both the operator UI and the CLI.
Optional RPA remains outside the default path and is governed by its own explicit safety checks.
Runtime profile separation is part of that default safety boundary:

- `demo` stays fixture-backed and dry-run by default
- `pilot` is the controlled live-read profile, with allowlisted read-only tools only
- `live` remains reserved and does not enable live side effects

Recovery stays dry-run by default as well. Retry and resume assessments are operator-reviewed controls, not automatic self-healing paths.

## CLI guardrails

Use these commands to inspect safety before attempting any execution:

```bash
taskframe safety-status
taskframe pending-actions
taskframe live-preflight --frame-id <frame_id> --action-id <action_id>
taskframe execute-approved --frame-id <frame_id> --action-id <action_id> --dry-run
```

The live form is still guarded:

```bash
taskframe execute-approved \
  --frame-id <frame_id> \
  --action-id <action_id> \
  --live \
  --i-understand-live-side-effects \
  --confirm "EXECUTE LIVE <frame_id> <action_id>"
```

`--live` alone is not sufficient.

## Example live preflight output

```text
Frame: frame_123
Action: pa_456
Tool: sheet/write
Status: LIVE_READY_REQUIRES_CONFIRMATION
Severity: warning
Guardrail: sheet_write | ok=true
Confirmation: EXECUTE LIVE frame_123 pa_456
Safe option: taskframe execute-approved --frame-id frame_123 --action-id pa_456 --dry-run
```

## Dry-run execution

Dry-run execution stays available even when live execution is blocked.

```bash
taskframe execute-approved --frame-id <frame_id> --action-id <action_id> --dry-run
```

## Example blocked output

```text
LIVE EXECUTION BLOCKED
Frame: frame_123
Action: pa_456
Tool: sheet/write
Status: LIVE_BLOCKED

Blockers:
- runtime_live_mode_disabled: TASKFRAME_ENABLE_LIVE_EXECUTION is not enabled.
- tool_not_live_allowed: Tool does not allow live side effects.

Safe option:
taskframe execute-approved --frame-id frame_123 --action-id pa_456 --dry-run
```

## Why this matters

The live boundary is the controlled side-effect edge. It must remain visible, auditable, and difficult to bypass.

## Spec 132 — Live side-effect execution contract

Spec 132 formalises the common execution rules that all future live-write tools must obey. It does not add specific live tools yet.

The contract adds:

- A formal `live_side_effect_execution` policy object (disabled by default)
- Ten explicit preflight checks with named error codes
- Extended manifest live allowlist fields (`allowed_actions`, `max_live_actions`, `requires_operator_confirmation`)
- Pending action live fields (`live_capable`, `live_executed`, `live_executed_at`, `dry_run_executed`, `guardrail_result`)
- `LIVE-EXECUTE` typed confirmation requirement for the CLI
- Idempotency key presence and duplicate-key checks
- Audit events `LIVE_SIDE_EFFECT_EXECUTED` / `LIVE_SIDE_EFFECT_BLOCKED`
- JSON and Markdown execution reports under `runtime_data/live_execution/`

See [live_side_effect_execution_contract.md](live_side_effect_execution_contract.md) for full details.

## Spec 133 — Approved live Gmail send tool

Spec 133 implements the first narrow live side-effect tool: `gmail/send`. It builds on Spec 132.

Key constraints:

- `demo`, `dev`, `test`, `release`, and `pilot` profiles never allow live Gmail sends.
- Gmail sending is disabled by default (`enabled: false` in the config).
- The email body is never written to reports or audit logs.
- All Spec 132 preflight checks plus the `gmail_send` guardrail must pass before any email is sent.
- No automatic sending, no unapproved sends, no attachments unless config explicitly allows them.

See [live_gmail_send.md](live_gmail_send.md) for the full Spec 133 documentation.

## Spec 134 — Approved live Google Sheets write tool

Spec 134 implements the second narrow live side-effect tool: `sheet/write_rows`. It follows the same safety pattern as Spec 133.

Key constraints:

- `demo`, `dev`, `test`, `release`, and `pilot` profiles never allow live Sheets writes.
- Sheets writing is disabled by default (`enabled: false` in the config).
- Row payloads are never written to summary reports or audit logs.
- All Spec 132 preflight checks plus the `sheet_write_rows_guardrail` must pass before any write is made.
- Spreadsheet ID and range/tab allowlists are mandatory.
- `append` mode is the preferred safe mode. `update` mode is disabled by default.
- No automatic writes, no unapproved writes, no spreadsheet mutations without an explicit allowlist.

See [live_google_sheets_write.md](live_google_sheets_write.md) for the full Spec 134 documentation.
