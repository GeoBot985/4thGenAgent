# Manifest Health Dashboard

## Purpose

The Manifest Health Dashboard gives operators a catalog-wide view of active manifest authoring health. It answers which manifests are healthy, warning-only, failed, critical, smoke-passable, repairable, or blocked before release review.

This is an authoring health feature. It does not change runtime workflow behavior.

## Manifest Catalog Boundary

Only manifests in the active catalog are treated as release/operator manifests. Test, smoke, broken, and internal policy fixtures must live under `tests/fixtures/` and be loaded explicitly by tests. The dashboard intentionally excludes quarantined fixtures and `manifests/archive/`; placing an unsafe manifest in the active catalog should still make catalog health fail.

## Health classifications

| Health | Meaning |
|---|---|
| `HEALTHY` | The manifest loads, validates, has no repair findings, and passes smoke when smoke is required. |
| `WARNING` | The manifest loads and validates, has warning-only findings, and smoke passed. |
| `FAILED` | The manifest cannot load, fails validation, fails a smoke check, or has error findings. |
| `CRITICAL` | A high-risk issue exists, such as `live_execution.enabled: true`. |
| `SMOKE_SKIPPED` | The manifest loads and validates, but smoke was intentionally skipped for a documented reason. |

## What Validate All checks

`Validate All` scans the active manifest catalog and, for each manifest:

1. Reads the JSON.
2. Loads it through the runtime manifest loader.
3. Runs deterministic repair guidance.
4. Summarizes available auto-fix proposals without applying them.
5. Runs a dry-run smoke check only when it is safe to do so.
6. Assigns a health classification and recommended next action.
7. Writes JSON and Markdown reports under `runtime_data/manifest_health/`.

Archived manifests under `manifests/archive/` are not included. Broken gallery fixtures under `tests/fixtures/broken_manifests/` are test assets and are not included in production catalog checks.

## What it does not check

- It does not execute live side effects.
- It does not apply auto-fixes.
- It does not save manifest edits.
- It does not replace release verification.
- It does not prove business correctness or production readiness.
- It does not invent new repair rules, manifest types, or runtime behavior.

## How smoke checks are handled

Smoke checks always use dry-run behavior. They are skipped when:

- the manifest cannot load;
- a critical finding is present;
- required sample inputs are missing;
- an event manifest has no sample event/input;
- a configured smoke limit has been reached;
- the manifest is known to require external or live setup.

Skipped smoke is informational unless validation or repair findings are already severe.

## Repairable and manual-fix counts

A manifest is **repairable** when at least one deterministic low-risk auto-fix proposal is available.

A manifest is **manual fix required** when it has error or critical findings and there is no low-risk applyable auto-fix.

The dashboard only summarizes auto-fix availability. It never applies changes in bulk.

## How to read the Markdown report

The Markdown report begins with a summary table for catalog-level counts, followed by one row per manifest:

- **Health** — final classification.
- **Validation** — runtime loader result.
- **Smoke** — pass, fail, or skipped.
- **Repairable** — number of low-risk applyable proposals.
- **Top Findings** — the most important repair findings.
- **Next Action** — the recommended operator action.

Use the JSON report when you need machine-readable evidence or downstream automation.

## Recommended operator workflow

1. Open Manifest Workbench.
2. Click **Validate All**.
3. Review summary cards for failures, repairable manifests, and critical issues.
4. Select a row to inspect the detailed validation, smoke, repair, and auto-fix summary.
5. Use **Open Selected Manifest** to load the manifest into the editor.
6. Use **Repair Guidance**, **Auto-Fix Preview**, or **Smoke Test Selected** for focused follow-up work.
7. Re-run **Validate All** after making fixes.
8. Use the generated JSON/Markdown reports as release evidence.
