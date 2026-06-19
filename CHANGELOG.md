# Changelog

All notable changes to the TaskFrame Runtime are recorded here.
This project follows a controlled demo → pilot → service boundary; see
[docs/production_readiness_roadmap.md](docs/production_readiness_roadmap.md).

## [0.2.0] — 2026-06-19

### Added
- **On-prem pilot Docker bundle.** Self-contained core image serving the controlled
  read/operate API (`src.production_backend:app` via uvicorn): non-root user, container
  healthcheck against `/api/health`, loopback-only port binding, optional PDF extra
  (`INSTALL_PDF=1`). Backend auth is on and dev bypass off; live side effects remain
  blocked by the runtime guardrails (`TASKFRAME_ENABLE_LIVE_EXECUTION=0`).
- **Per-customer bundle model.** `docker-compose.bundle.yml` overlay, `bundles/_template`
  scaffold, and an `ONBOARDING.md` engagement gate so each customer's config, manifests,
  tool packs, and runtime state are mounted into the unchanged core image.
- **On-prem deployment runbook** ([docs/deployment_onprem.md](docs/deployment_onprem.md))
  covering secrets, build/run, health verification, data persistence, TLS, and upgrades.

### Fixed
- `taskframe --help` no longer raises a format error: literal `%` in the `readiness` and
  `readiness-gate` subcommand help strings is now escaped (`%%`).

### Changed
- Roadmap updated to record the Docker bundle as delivered (removed from Deferred Work).

### Chore
- Stopped tracking generated packaging metadata; `*.egg-info/`, `build/`, and `dist/`
  are now gitignored. (Previously a regenerated `SOURCES.txt` had pulled ~246k
  `runtime_data/` paths into the tree.)
</content>
</invoke>
