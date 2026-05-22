# Scheduler Runtime (Spec 138)

The scheduler subsystem creates standard events from time-based or interval-based schedules and feeds them into the Spec 137 durable event queue.

## Overview

- Schedules are stored as canonical records in `runtime_data/scheduler/schedules_index.json` (filesystem) or in the `schedules` SQLite table.
- On each tick, the engine finds enabled schedules whose next fire time has passed, generates a standard event, and enqueues it via `enqueue_event`.
- All ticks are **dry-run by default** — no live side effects.

## Schedule Types

| Type | Description | Required Fields |
|---|---|---|
| `daily` | Fires once per day at `time_of_day` | `time_of_day` (HH:MM or HH:MM:SS) |
| `interval` | Fires every N minutes | `interval_minutes` > 0 |
| `weekly` | Fires on a specific weekday at `time_of_day` | `time_of_day`, `day_of_week` |
| `cron` | Reserved for future use | — |

## Misfire Policies

| Policy | Behaviour when behind |
|---|---|
| `skip` | Fire only the latest missed window; discard the rest |
| `enqueue_latest` | Enqueue only the most recent missed window |
| `enqueue_all` | Enqueue all missed windows, up to `max_catchup_windows` |

## CLI

```bash
taskframe schedule status           # Show scheduler panel
taskframe schedule list             # List all schedules
taskframe schedule list --enabled-only
taskframe schedule enable <id>
taskframe schedule disable <id>
taskframe schedule tick             # Run one tick (always dry-run)
taskframe schedule load-fixture <path>
taskframe schedule runs             # List recent run records
taskframe schedule runs --schedule-id <id>
```

## Fixture Files

Three sample fixtures are provided under `runtime_data/fixtures/schedules/`:

- `daily_low_stock_check.json` — daily stock check at 06:00 UTC (enabled)
- `daily_accounting_summary.json` — daily accounting summary at 17:30 UTC (disabled)
- `delayed_order_detection.json` — 60-minute interval order scan (enabled)

Load a fixture with:
```bash
taskframe schedule load-fixture runtime_data/fixtures/schedules/daily_low_stock_check.json
```

## Persistence

Schedules and run records are stored in:

- **Filesystem**: `runtime_data/scheduler/schedules_index.json` and `runtime_data/scheduler/schedule_runs.jsonl`
- **SQLite**: `schedules` and `schedule_runs` tables (schema v3)

## Key Modules

| Module | Purpose |
|---|---|
| `runtime/scheduler_contract.py` | Constants, record builders, validation |
| `runtime/scheduler_store.py` | CRUD: create, get, list, enable, disable, delete |
| `runtime/scheduler_engine.py` | Due calculation, missed windows, tick execution |
| `src/operator_scheduler_panel.py` | Read-only operator summary |

## Deduplification

Each scheduled event has a deterministic `event_id` of the form `evt_sched_{schedule_id}_{yyyymmddTHHMMSS}`. The durable queue's `build_dedupe_key` uses `source=schedule`, `event_type`, and `payload.scheduled_for` to produce a stable SHA-256 dedupe key — so re-enqueuing the same window is idempotent.

## Integration with Event Source Polling (Spec 139)

To trigger bounded event source polling on a schedule, use the CLI wrapper command in a schedule payload:

```bash
taskframe event-sources poll-enabled --limit 10
```

This may be called from a schedule's command target. See [docs/external_event_source_polling.md](external_event_source_polling.md) for the full event source polling guide.
