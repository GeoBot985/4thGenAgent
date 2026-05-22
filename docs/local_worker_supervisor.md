# Local Worker Supervisor

**Spec 140 — Local Worker Supervisor + Bounded Runtime Loop v1**

## Purpose

The local worker supervisor coordinates the production runtime surfaces introduced in Specs 136–139:

- Persistence backend (Spec 136)
- Durable event queue (Spec 137)
- Scheduler (Spec 138)
- External event-source polling (Spec 139)

It provides a controlled, bounded runtime cycle that recovers stale queue items, runs the scheduler tick, polls enabled event sources, and processes queued events — all without installing a background service.

## Worker Cycle

Each cycle executes in this exact order:

1. **Load worker config** — resolve worker ID, features, limits, safety settings
2. **Acquire worker lock** — prevent duplicate workers in the same `runtime_data_dir`
3. **Write heartbeat: STARTING** — persist initial state to `runtime_data/worker/state.json`
4. **Recover stale queue items** — re-queue any CLAIMED/PROCESSING items that timed out
5. **Run scheduler tick** — enqueue events for due schedules (always dry-run)
6. **Poll enabled event sources** — call adapters for all enabled sources (bounded by `max_sources_per_cycle`)
7. **Process queue batch** — process up to `max_queue_items_per_cycle` PENDING queue items into TaskFrames
8. **Write cycle summary** — persist structured summary to `runtime_data/worker/cycles.jsonl`
9. **Write heartbeat: IDLE or FAILED** — update `runtime_data/worker/state.json`
10. **Release lock** — remove `runtime_data/worker/worker.lock.json`

## Lock and Heartbeat Model

The worker uses a filesystem lock file to prevent duplicate local workers:

```
runtime_data/worker/worker.lock.json
```

Lock fields: `worker_id`, `pid`, `lock_id`, `acquired_at`, `last_heartbeat_at`.

A lock is considered **stale** if:
- The heartbeat is older than 120 seconds **and**
- The recorded PID is no longer running

A stale lock can be cleared explicitly with `taskframe worker clear-stale-lock`. The worker will never force-clear a live lock.

## Run-Once vs Bounded Loop

### Run-Once

Executes exactly one cycle and exits. The default mode for operator-triggered runs.

```bash
taskframe worker run-once
taskframe worker run-once --no-scheduler
taskframe worker run-once --no-event-sources
taskframe worker run-once --queue-limit 5
taskframe worker run-once --json
```

### Bounded Loop

Executes a fixed number of cycles separated by a configurable sleep interval. Always bounded — no indefinite loops.

```bash
taskframe worker run-loop --max-cycles 3 --sleep-seconds 5
taskframe worker run-loop --max-cycles 10 --sleep-seconds 30 --max-runtime-seconds 600
```

The loop respects:
- `max_cycles` — hard upper bound on cycle count
- `sleep_seconds` — delay between cycles
- `max_runtime_seconds` — wall-clock budget
- Stop request file — graceful shutdown between cycles

## Scheduler Integration

The worker calls `run_scheduler_tick()` with `dry_run=True`. The scheduler enqueues events for due schedules but does not execute them directly. All events flow through the durable queue.

## Event-Source Integration

The worker calls `poll_enabled_event_sources()` for all enabled sources. Each adapter produces normalized events that are deduplicated and enqueued via the durable queue. The worker limits the number of sources polled per cycle via `max_sources_per_cycle`.

## Queue Integration

The worker calls `process_queued_events()` with `dry_run=True`. Processing always runs in dry-run mode — live side effects are never executed by the worker. Pending actions are left pending for operator approval.

## Stop Request Model

A stop request is written to `runtime_data/worker/stop.request.json`:

```json
{
  "worker_id": "local-worker-1",
  "requested_at": "2026-05-22T08:00:00Z",
  "requested_by": "operator",
  "reason": "manual_stop"
}
```

The running loop checks for this file before each cycle. When found:
1. The worker completes the current cycle (if in progress)
2. The stop request file is deleted
3. Worker state is set to `STOPPED`
4. No further cycles are started

## Filesystem vs SQLite Persistence

The worker's own operational state (lock, heartbeat, cycle history) is always stored on the filesystem under `runtime_data/worker/`. The underlying queue, scheduler, and event-source data flows through the configured persistence backend (filesystem or SQLite).

| File | Purpose |
|------|---------|
| `runtime_data/worker/worker.lock.json` | Exclusive lock |
| `runtime_data/worker/state.json` | Worker status and last cycle |
| `runtime_data/worker/cycles.jsonl` | Append-only cycle history |
| `runtime_data/worker/stop.request.json` | Graceful stop signal |

## Safety Guarantees

The worker enforces these safety invariants:

- `dry_run_only = true` always — live side effects are never triggered
- `allow_live_side_effects = false` — blocked at config validation
- All execution goes through the queue runner (no direct manifest execution)
- Pending actions remain pending (approval required)
- Dead-letter records are never silently cleared
- No credentials or tokens appear in worker state or cycle history
- One subsystem failure does not abort the entire cycle (failures are recorded, not propagated)

## CLI Commands

```bash
taskframe worker status              # Show worker ID, status, lock, last cycle
taskframe worker health              # Check all dependency availability
taskframe worker run-once            # Execute one cycle
taskframe worker run-loop            # Execute bounded loop
taskframe worker stop                # Request graceful stop
taskframe worker cycles              # Show recent cycle history
taskframe worker clear-stale-lock    # Clear a stale lock (explicit)
```

## Cycle Summary Shape

```json
{
  "ok": true,
  "worker_id": "local-worker-1",
  "cycle_id": "cycle_20260522T080000_1",
  "started_at": "2026-05-22T08:00:00Z",
  "completed_at": "2026-05-22T08:00:01Z",
  "duration_ms": 1200,
  "stale_queue_recovered": 0,
  "schedule_events_enqueued": 0,
  "event_sources_polled": 1,
  "source_events_enqueued": 3,
  "queue_items_processed": 3,
  "queue_items_completed": 2,
  "queue_items_failed": 1,
  "dead_letter_count": 0,
  "warnings": [],
  "errors": []
}
```

## Known Limitations

- No Windows service or Linux systemd integration (planned for a future spec)
- No parallel workers — single-threaded, single-process
- No distributed locking — one `runtime_data_dir` per local worker
- No live side-effect execution — always dry-run
- Indefinite loop mode is not available in v1
- Worker state on the filesystem; SQLite tables for worker operational data are planned

## Future Path

- Windows service via `sc.exe` / NSSM
- Linux systemd unit file
- Container sidecar pattern
- Distributed lock via SQLite WAL or Redis
- Live side-effect execution (separate spec with additional safety gates)
