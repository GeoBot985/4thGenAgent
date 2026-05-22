# Configuration and Secrets

## Overview

TaskFrame uses a safe default configuration for the demo path. You can run the project without Google credentials, browser profiles, Ollama, or live integrations.

Configuration is profile-based. Profiles change where settings are read from; they do not automatically enable live side effects.

Runtime profiles are separate from config profiles. The runtime profile controls execution safety and tool access, and it defaults to the safe `demo` profile.

Runtime profile resolution order:

1. explicit CLI argument
2. environment variable
3. user config file
4. safe internal default (`demo`)

## Persistence Backends

TaskFrame uses filesystem JSON persistence by default. This keeps portfolio/demo runs easy to inspect and preserves evidence artifacts under `runtime_data/runs/<frame_id>/`.

SQLite can be enabled for production-shaped operational state:

```powershell
$env:TASKFRAME_PERSISTENCE_BACKEND="sqlite"
$env:TASKFRAME_SQLITE_DB_PATH="runtime_data/taskframe_runtime.db"
```

In SQLite mode the runtime dual-writes: SQLite stores operational state, while JSON artifacts, reports, screenshots, evidence bundles, and exported markdown/html files remain file-based. Do not store credentials, OAuth tokens, raw secrets, private local config contents, live confirmation phrases, or raw browser profile paths in SQLite.

See `config/examples/taskframe.sqlite.example.json` and `docs/production_persistence_backend.md`.

## Safe default configuration

The default profile uses:

- fake/deterministic LLM mode
- Google integrations disabled
- RPA disabled
- live execution disabled
- local runtime data paths

This is the right choice for first-time setup and public demos.

## Runtime profiles

Available runtime profiles:

- `demo` - safe portfolio/demo mode using fixtures and dry-run behavior
- `dev` - local development with relaxed diagnostics and no live side effects by default
- `test` - deterministic fixture-backed automated test mode
- `release` - strict release-verification mode
- `pilot` - controlled live-read mode with explicit allowlists
- `live` - reserved future profile, blocked unless explicitly enabled by a future override

The runtime profile does not enable live side effects by default. `pilot` may allow governed live reads for allowlisted read-only tools only.

Use `taskframe profile show`, `taskframe profile list`, and `taskframe profile check` to inspect the active runtime profile.

## Config profiles

Available profiles:

- `default` — safe local dry-run path
- `dev` — local development profile
- `local-llm` — use local Ollama if available
- `google-live` — enable Google config lookup only
- `rpa-local` — enable local browser/RPA config lookup only

Profiles do not override approval policy or live-execution rules.

## Where config files live

Lookup order:

1. explicit CLI argument
2. `TASKFRAME_CONFIG_DIR`
3. user config directory: `~/.taskframe/`
4. repo examples under `config/examples/`

Runtime data defaults to `runtime_data/` unless `TASKFRAME_RUNTIME_DIR` or a CLI override is supplied.

The runtime store is organized as a documented artifact layout under `runtime_data/`:

- `taskframes/`
- `reports/`
- `approval_packs/`
- `evidence/`
- `tool_health/`
- `indexes/`
- `backups/`
- `cleanup/`
- `migrations/`

`taskframe runtime-store check` validates that layout and reports corrupted or orphaned artifacts. `taskframe runtime-store backup` writes a zip archive into `runtime_data/backups/`, and `taskframe runtime-store restore` only extracts into a separate target directory.

Operational monitoring is layered on top of the runtime store and is read-only. Use `taskframe monitor summary`, `taskframe monitor failed`, `taskframe monitor pending`, `taskframe monitor stuck`, `taskframe monitor blocked`, `taskframe monitor tools`, and `taskframe monitor report` to inspect run health without changing execution state.

Pending actions and live-related artifacts are protected by default so demo and pilot runs cannot be cleaned away accidentally.

## Environment variables

Supported variables:

