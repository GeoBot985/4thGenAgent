# Backend Security Hardening

**Spec 148** — Backend Security Headers, CORS Enforcement, and Token Hardening

---

## Overview

The production backend API applies layered security hardening at the middleware level:

1. **Security response headers** — added to every HTTP response regardless of outcome.
2. **CORS allowlist enforcement** — cross-origin requests from unlisted origins are rejected.
3. **Token hashing helpers** — tokens are stored and verified as SHA-256 hashes, never in plaintext.
4. **Token expiry enforcement** — expired `token_records` are rejected before reaching auth.
5. **Security status endpoint** — `/api/security/status` exposes the security posture without secrets.

---

## Default Security Posture

With no config file, the following defaults apply:

| Setting | Default |
|---|---|
| Security headers | Enabled |
| CORS enforcement | Enabled |
| Allowed CORS origins | `http://127.0.0.1:7860`, `http://localhost:7860` |
| Token authentication required | Yes |
| Plaintext dev tokens allowed | Yes (dev-only intent) |
| Token expiry enforcement | Off (no `token_records`) |
| Wildcard CORS (`*`) | Blocked except in `TASKFRAME_ENV=dev` or `test` |

---

## Security Response Headers

Applied to **all** responses, including auth failures, CORS rejections, and 4xx/5xx errors:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `Cache-Control` | `no-store` |
| `Content-Security-Policy` | `default-src 'self'; frame-ancestors 'none'; object-src 'none'` |

---

## CORS Configuration

CORS is enforced by an allowlist. Requests with an `Origin` header not in the list receive a `403 CORS_ORIGIN_BLOCKED` response.

Requests without an `Origin` header (same-origin, server-to-server) pass through without any CORS check.

### Wildcard CORS

`*` in `allowed_origins` is stripped unless `TASKFRAME_ENV` is `dev` or `test`. Setting a wildcard origin in a non-dev environment is an error surfaced by `get_security_status()`.

### Preflight (OPTIONS)

Preflight requests from an allowlisted origin return `200` immediately — they never reach the auth middleware. This is the standard browser behavior for CORS preflight.

### Configuration example

```json
{
  "backend_security": {
    "cors": {
      "enabled": true,
      "allowed_origins": ["http://127.0.0.1:7860", "http://localhost:7860"],
      "allow_credentials": false,
      "allowed_methods": ["GET", "POST", "OPTIONS"],
      "allowed_headers": ["Authorization", "Content-Type", "X-TaskFrame-Request-ID"]
    }
  }
}
```

---

## Token Hashing

Token values are never stored in plaintext. The `hash_token()` helper returns a `sha256:<hex>` string:

```python
from src.backend_security import hash_token, verify_token

h = hash_token("my-bearer-token")
# → "sha256:a3f1..."

assert verify_token("my-bearer-token", [h]) is True
```

To add a token to the config, generate its hash and store only the hash:

```bash
python -c "from src.backend_security import hash_token; print(hash_token('my-token'))"
```

---

## Token Expiry (token_records)

`token_records` provide per-token metadata including optional `expires_at`. When a bearer token matches a record that is expired, the security headers middleware rejects the request with `401 AUTH_TOKEN_EXPIRED` before the auth middleware is reached.

Token records use hashed values — raw tokens never appear in config files or audit logs.

```json
{
  "backend_security": {
    "token_records": [
      {
        "token_hash": "sha256:...",
        "label": "ci-deploy-token",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-12-31T23:59:59Z",
        "scopes": ["read"]
      }
    ]
  }
}
```

If a token is **not** found in `token_records`, it falls through to the existing auth middleware — backwards compatibility is preserved.

---

## Security Status Endpoint

`GET /api/security/status` (requires `viewer` role) returns the current security posture:

```json
{
  "ok": true,
  "security_headers_enabled": true,
  "cors_enabled": true,
  "allowed_origin_count": 2,
  "auth_required": true,
  "token_hash_count": 0,
  "token_record_count": 0,
  "plaintext_dev_token_allowed": true,
  "expired_token_count": 0,
  "warnings": [],
  "errors": []
}
```

This endpoint **never** exposes token hashes, raw token values, or plaintext secrets.

### CLI equivalent

```bash
taskframe backend-security
taskframe backend-security --json
```

---

## Middleware Order

Middleware is registered innermost-first (LIFO execution order):

1. `install_backend_auth_middleware` — resolves auth context (innermost)
2. `install_audit_request_id_middleware` — generates `X-Request-ID`
3. `install_body_size_middleware` — rejects oversized payloads
4. `install_cors_middleware` — CORS allowlist enforcement
5. `install_security_headers_middleware` — adds headers to ALL responses; checks token expiry (outermost)

The outermost middleware wraps all others, so security headers appear on every response regardless of where the request is rejected.

---

## Reverse Proxy Notes

This API is intended for private-network deployment (localhost or internal LAN). When deployed behind a reverse proxy (nginx, Caddy):

- The proxy should terminate TLS and add its own `Strict-Transport-Security` header.
- The CORS `allowed_origins` should list the proxy's origin, not internal addresses.
- The proxy may add `X-Forwarded-For` — the API does not use this value for auth decisions.

---

## What This Does NOT Solve

| Item | Notes |
|---|---|
| OAuth2 / OIDC | Not implemented. Single shared bearer token only. |
| SSO / multi-user sessions | Not implemented. |
| RBAC beyond 3 roles | Roles are `admin`, `operator`, `viewer` — no custom RBAC. |
| Browser session management | No cookies or session tokens. |
| Public internet exposure | Designed for local/private network only. |
| Live side-effect authorization | Controlled by the runtime safety layer, not the HTTP security layer. |
| Secrets vault | Config file tokens are hashed but the config file itself must be protected by OS file permissions. |

---

## Files

| File | Description |
|---|---|
| `src/backend_security.py` | Core security config, middleware, and token helpers |
| `src/backend/routes/security.py` | `/api/security/status` endpoint |
| `config/backend_security.example.json` | Full example configuration |
| `tests/test_backend_security.py` | Test suite (51 tests) |
| `docs/backend_security_hardening.md` | This document |
