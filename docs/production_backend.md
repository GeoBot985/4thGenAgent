# Production Backend Run Operations API

**Spec 141 — Production Backend Run Operations API v1**

## Purpose

The production backend exposes a controlled FastAPI HTTP API for inspecting TaskFrame runs and triggering supported run operations. It wraps existing runtime functions — it does not add new business logic.

## API Boundary

The backend API:

- Reads from persisted run artifacts via existing runtime functions
- Approves/rejects pending actions through `runtime.approval` only
- Generates run reports through `runtime.run_report` only
- Receives events via POST `/api/events` but routes them using the existing `event_routes.json` registry
- Accepts only registered event sources and event types; the API never selects a manifest directly
- Does not execute tools directly
- Does not read arbitrary files
- Does not bypass pending-action approval state
- Preserves dry-run defaults (live event execution is rejected)

## Routes

### POST /api/events

Submits an external event into the TaskFrame runtime (Controlled Event Intake API). 

**Request body:**
```json
{
  "source": "api",
  "event_type": "customer.message.received",
  "payload": {},
  "idempotency_key": "optional-string",
  "dry_run": true
}
```

**Response:**
```json
{
  "ok": true,
  "event_id": "string",
  "source": "api",
  "event_type": "customer.message.received",
  "route_id": "string",
  "manifest_id": "string",
  "linked_frame_id": "string",
  "frame_state": "WAITING_FOR_EXECUTE",
  "summary": {},
  "pending_action_count": 1,
  "executed_action_count": 0,
  "error": ""
}
```

### GET /api/events

Returns recent event ledger entries.

**Query parameters:**
- `limit` (int, default 50)
- `source` (string, optional)
- `event_type` (string, optional)
- `status` (string, optional)

**Response:**
```json
{
  "ok": true,
  "events": [
    {
      "event_id": "string",
      "source": "string",
      "event_type": "string",
      "received_at": "string",
      "status": "string",
      "route_id": "string",
      "manifest_id": "string",
      "linked_frame_id": "string",
      "error": ""
    }
  ],
  "count": 0,
  "error": ""
}
```

### GET /api/events/{event_id}

Returns one event plus linked run metadata.

**Response:**
```json
{
  "ok": true,
  "event": {},
  "linked_frame": {
    "frame_id": "string",
    "manifest_id": "string",
    "state": "string",
    "summary": {},
    "pending_action_count": 0,
    "executed_action_count": 0,
    "error_count": 0
  },
  "error": ""
}
```

### GET /api/runs

Returns recent run ledger records (most recent first).

**Query parameters:**
- `limit` (int, default 50) — max records to return

**Response:**
```json
{
  "ok": true,
  "runs": [
    {
      "frame_id": "string",
      "manifest_id": "string",
      "state": "string",
      "created_at": "string",
      "updated_at": "string",
      "pending_action_count": 0,
      "executed_action_count": 0,
      "error_count": 0,
      "artifact_dir": "string"
    }
  ],
  "count": 0,
  "error": ""
}
```

### GET /api/runs/{frame_id}

Returns the normalized TaskFrame summary and core metadata for one run.

Large raw outputs are not returned by default. The `outputs_preview` field contains up to 10 output keys.

**Response:**
```json
{
  "ok": true,
  "frame_id": "string",
  "manifest_id": "string",
  "state": "string",
  "summary": {},
  "outputs_preview": {},
  "pending_actions": [],
  "errors": [],
  "validations": [],
  "artifact_paths": {"artifact_dir": "string"},
  "error": ""
}
```

### GET /api/runs/{frame_id}/evidence

Returns the full evidence bundle generated from persisted run artifacts. Evidence is built from `runtime/evidence_bundle.py` — not from live UI state.

### GET /api/runs/{frame_id}/approval-pack

Returns the approval pack view for the run.

```json
{
  "ok": true,
  "frame_id": "string",
  "approval_pack": {},
  "pending_action_count": 0,
  "error": ""
}
```

### GET /api/runs/{frame_id}/failure-summary

Returns the failure summary for the run (works for both failed and completed frames).

```json
{
  "ok": true,
  "frame_id": "string",
  "failure_summary": {},
  "error": ""
}
```

### POST /api/runs/{frame_id}/report