- `TASKFRAME_CONFIG_DIR`
- `TASKFRAME_PROFILE`
- `TASKFRAME_ENV` - legacy alias for runtime profile resolution
- `TASKFRAME_RUNTIME_DIR`
- `TASKFRAME_LLM_PROVIDER`
- `TASKFRAME_OLLAMA_MODEL`
- `TASKFRAME_OLLAMA_BASE_URL`
- `TASKFRAME_ACCOUNTING_SHEET_CONFIG`
- `ENABLE_OPTIONAL_RPA_TOOLS`
- `TASKFRAME_BACKEND_AUTH_CONFIG_PATH`
- `TASKFRAME_BACKEND_AUTH_ENABLED`
- `TASKFRAME_BACKEND_ALLOW_DEV_BYPASS`
- `TASKFRAME_BACKEND_ADMIN_TOKEN`
- `TASKFRAME_BACKEND_OPERATOR_TOKEN`
- `TASKFRAME_BACKEND_VIEWER_TOKEN`

CLI arguments win over environment variables.
If `taskframe profile show` reports the wrong runtime profile, check `TASKFRAME_PROFILE`, `TASKFRAME_ENV`, and `config/runtime_profile.json`.

## Production backend auth

The production backend uses static bearer tokens loaded from environment variables or a JSON config file. Keep the token values out of source control.

Example:

```powershell
$env:TASKFRAME_BACKEND_AUTH_ENABLED="true"
$env:TASKFRAME_BACKEND_ALLOW_DEV_BYPASS="false"
$env:TASKFRAME_BACKEND_ADMIN_TOKEN="..."
$env:TASKFRAME_BACKEND_OPERATOR_TOKEN="..."
$env:TASKFRAME_BACKEND_VIEWER_TOKEN="..."
```

You can also point the app at a config file with `TASKFRAME_BACKEND_AUTH_CONFIG_PATH` or pass `backend_auth_config_path` to `create_app()`. The example config is `config/examples/taskframe.backend.example.json`.

Roles:

- `viewer` for read-only inspection
- `operator` for event intake and pending-action approval/rejection
- `admin` for all backend routes, still subject to runtime live-execution guardrails

Dev bypass is unsafe outside local development. It should only be used when auth is explicitly disabled and bypass is explicitly enabled.

## Google integration config

Google credentials should live under user-local config, for example:

- `~/.taskframe/google/credentials.json`
- `~/.taskframe/google/google_token.json`

The repository root is not the preferred place for credentials. If legacy files still exist locally, treat them as transitional and keep them out of Git.

## Accounting sheet config

The accounting sheet config should live at:

- `~/.taskframe/accounting_google_sheet.json`

A repository example file is provided at:

- `config/examples/accounting_google_sheet.example.json`

## Optional RPA config

RPA/browser profiles are optional and high-risk. Keep them local and user-specific. Do not commit browser session state or profile directories.

### RPA local profile

The `rpa-local` profile enables optional RPA config lookup. It does not automatically launch browser tools or run live probes.

To use it:

```bash
TASKFRAME_PROFILE=rpa-local taskframe rpa health --enable-rpa
```

Or set it in `~/.taskframe/taskframe.rpa-local.json`.

An example profile is available at `config/examples/taskframe.rpa-local.example.json`.

RPA config must stay in user-local config only:

- browser profile paths
- session directories
- authentication state

**Never commit RPA config, browser session files, or profile directories to the repository.**

## Local Ollama config

For a local LLM profile, use:

- `TASKFRAME_LLM_PROVIDER=ollama`
- `TASKFRAME_OLLAMA_MODEL=<your-model>`
- `TASKFRAME_OLLAMA_BASE_URL=http://127.0.0.1:11434`

The default profile still uses fake/deterministic mode.

## What not to commit

Do not commit:

- credentials
- tokens
- browser profiles
- local config files
- runtime outputs

The repository `.gitignore` excludes the common secret and local-config patterns.

## Troubleshooting

- If `taskframe config show` reports the wrong profile, check `TASKFRAME_PROFILE`.
- If Google checks are failing, confirm the credential files exist under `~/.taskframe/google/`.
- If Ollama is unavailable, switch back to the default fake provider.
- If a local config file is not being read, check `TASKFRAME_CONFIG_DIR`.

Use `taskframe config paths` to inspect the lookup order and active config file path.
