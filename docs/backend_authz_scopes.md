# Backend Auth Scopes + Route Permission Enforcement

**Spec 149** — Token-scope-based route permission enforcement for the TaskFrame backend API.

> This spec adds route-level token authorization. It does not implement user accounts, SSO, RBAC, tenancy, or production identity management.

---

## Overview

Spec 148 introduced `token_records` with a `scopes` field. Spec 149 makes those scopes meaningful: every token that has a `token_records` entry is now **scope-checked** against the permission requirements of the route it accesses.

Tokens that have **no** matching `token_record` are not scope-checked (backwards compatibility with the 3-role env-var token system from Spec 141).

---

## Canonical Scopes

| Scope | Meaning |
|---|---|
| `read` | General low-risk read access |
| `events:intake` | Submit external events into the runtime |
| `runs:read` | View runs and TaskFrame state |
| `reports:read` | View/open report metadata and evidence |
| `approvals:read` | View pending approval packs |
| `approvals:write` | Approve or reject pending actions |
| `readiness:read` | View readiness and evidence gate status |
| `security:read` | View sanitized backend security status |
| `admin:status` | View general backend status/config posture |

No wildcard scope exists. `read` does not imply any `*:read` scope and `approvals:read` does not imply `approvals:write`.

---

## Route Permission Map

| Route | Required Scopes |
|---|---|
| `GET /api/health` | *(none — any authenticated token)* |
| `GET /api/security/status` | `security:read` |
| `POST /api/events` | `events:intake` |
| `GET /api/events` | `runs:read` |
| `GET /api/events/{event_id}` | `runs:read` |
| `GET /api/audit` | `admin:status` |
| `GET /api/audit/{audit_id}` | `admin:status` |
| `GET /api/runs` | `runs:read` |
| `GET /api/runs/{frame_id}` | `runs:read` |
| `GET /api/runs/{frame_id}/evidence` | `reports:read` |
| `GET /api/runs/{frame_id}/approval-pack` | `approvals:read` |
| `GET /api/runs/{frame_id}/failure-summary` | `runs:read` |
| `POST /api/runs/{frame_id}/report` | `reports:read` |
| `POST /api/runs/{frame_id}/pending-actions/{action_id}/approve` | `approvals:write` |
| `POST /api/runs/{frame_id}/pending-actions/{action_id}/reject` | `approvals:write` |

Routes not in the map fail closed when scope enforcement is active.

---

## Example Token Records

### Read-only UI Token

```json
{
  "token_hash": "sha256:<hash>",
  "label": "operator-ui-local",
  "created_at": "2026-05-22T00:00:00Z",
  "expires_at": "2026-06-22T00:00:00Z",
  "scopes": ["read", "runs:read", "reports:read", "approvals:read"]
}
```

This token can view runs, evidence, and approval packs — but cannot approve/reject actions or submit events.

### Approval Operator Token

```json
{
  "token_hash": "sha256:<hash>",
  "label": "approval-operator",
  "created_at": "2026-05-22T00:00:00Z",
  "expires_at": "2026-06-22T00:00:00Z",
  "scopes": ["runs:read", "approvals:read", "approvals:write"]
}
```

This token can view and act on pending approvals.

### Event Intake Token

```json
{
  "token_hash": "sha256:<hash>",
  "label": "event-intake-service",
  "created_at": "2026-05-22T00:00:00Z",
  "expires_at": "2026-12-31T23:59:59Z",
  "scopes": ["events:intake"]
}
```

This token can only submit events. It cannot read runs or reports.

### Admin/Status Token

```json
{
  "token_hash": "sha256:<hash>",
  "label": "monitoring-dashboard",
  "created_at": "2026-05-22T00:00:00Z",
  "scopes": ["admin:status", "security:read", "runs:read"]
}
```

This token can view health, security status, audit logs, and runs — but cannot approve actions or submit events.

---

## Permission Denied Response

When a scoped token is missing a required scope:

```json
{
  "ok": false,
  "error": "FORBIDDEN",
  "message": "Token does not have permission for this endpoint.",
  "required_scopes": ["approvals:write"],
  "missing_scopes": ["approvals:write"],
  "request_id": "req_..."
}
```

The response never includes token hashes or raw token values.

---

## Audit Events

Four authz audit event types are written to the backend audit ledger:

| Event Type | When |
|---|---|
| `AUTHZ_ALLOWED` | Scoped token passes the scope check |
| `AUTHZ_DENIED` | Scoped token is missing a required scope |
| `AUTHZ_ROUTE_UNMAPPED` | Route is not in the permission map (fail closed) |
| `AUTHZ_SCOPE_INVALID` | (Reserved for future invalid-scope detection) |

Audit records include `token_label` (from the token record), never the raw token or its hash:

```json
{
  "event_type": "AUTHZ_DENIED",
  "request_id": "req_...",
  "token_label": "operator-ui-local",
  "method": "POST",
  "path": "/api/runs/TF-001/pending-actions/ACT-1/approve",
  "required_scopes": ["approvals:write"],
  "missing_scopes": ["approvals:write"],
  "timestamp": "2026-05-22T..."
}
```

---

## Middleware Execution Order

The authz middleware is registered first in `create_app()`, making it the innermost middleware. It runs after auth has set the auth context:

```
security_headers (outermost)
  → cors
    → body_size
      → audit_request_id
        → auth (resolves backend_auth_context)
          → authz (enforces scopes)  ← innermost
            → route_handler
```

Scope enforcement is skipped when:
- No `token_records` are configured (backwards compatible).
- Auth context is missing or failed (route handles 401).
- Dev bypass is active.
- The bearer token has no matching `token_record` (pass-through).

---

## Backwards Compatibility

If no `token_records` are configured in the security config, the authz middleware is fully transparent. All existing behaviour from Spec 141–148 is preserved.

Only tokens with an explicit `token_record` entry are scope-enforced.

---

## Why Scopes Do Not Equal Full RBAC

The 3 existing roles (`admin`, `operator`, `viewer`) provide coarse-grained access tiers. Scopes provide fine-grained, per-token capability constraints within those tiers.

Scopes are intentionally simple:
- No scope hierarchy or inheritance
- No resource-level permissions
- No per-record access control
- No tenant isolation
- No delegation or chaining

More advanced access control (multi-user accounts, tenant isolation, OAuth2 flows) would require a dedicated identity management layer not in scope here.

---

## Files

| File | Description |
|---|---|
| `src/backend_authz.py` | Core scope definitions, route map, authz functions, middleware |
| `tests/test_backend_authz.py` | Test suite (43 tests) |
| `docs/backend_authz_scopes.md` | This document |
