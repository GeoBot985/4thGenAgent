# Built-in Tool Pack Migration v1

This document records the first migration step where selected core tools are represented as tool packs while the legacy registry remains as fallback.

## What migrated in v1

- `business/get_order_context`
- `memory/set`
- `q/extract_order_ref`
- `report/generate`

These tools are available through the same `toolpack.json` contract used by external packs.

## Compatibility registry

The runtime merges:

1. migrated core tool packs;
2. enabled external tool packs;
3. legacy fallback registry.

The compatibility registry is intentionally conservative. Migrated tools must not become less safe than the legacy equivalent.

## What stays unchanged

- manifest syntax;
- pending-action approval flow;
- default dry-run behavior;
- optional RPA exclusion;
- live execution guardrails.

Existing manifests keep using the same command strings. No manifest edits are required for this migration step.

