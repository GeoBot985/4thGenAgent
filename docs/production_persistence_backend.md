# Production Persistence Backend

Spec 136 introduces a persistence boundary behind the TaskFrame runtime. Filesystem JSON remains the default because it is transparent, easy to inspect, and still ideal for portfolio demos, evidence packs, screenshots, and exported reports.

SQLite is the first production-shaped backend. It gives the runtime transactional operational state without changing manifest execution, orchestrator state transitions, approval rules, or live side-effect guardrails.

## Backend Selection

Default mode:

```powershell
$env:TASKFRAME_PERSISTENCE_BACKEND="filesystem"
```

SQLite mode:

```powershell
$env:TASKFRAME_PERSISTENCE_BACKEND="sqlite"
$env:TASKFRAME_SQLITE_DB_PATH="runtime_data/taskframe_runtime.db"
```

If `TASKFRAME_SQLITE_DB_PATH` is not set, SQLite uses `runtime_data/taskframe_runtime.db`.

## Dual Write

When SQLite is active, operational records are written to SQLite and JSON artifacts are still written under `runtime_data/runs/<frame_id>/`. Existing reports, evidence bundles, summaries, and operator inspection flows can continue to read file artifacts.

## CLI

```powershell
python -m src.taskframe_cli persistence status
python -m src.taskframe_cli persistence init
python -m src.taskframe_cli persistence migrate-json
python -m src.taskframe_cli persistence verify
```

`migrate-json` backfills readable JSON artifacts into SQLite and skips malformed artifacts with warnings. It is idempotent for TaskFrames, events, queue records, and migrated run ledger rows.

## Schema Summary

SQLite stores JSON payloads plus indexed fields in these tables: `taskframes`, `events`, `event_queue`, `durable_event_queue`, `run_ledger`, `audit_events`, `pending_actions`, `executed_actions`, `tool_calls`, `llm_calls`, `validations`, `event_sources`, `event_source_state`, and `event_source_history`. The `event_sources` tables (Spec 139) store event source configs, per-source polling state, and polling history.

Schema version 2 adds the `durable_event_queue` table (Spec 137) with columns `queue_id`, `event_id`, `source`, `event_type`, `status`, `priority`, `attempt_count`, `max_attempts`, `available_at`, `claimed_at`, `claimed_by`, `completed_at`, `linked_frame_id`, `dedupe_key`, `last_error`, `failure_category`, `created_at`, `updated_at`, and `payload_json`. Indexes cover status + priority ordering, dedupe lookups, and event_id joins.

## Safety Boundary

The SQLite backend must not store credentials, OAuth tokens, raw secret values, private local config contents, live confirmation phrases, or raw browser profile paths. Sensitive keys are redacted before SQLite writes. Reports and generated markdown/html artifacts remain file-based.

## Limitations

This is not a PostgreSQL backend and does not migrate business fixture data. Generated reports, screenshots, exported evidence bundles, and markdown/html artifacts remain on disk.

## Future PostgreSQL Path

The backend contract is intentionally narrow: TaskFrames, events, queue records, run ledger records, actions, calls, validations, and health. PostgreSQL can later implement the same contract with stronger concurrency and deployment options.
