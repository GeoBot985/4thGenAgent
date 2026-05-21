# Durable Event Queue

Spec 137 — Production-ready event intake queue with persistence, dedupe, retry, dead-letter, and recovery.

## Purpose

The durable event queue makes event intake resilient by persisting each incoming event as a **queue record** before processing. This ensures:

- Events survive process restarts
- Duplicate events are blocked by deterministic dedupe keys
- Transient failures are retried automatically
- Permanent failures and exhausted retries are moved to a dead-letter queue
- Stale processing items can be recovered safely

The queue coexists with the existing Spec 108 event pipeline. It adds a buffered, claim-based processing layer between event ingestion and TaskFrame creation.

## Queue States

Each queue record moves through a defined state machine:

```
PENDING
  ↓ claim_next_event()
CLAIMED
  ↓ mark_event_processing()
PROCESSING
  ↓ success: mark_event_completed()   ─→ COMPLETED          (terminal)
  ↓ failure: mark_event_failed()
      ├── non-retryable category      ─→ FAILED_PERMANENT    (terminal)
      ├── retryable + below max       ─→ FAILED_RETRYABLE
      │       ↓ retry_event()
      │     PENDING
      └── retryable + at max          ─→ DEAD_LETTER         (terminal)

PENDING / CLAIMED / PROCESSING
  ↓ cancel_event()                   ─→ CANCELLED           (terminal)
```

**Terminal states**: `COMPLETED`, `FAILED_PERMANENT`, `DEAD_LETTER`, `CANCELLED`

## Event Dedupe Rules

Every queue record carries a `dedupe_key` derived from source + event_type + stable payload identity:

| Event Source        | Dedupe Identity                             |
|---------------------|---------------------------------------------|
| Manual / command    | `event_id`                                  |
| Gmail / email       | `message_id` from payload                   |
| Call-centre         | `message_id` or `call_id` from payload      |
| Schedule            | `schedule_id` + `scheduled_time`            |
| File event          | `file_path` + `content_hash`                |
| Database event      | `source_table` + `source_key` + `version`   |
| Other sources       | `event_id` (fallback)                       |

If an event with the same dedupe key already exists in a **non-terminal** state, `enqueue_event()` returns `ok=False` with `duplicate=True`. Terminal events may be re-enqueued by passing a new event with a different dedupe identity.

## Retry Rules

```json
{
  "max_attempts": 3,
  "retry_delay_seconds": 0,
  "retryable_categories": [
    "transient_tool_failure",
    "llm_transient_failure",
    "runtime_exception"
  ]
}
```

**Non-retryable categories** (always → `FAILED_PERMANENT`):
- `route_not_found`
- `manifest_not_found`
- `input_mapping_failed`
- `validation_failed`
- `policy_blocked`

**Retryable categories** (→ `FAILED_RETRYABLE`, or `DEAD_LETTER` after max attempts):
- `transient_tool_failure`
- `llm_transient_failure`
- `runtime_exception`

## Dead-Letter Handling

A queue item moves to `DEAD_LETTER` when:
- A retryable failure occurs AND `attempt_count >= max_attempts`

Dead-letter items remain in the queue index and are inspectable via:

```bash
taskframe queue dead-letter
taskframe queue dead-letter --json
```

Dead-letter items cannot be retried via `retry_event()`. Re-queuing requires explicit operator action (enqueue a new event).

## Recovery Command

Stale `CLAIMED` or `PROCESSING` items (no progress after 15 minutes) are recoverable:

```bash
taskframe queue recover-stale
taskframe queue recover-stale --stale-timeout-minutes 30
```

Recovery rules:
- `attempt_count < max_attempts` → move to `FAILED_RETRYABLE`
- `attempt_count >= max_attempts` → move to `DEAD_LETTER`
- `last_error` is updated with the recovery reason
- No new queue record is created

## Filesystem vs SQLite Behaviour

### Filesystem (default)
- Queue records stored in `runtime_data/queue/durable_queue.jsonl` (append-only log)
- Index stored in `runtime_data/queue/durable_queue_index.json` (keyed by `queue_id`)
- Persists across process restarts
- Thread-safe for single-process use

### SQLite (production)
- Queue records stored in `durable_event_queue` table (schema version 2)
- Indexed by `queue_id`, `dedupe_key`, and `event_id`
- Ordered by `priority ASC, available_at ASC` for `claim_next_event()`
- Enable with: `TASKFRAME_PERSISTENCE_BACKEND=sqlite TASKFRAME_SQLITE_DB_PATH=path/to/db`

## CLI Examples

```bash
# Show queue health summary
taskframe queue status
taskframe queue status --json

# List queue records
taskframe queue list
taskframe queue list --status PENDING
taskframe queue list --status FAILED_RETRYABLE --limit 20 --json

# Enqueue a safe local fixture event
taskframe queue enqueue-fixture customer_status
taskframe queue enqueue-fixture order_status

# Process one item
taskframe queue process-next
taskframe queue process-next --worker-id my-worker --json

# Process a batch
taskframe queue process-batch --limit 10

# Retry a failed item
taskframe queue retry <queue_id>

# Cancel an item
taskframe queue cancel <queue_id> --reason "Stale fixture"

# Inspect dead-letter queue
taskframe queue dead-letter
taskframe queue dead-letter --json

# Recover stale processing items
taskframe queue recover-stale
taskframe queue recover-stale --stale-timeout-minutes 30
```

## Queue Record Fields

| Field              | Type    | Description                                   |
|--------------------|---------|-----------------------------------------------|
| `queue_id`         | string  | UUID, primary key                             |
| `event_id`         | string  | Source event ID                               |
| `source`           | string  | Event source (e.g. `operator_ui`, `gmail`)    |
| `event_type`       | string  | Event type slug                               |
| `status`           | string  | Current queue status                          |
| `priority`         | int     | Lower = higher priority (default: 100)        |
| `attempt_count`    | int     | Number of processing attempts so far          |
| `max_attempts`     | int     | Maximum attempts before dead-letter           |
| `available_at`     | ISO ts  | Earliest time the item can be claimed         |
| `claimed_at`       | ISO ts  | When the item was claimed                     |
| `claimed_by`       | string  | Worker ID that claimed the item               |
| `completed_at`     | ISO ts  | When the item was completed                   |
| `linked_frame_id`  | string  | TaskFrame ID created during processing        |
| `dedupe_key`       | string  | SHA-256 of source + event_type + identity     |
| `payload_json`     | object  | Original event payload                        |
| `last_error`       | string  | Last failure message                          |
| `failure_category` | string  | Classified failure category                   |
| `created_at`       | ISO ts  | Record creation time                          |
| `updated_at`       | ISO ts  | Last modification time                        |

## Known Limitations

- **No parallel workers**: `claim_next_event()` is not concurrency-safe without external locking. Use a single worker process per queue.
- **No scheduled execution**: The queue runner does not auto-poll. Call `process-next` or `process-batch` explicitly.
- **No email/webhook polling**: External event sources must explicitly call `enqueue_event()`.
- **Retry delay is 0**: Items become available immediately after `retry_event()`. Back-off is not yet implemented.
- **Dead-letter replay**: Dead-letter items cannot be automatically re-queued. Operator must explicitly enqueue a new event.
