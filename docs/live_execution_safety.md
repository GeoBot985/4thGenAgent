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
