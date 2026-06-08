# Customer manifests

Drop this customer's `*.manifest.json` files here. They are auto-discovered at runtime
because the engine searches `TASKFRAME_CONFIG_DIR/manifests` (set to `/bundle/config/manifests`
by the bundle compose override) in addition to the built-in catalog.

Author and validate them with the engine's tooling before enabling:

- `docs/manifest_building_manual.md` — authoring
- `docs/manifest_contract_strict_mode.md` — strict validation
- `docs/manifest_catalog_health_repair.md` — catalog health
- dry-run each manifest before any pilot use

Only reference tools that are registered via `../enabled_toolpacks.json`.
