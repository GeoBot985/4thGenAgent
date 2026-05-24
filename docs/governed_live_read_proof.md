# Governed Live Read Proof

## Purpose

The governed live-read proof pack (Spec 154) proves that TaskFrame can perform controlled live read-only integration checks without allowing live writes, sends, deletes, browser RPA, or side effects.

This moves the project from "live-read capable in theory" to evidence-backed governed live-read proof.

---

## What Controlled Live Read Means

**Controlled live read** means:

- Live reads of external Google Workspace data (Gmail search, Calendar search, Sheets read) are **explicitly enabled** via the `controlled_live_read` profile.
- Only **allowlisted read-only tools** (`google_workspace_readonly` pack) may run.
- All **write, send, delete, mutation, and side-effect** tools remain blocked.
- **RPA** remains blocked.
- **Credentials are detected but never logged** (tokens and secrets are redacted).

Controlled live read is **not** live automation. It reads external data safely, within a governed boundary.

---

## How It Differs from Live Side Effects

| Feature | Controlled Live Read | Live Side Effect |
|---|---|---|
| Gmail search | ✅ Allowed | N/A |
| Gmail send | ❌ Blocked | Only with full guardrails |
| Calendar read | ✅ Allowed | N/A |
| Calendar create/update/delete | ❌ Blocked | Only with full guardrails |
| Sheets read | ✅ Allowed | N/A |
| Sheets write | ❌ Blocked | Only with full guardrails |
| RPA | ❌ Blocked | ❌ Blocked |
| Credentials required | Optional | Required |
| Release verification safe | ✅ Yes (boundary-only mode) | Separate gate |

---

## Profile

```json
{
  "profile": "controlled_live_read",
  "allow_live_reads": true,
  "allow_live_side_effects": false,
  "require_tool_governance": true,
  "allowed_toolpacks": ["google_workspace_readonly"],
  "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"]
}
```

---

## Proof Pack Modes

### Boundary-Only Proof (no credentials required)

Validates configuration, profile, and tool boundaries without any external API calls.

```bash
python -m src.taskframe_cli live-read proof \
  --profile controlled_live_read \
  --no-live-probes \
  --write-report \
  --json
```

This mode:
- Validates the profile is correctly configured.
- Confirms all side-effect tools are blocked at policy level.
- Confirms RPA is blocked.
- Does **not** call any external API.
- Does **not** require credentials.
- Is safe for release verification.

### Live Probe Mode (requires Google credentials)

Runs real read-only probes against Google Workspace APIs.

```bash
python -m src.taskframe_cli live-read proof \
  --profile controlled_live_read \
  --write-report \
  --json
```

This mode:
- Checks auth/token availability.
- Performs a Gmail metadata search (no email body access).
- Performs a Calendar search.
- Reads a Sheets range.
- Redacts all tokens and secrets from evidence.
- Confirms that no side effects occurred.

---

## CLI Commands

### Status (safe, no API calls)

```bash
python -m src.taskframe_cli live-read status --profile controlled_live_read --json
```

Returns:
- Profile configuration
- Credential status (`needs_auth`, `token_missing`, `token_expired`, `ready`)
- Whether a latest proof report is available
- Allowed read tools and blocked side-effect tools

### Proof

```bash
python -m src.taskframe_cli live-read proof \
  --profile controlled_live_read \
  --no-live-probes \
  --write-report \
  --json
```

Options:
- `--no-live-probes`: boundary-only, no API calls (default for release verification)
- `--write-report`: write JSON and Markdown reports to `runtime_data/live_read_proof/`
- `--spreadsheet-range RANGE`: Sheets range to read (default: `Sheet1!A1:D10`)
- `--gmail-query QUERY`: Gmail search query (default: `in:inbox`)
- `--calendar-query QUERY`: Calendar search query (default: `upcoming`)

### Blocked Side-Effects Check

```bash
python -m src.taskframe_cli live-read blocked-side-effects \
  --profile controlled_live_read \
  --json
```

Proves send/write/delete/RPA tools are blocked at policy level. Does **not** call real external APIs.

---

## Proof Pack Result Shape

```json
{
  "ok": true,
  "profile": "controlled_live_read",
  "live_reads_attempted": false,
  "live_side_effects_performed": false,
  "credentials_present": false,
  "token_present": false,
  "probes": [],
  "blocked_side_effect_checks": [],
  "rpa_blocked": true,
  "blockers": [],
  "warnings": [],
  "report_paths": {}
}
```

### Probe Shape

```json
{
  "probe_id": "gmail_search_readonly",
  "tool": "gmail/search",
  "status": "PASS|FAIL|SKIPPED|BLOCKED",
  "live_external_call": true,
  "side_effect": false,
  "records_seen": 0,
  "evidence": {},
  "error": "",
  "warnings": []
}
```

---

## Required Credentials

Live probe mode requires:

- `credentials.json` — OAuth2 client credentials file from Google Cloud Console
- `token.json` — Valid OAuth2 token with read-only scopes

Boundary-only proof mode requires **no credentials**.

Credential paths searched (in order):
1. `credentials.json` (project root)
2. `config/credentials.json`
3. `GOOGLE_APPLICATION_CREDENTIALS` environment variable
4. `token.json` (project root)
5. `config/token.json`

---

## Blocked Side-Effect Proof

The blocked side-effect check proves that these tools are blocked at the policy/preflight level. No real external API call is made.

| Tool | Expected Status |
|---|---|
| `gmail/send` | BLOCKED |
| `calendar/create` | BLOCKED |
| `calendar/update` | BLOCKED |
| `calendar/delete` | BLOCKED |
| `sheet/write` | BLOCKED |
| `sheet/write_rows` | BLOCKED |
| `rpa/run` | BLOCKED |
| `rpa/click` | BLOCKED |
| `rpa/type` | BLOCKED |
| `rpa/navigate` | BLOCKED |

---

## Evidence Reports

Reports are written to `runtime_data/live_read_proof/`:

- `live_read_proof_latest.json` — Full proof pack result (redacted)
- `live_read_proof_latest.md` — Human-readable Markdown report
- `blocked_side_effects_latest.json` — Blocked tool evidence
- `blocked_side_effects_latest.md` — Blocked tool Markdown report

---

## Release Verification

The release verifier includes `governed_live_read_proof` as a standard check. It runs boundary-only mode with `--no-live-probes`, which:

- Requires no Google credentials.
- Confirms the profile is correctly configured.
- Confirms side-effect tools are blocked.
- Confirms RPA is blocked.
- Confirms reports can be written.
- Introduces no live side effects.

---

## Safety Statement

> Controlled live reads were allowed only for allowlisted read-only tools.
> No live side effects were performed.
> All write/send/delete/RPA paths remained blocked.

---

## See Also

- [live_read_redaction.md](live_read_redaction.md) — Redaction rules
- [controlled_live_profile.md](controlled_live_profile.md) — Profile definition
- [google_workspace_readonly_toolpack.md](google_workspace_readonly_toolpack.md) — Read-only toolpack
- [cli_reference.md](cli_reference.md) — Full CLI reference