Generates or rebuilds the operator run report.

**Request body:**
```json
{"rebuild": false}
```

**Response:**
```json
{
  "ok": true,
  "frame_id": "string",
  "markdown_path": "string",
  "html_path": "string",
  "evidence_bundle_path": "string",
  "error": ""
}
```

### POST /api/runs/{frame_id}/pending-actions/{action_id}/approve

Approves a pending action. Calls `runtime.approval.approve_action` — no direct mutation.

### POST /api/runs/{frame_id}/pending-actions/{action_id}/reject

Rejects a pending action. Calls `runtime.approval.reject_action` — no direct mutation.

**Approval/rejection response:**
```json
{
  "ok": true,
  "frame_id": "string",
  "action_id": "string",
  "operation": "approve|reject",
  "state": "string",
  "pending_actions": [],
  "executed_actions": [],
  "error": ""
}
```

## Safety Rules

| Rule | Enforcement |
|------|-------------|
| frame_id must match `[A-Za-z0-9_-]{1,128}` | Validated at route entry; 400 if invalid |
| action_id must match `[A-Za-z0-9_-]{1,128}` | Validated at route entry; 400 if invalid |
| event_id must match `[A-Za-z0-9_-]{1,128}` | Validated at route entry; 400 if invalid |
| No path traversal | ID regex blocks `/`, `..`, `\` |
| No arbitrary file reads | Only approved runtime functions called |
| No direct tool execution | No tool runner invoked from API |
| Event Intake payload | Must be JSON object. Event route logic resolves manifest. |
| Event routing | Strict routing boundary. API cannot bypass and select arbitrary tools or manifests directly. |
| Registered sources | `source` must be a registered contract entry such as `api` for the controlled intake route |
| Approval must go through existing approval functions | `runtime.approval.approve_action` / `reject_action` only |
| Live side effects | Controlled by existing live execution guardrails (unchanged). Event intake `dry_run=false` is rejected. |
| Dry-run default | Report generation and queue operations default to dry-run |

## Authentication and roles

Production backend routes are protected by static bearer tokens.

Set up local auth with environment variables:

```powershell
$env:TASKFRAME_BACKEND_AUTH_ENABLED="true"
$env:TASKFRAME_BACKEND_ALLOW_DEV_BYPASS="false"
$env:TASKFRAME_BACKEND_ADMIN_TOKEN="<secret>"
$env:TASKFRAME_BACKEND_OPERATOR_TOKEN="<secret>"
$env:TASKFRAME_BACKEND_VIEWER_TOKEN="<secret>"
```

You can also point the backend at a JSON config file with `TASKFRAME_BACKEND_AUTH_CONFIG_PATH` or pass `backend_auth_config_path` to `create_app()`. The example config lives at `config/examples/taskframe.backend.example.json`.

Role access:

- `viewer`: read-only inspection routes
- `operator`: inspection plus event intake and approval/rejection
- `admin`: all backend routes, still subject to runtime live-execution guardrails

The dev bypass is only for local development. It is only active when auth is explicitly disabled and `TASKFRAME_BACKEND_ALLOW_DEV_BYPASS=true`. Do not use it outside local dev.

Backend auth does not replace the runtime live-execution safety model.

## Usage

```python
from src.production_backend import create_app

app = create_app(runtime_data_dir="runtime_data")
# Serve with: uvicorn src.production_backend:app
```

Or in tests:

```python
from fastapi.testclient import TestClient
from src.production_backend import create_app

client = TestClient(
    create_app(runtime_data_dir=str(tmp_path)),
    headers={"Authorization": "Bearer <viewer-token>"},
)
response = client.get("/api/runs")
```

If you are using the dev bypass locally, keep it explicit in your config and do not rely on unauthenticated calls in production-shaped tests.

## Known Limitations

- No user-management UI or OAuth flow
- No pagination cursor (limit parameter only)
- Evidence bundle may be large for long-running frames
- Approval/rejection does not trigger automatic task continuation
- Report generation is synchronous; large frames may be slow

## Related

- [production_persistence_backend.md](production_persistence_backend.md)
- [durable_event_queue.md](durable_event_queue.md)
- [local_worker_supervisor.md](local_worker_supervisor.md)
