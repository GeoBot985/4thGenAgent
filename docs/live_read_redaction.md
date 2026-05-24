# Live Read Redaction

## Purpose

All evidence produced by the governed live-read proof pack (Spec 154) is redacted before being written to disk or returned in API responses. This ensures that credentials, tokens, OAuth secrets, and sensitive content are never exposed in reports.

---

## What Is Redacted

The following fields are always replaced with `[REDACTED]` in proof pack output:

| Field | Reason |
|---|---|
| `access_token` | OAuth2 access token — grants live API access |
| `refresh_token` | OAuth2 refresh token — allows token renewal |
| `client_secret` | OAuth2 client secret — identifies the app |
| `client_id` | OAuth2 client ID — redacted as a precaution |
| `token_raw` | Raw token file content |
| `raw_json` | Raw credential JSON content |
| `email_body` | Email body content — not read, but redacted if present |
| `message_body` | Message content |
| `raw_content` | Any raw external content |
| `api_key` | API keys |
| `token` | Generic token fields in probe evidence |

---

## What Is Preserved (Not Redacted)

The following evidence fields are safe to include in reports:

| Field | Preserved |
|---|---|
| `credentials_present` | Whether the credentials file exists (bool) |
| `token_present` | Whether the token file exists (bool) |
| `token_parseable` | Whether the token JSON is valid (bool) |
| `scopes_detected` | Whether OAuth scopes are present (bool) |
| `token_expired` | Whether the token is expired (bool or "unknown") |
| `credentials_path` | File path to credentials (no content) |
| `token_path` | File path to token (no content) |
| `records_returned` | Count of records seen in search |
| `query` | The search query used (not results) |
| `range` | The Sheets range queried |
| `source` | Tool source identifier |
| `operation` | Operation type (e.g., "read_only_search") |
| `mode` | Probe mode (e.g., "metadata_only") |

---

## Redaction Implementation

Redaction is applied in two places:

### 1. Credential Evidence (`redact_credential_evidence`)

Applied to all credential check results before they are included in proof pack output.

```python
from runtime.live_read_proof import redact_credential_evidence

safe_cred = redact_credential_evidence(raw_credential_check)
```

### 2. Full Proof Result (`redact_proof_result`)

Applied to the full proof pack result before writing to disk. Redacts credential fields and probe evidence.

```python
from runtime.live_read_proof import redact_proof_result

safe_result = redact_proof_result(raw_result)
```

---

## Report Safety

All files written to `runtime_data/live_read_proof/` are redacted before writing:

- `live_read_proof_latest.json` — Redacted JSON
- `live_read_proof_latest.md` — Redacted Markdown
- `blocked_side_effects_latest.json` — Contains no credentials
- `blocked_side_effects_latest.md` — Contains no credentials

---

## Credential Detection (Not Logging)

The proof pack checks whether credentials exist and whether the token appears valid, without logging the credential content:

- ✅ Checks whether `credentials.json` exists
- ✅ Checks whether `token.json` exists
- ✅ Checks whether the token JSON is parseable
- ✅ Checks whether OAuth scopes are present
- ✅ Checks whether the token has expired
- ❌ Does NOT log `access_token`
- ❌ Does NOT log `refresh_token`
- ❌ Does NOT log `client_secret`
- ❌ Does NOT log raw credential JSON

---

## Email Content

Email search probes return only metadata (message IDs, thread IDs, labels). Email body content is never retrieved or logged. If body content appears in any evidence dict, it is replaced with `[REDACTED]`.

---

## Why Clean-Clone Release Verification Does Not Require Credentials

The release verifier uses `--no-live-probes` mode, which:

1. Validates the profile configuration without loading credentials.
2. Runs blocked-side-effect checks at the policy level (no external API calls).
3. Writes boundary-only proof reports.
4. Produces `live_side_effects_performed: false` and `rpa_blocked: true` evidence.

No credentials are required or checked in this mode.

---

## See Also

- [governed_live_read_proof.md](governed_live_read_proof.md) — Full proof pack documentation
- [controlled_live_profile.md](controlled_live_profile.md) — Profile definition
