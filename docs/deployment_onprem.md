# On-Prem Pilot Deployment

This runbook covers deploying the TaskFrame Runtime **production backend API** for a
self-hosted pilot customer using Docker. The customer runs the image in their own
environment; you ship the image and this document, and they supply secrets and storage.

> Scope: this deploys the controlled **read/operate API** (`src.production_backend:app`).
> Live side effects (email send, sheet write, calendar mutation) remain **blocked** by the
> runtime guardrails. The backend auth boundary is not a substitute for those guardrails.

---

## 1. Prerequisites

- Docker Engine 24+ and the Docker Compose plugin on the host.
- A reverse proxy (nginx/Caddy/Traefik) for TLS if the API is reached over a network.
  The compose file binds to `127.0.0.1` by default — nothing is exposed without a proxy.

## 2. Configure secrets

```bash
cp .env.example .env
```

Generate one strong token per role and paste them into `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set `TASKFRAME_BACKEND_ADMIN_TOKEN`, `TASKFRAME_BACKEND_OPERATOR_TOKEN`, and
`TASKFRAME_BACKEND_VIEWER_TOKEN`. Keep `TASKFRAME_BACKEND_AUTH_ENABLED=true` and
`TASKFRAME_BACKEND_ALLOW_DEV_BYPASS=false`. The `.env` file is gitignored — never commit it.

Roles are hierarchical (`admin > operator > viewer`). Hand the customer only the tokens
each user needs; the viewer token is enough for read-only/health access.

## 3. Build and start

```bash
docker compose up -d --build
docker compose logs -f api
```

To include PDF/invoice extraction support, build with the PDF extra:

```bash
docker compose build --build-arg INSTALL_PDF=1
docker compose up -d
```

## 4. Verify

The container healthcheck calls `/api/health` with the viewer token. Check status:

```bash
docker compose ps          # api should be "healthy" after ~30s
curl -s http://127.0.0.1:8000/api/health \
  -H "Authorization: Bearer $TASKFRAME_BACKEND_VIEWER_TOKEN" | python -m json.tool
```

A healthy response has `"ok": true` and `"backend": "ready"`. A `403`/`401` means the
token is wrong; `"backend": "auth_invalid"` means the auth config didn't load.

## 5. Data persistence

Runtime state (audit trail, runs, stores) lives in `/app/runtime_data`, mounted to the
named volume `taskframe_runtime_data`. Back it up regularly:

```bash
docker run --rm -v taskframe_runtime_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/taskframe_runtime_data_$(date +%F).tar.gz -C /data .
```

## 6. TLS / network exposure

The API ships **without** TLS. To expose it beyond localhost, place it behind a reverse
proxy that terminates TLS and forwards to `127.0.0.1:8000`. Only then change the compose
`ports` binding if needed. Do not bind `0.0.0.0:8000` directly to an untrusted network.

CORS, security headers, request hardening (body-size limits, ID validation), and rate
limits are configured in `config/examples/taskframe.backend.example.json`. Mount a
customer-specific copy and point `TASKFRAME_BACKEND_AUTH_CONFIG_PATH` /
`TASKFRAME_BACKEND_CONFIG_PATH` at it to override.

## 7. Upgrades

```bash
git pull                       # or load the new image tarball
docker compose up -d --build   # rebuild and restart; the data volume is preserved
```

## 8. Operational checks

- `docker compose logs api` — application logs (uvicorn + audit warnings).
- `/api/health` — auth/audit/hardening status and whether the runtime is in live mode
  (should be `runtime_live_mode: false` for a pilot).
- Audit records are written under `runtime_data/audit/` and never contain bearer tokens.

---

## Pre-pilot checklist

- [ ] `.env` populated with strong, unique tokens; `.env` not committed.
- [ ] `docker compose ps` shows the `api` service `healthy`.
- [ ] `/api/health` returns `ok: true` and `runtime_live_mode: false`.
- [ ] Reverse proxy with TLS in front of the API (if network-exposed).
- [ ] `runtime_data` volume backup scheduled.
- [ ] Customer handed only the role tokens they require.
- [ ] `taskframe pilot-readiness` gate reviewed (see docs/pilot_readiness.md).
