# External Event Source Polling — Spec 139

## Purpose

The external event source polling framework provides a structured, safe way to ingest events from external sources into the TaskFrame durable queue. It is:

- **Read-only by default** — adapters may only read from external sources
- **Deduplicated** — repeated polls never enqueue the same event twice
- **Stateful** — cursor/watermark state persists across polls
- **Auditable** — every poll run is recorded in polling history
- **Bounded** — no polling daemon; polling is triggered explicitly via CLI or schedule

The canonical flow is:

```
External Source
  → Read-only Poll (Adapter)
  → Normalized RuntimeEvent
  → Durable Queue (deduplication)
  → Queue Runner
  → TaskFrame Runtime
```

---

## Source Config Contract

Every event source has a canonical config record:

```json
{
  "source_id": "fixture_customer_messages",
  "name": "Fixture Customer Messages",
  "enabled": true,
  "adapter": "fixture_json",
  "mode": "fixture",
  "event_source": "fixture_customer_inbox",
  "event_type": "customer_message_received",
  "route_hint": "customer.status.from_email",
  "poll": {
    "fixture_path": "tests/fixtures/event_sources/customer_messages.json",
    "max_events_per_poll": 10
  },
  "dedupe": {
    "key_template": "fixture:{message_id}"
  },
  "cursor": {},
  "auth": {},
  "created_at": "2026-05-21T08:00:00Z",
  "updated_at": "2026-05-21T08:00:00Z"
}
```

| Field | Description |
|---|---|
| `source_id` | Unique identifier for this source |
| `name` | Human-readable name |
| `enabled` | Whether this source is active for polling |
| `adapter` | Adapter ID: `fixture_json` or `gmail_readonly` |
| `mode` | `fixture` (local) or `live_read` (external) |
| `event_source` | Runtime event source label |
| `event_type` | Runtime event type |
| `poll` | Adapter-specific poll settings |
| `dedupe` | Dedupe key template |
| `cursor` | Cursor type and watermark field |
| `auth` | Auth profile (Gmail only) |

---

## Adapter Contract

Adapters implement three methods:

```python
class EventSourceAdapter:
    adapter_id: str

    def health(self, config, runtime_data_dir) -> dict: ...
    def poll(self, config, state, runtime_data_dir) -> dict: ...
    def normalize(self, raw_record, config) -> dict: ...
```

All adapters are **read-only**. Adapters must never send, archive, delete, label, or otherwise mutate external sources.

Poll result shape:

```json
{
  "ok": true,
  "source_id": "...",
  "adapter": "fixture_json",
  "mode": "fixture",
  "raw_count": 3,
  "event_count": 3,
  "events": [...],
  "cursor_update": {"seen_ids": ["fixture:msg-001"]},
  "evidence": {},
  "error": "",
  "error_category": "",
  "warnings": []
}
```

---

## Fixture Event Source

The `fixture_json` adapter reads from a local JSON file. It is the safe default for tests and demos.

Config:

```json
{
  "source_id": "fixture_customer_messages",
  "adapter": "fixture_json",
  "mode": "fixture",
  "enabled": true,
  "poll": {
    "fixture_path": "tests/fixtures/event_sources/customer_messages.json",
    "max_events_per_poll": 10
  },
  "dedupe": {"key_template": "fixture:{message_id}"}
}
```

Fixture records look like:

```json
{
  "message_id": "msg-fixture-001",
  "customer_id": "CUST-1001",
  "from": "alex@example.com",
  "subject": "Where is my order?",
  "body": "Hi, where is order ORD-10042?",
  "received_at": "2026-05-21T08:00:00+02:00"
}
```

Normalized event:

```json
{
  "event_id": "evt_fixture_msg_fixture_001",
  "source": "fixture_customer_inbox",
  "event_type": "customer_message_received",
  "received_at": "2026-05-21T08:00:00+02:00",
  "payload": {
    "message_id": "msg-fixture-001",
    "customer_id": "CUST-1001",
    "from": "alex@example.com",
    "subject": "Where is my order?",
    "message": "Hi, where is order ORD-10042?",
    "channel": "email"
  }
}
```

---

## Gmail Read-Only Event Source

The `gmail_readonly` adapter reads from Gmail. It is **disabled by default** and requires explicit configuration.

Config:

```json
{
  "source_id": "gmail_customer_support",
  "adapter": "gmail_readonly",
  "mode": "live_read",
  "enabled": false,
  "poll": {
    "query": "label:inbox newer_than:7d",
    "max_events_per_poll": 20,
    "include_body": true
  },
  "auth": {
    "profile": "google_readonly",
    "requires_credentials": true,
    "token_path": "~/.taskframe/gmail_token.json"
  }
}
```

