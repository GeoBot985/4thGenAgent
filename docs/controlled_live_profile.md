# Controlled Live Read Profile

## Purpose
The `controlled_live_read` profile enables governed, read-only access to external services (Gmail, Calendar, Sheets) for demonstration and testing purposes. It does not enable production live automation, live writes, or live side effects.

## What Is Allowed
- Gmail search and read
- Calendar search and read
- Sheets read and get_values
- Google Workspace read-only tool pack

## What Is Blocked
- Gmail send and draft send
- Calendar create, update, delete
- Sheets write, write_rows, update
- RPA browser automation (all rpa/* tools)
- Any tool with side_effect=True

## Governance Requirements
- `require_tool_governance: true` — tool governance must pass before any live read is attempted
- Only tools in the `google_workspace_readonly` tool pack are permitted
- Tool pack must be enabled and pass health check

## Credential Requirements
- Google OAuth credentials must be configured at `~/.taskframe/google/credentials.json`
- Google token must exist at `~/.taskframe/google/google_token.json`
- No credentials are required to run the profile status check

## How to Run Preflight

```bash
taskframe profile controlled-live-status
taskframe profile controlled-live-status --check-tools
taskframe profile controlled-live-status --json
```

From the operator UI: use the "Controlled Live Read Status" button in the Live Safety Panel.

## Safety Guarantees
- `allow_live_side_effects: false` — side effects are unconditionally blocked
- All write/send/delete tool calls return `LIVE_SIDE_EFFECT_BLOCKED`
- RPA tools are blocked regardless of credentials or configuration
- Tool governance is enforced before any live read is attempted

## Known Limitations
- This profile allows governed live reads only. It does not allow production live automation or live side effects.
- Real Google credentials are required to use live read tools.
- The profile does not schedule or automate live reads in the background.