**Allowed operations:** search, list, read (messages.list, messages.get)

**Forbidden operations:** send, draft, archive, delete, label, mark-read, mark-unread, move, forward, insert, modify, trash

If credentials are missing, the adapter returns:

```json
{"ok": false, "status": "needs_auth", "error_category": "credentials_missing"}
```

---

## Dedupe Rules

The durable queue is the final dedupe authority. The event source layer provides stable dedupe keys:

| Source | Dedupe Key |
|---|---|
| Fixture message | `fixture:{message_id}` |
| Gmail message | `gmail:{message_id}` |
| Future Calendar event | `calendar:{calendar_id}:{event_id}:{updated}` |
| Future Sheet row | `sheet:{spreadsheet_id}:{range}:{row_hash}` |
| Future file event | `file:{path}:{content_hash}` |

Repeated polls with the same message IDs will not enqueue duplicates. The adapter's cursor/seen-id state also prevents re-polling already-processed records.

---

## Cursor / Watermark Handling

Each source has persistent cursor state:

```json
{
  "cursor": {
    "watermark": "",
    "seen_ids": ["fixture:msg-001", "fixture:msg-002"]
  }
}
```

- `seen_ids` — list of dedupe keys for already-processed records (capped at 500)
- `watermark` — ISO timestamp for watermark-based sources

Cursor state is updated automatically after each successful poll.

---

## Queue Integration

Polled events flow into the durable queue via `enqueue_event()` from `runtime/event_queue.py`. The queue assigns a `queue_id` and `dedupe_key`. Duplicate events (same dedupe key with a non-terminal status) are rejected silently.

The queue runner (`runtime/event_queue_runner.py`) picks up PENDING events and routes them to the appropriate manifest via `event_router.py`.

---

## Safety Rules

- Fixture sources are enabled by default only in test/demo profiles.
- Gmail live-read source is **disabled by default**.
- Gmail live-read requires explicit config and valid OAuth credentials.
- **No Gmail mutations are allowed** — ever.
- Polling never executes manifests directly.
- Polling only enqueues events into the durable queue.
- The queue runner handles TaskFrame creation.
- OAuth tokens are never stored in event source state or history.
- Polling history redacts message bodies by default.

---

## CLI Examples

```bash
# Show subsystem status
python -m src.taskframe_cli event-sources status

# List all configured sources
python -m src.taskframe_cli event-sources list-sources

# Create a default fixture source
python -m src.taskframe_cli event-sources create-fixture fixture_customer_messages

# Health check
python -m src.taskframe_cli event-sources health-check fixture_customer_messages

# Poll a single source
python -m src.taskframe_cli event-sources poll fixture_customer_messages

# Poll all enabled sources (bounded)
python -m src.taskframe_cli event-sources poll-enabled --limit 10

# Enable / disable
python -m src.taskframe_cli event-sources enable fixture_customer_messages
python -m src.taskframe_cli event-sources disable gmail_customer_support

# View polling history
python -m src.taskframe_cli event-sources history --limit 20

# JSON output
python -m src.taskframe_cli event-sources poll fixture_customer_messages --json
```

---

## Filesystem vs SQLite Persistence

### Filesystem (default)

```
runtime_data/event_sources/sources.json        — source configs (keyed by source_id)
runtime_data/event_sources/state.json          — per-source state (keyed by source_id)
runtime_data/event_sources/history.jsonl       — polling history (append-only)
```

### SQLite

When `TASKFRAME_PERSISTENCE_BACKEND=sqlite`, event sources use three tables:

- `event_sources` — source config records
- `event_source_state` — per-source polling state
- `event_source_history` — polling history

---

## Known Limitations

- No long-running polling daemon yet (explicit CLI trigger only).
- No push webhooks yet.
- Gmail live-read requires manual OAuth token setup.
- Calendar and Sheets polling not yet implemented.
- Polling history bodies are redacted; full payload stored in queue only.

See `docs/known_limitations.md` for the full list.

---

## Future Webhook / Daemon Path

A future polling daemon would wrap `poll_enabled_event_sources()` in a loop with configurable intervals. This is not implemented in Spec 139 — use the scheduler subsystem (Spec 138) with a `poll-enabled` command wrapper for now.

Webhooks would bypass the polling engine entirely and write directly to the durable queue.
