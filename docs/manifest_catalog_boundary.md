# Manifest Catalog Boundary

## Purpose

The manifest catalog boundary separates release/operator manifests from test-only fixtures. Catalog health is intentionally strict, so manifests that are useful only for tests must not be mixed into the active operator catalog.

## Active Manifest Catalog

`manifests/` contains active operator and demo manifests. Files in this directory are assumed to be:

- release-relevant;
- operator-visible;
- health-checkable;
- safe by default.

Active manifests are included in catalog loading, the operator UI, and release health verification.

## Test and Smoke Manifest Quarantine

Test-only manifests live under `tests/fixtures/`, including smoke and live-policy fixtures under `tests/fixtures/smoke_manifests/`.

These fixtures may intentionally contain dangerous settings, intentional failures, or narrowly targeted runtime behavior used by tests. They are not operator-visible and are not part of release catalog health.

## Why Live-Policy Manifests Are Not Active Manifests

Some live-execution policy tests need manifests with `live_execution.enabled: true`. Those manifests are valuable test inputs, but they are not safe defaults for operators and should not be release catalog entries. Keeping them quarantined preserves test coverage without weakening active-catalog safety rules.

## How Tests Should Load Quarantined Manifests

Tests should load quarantined manifests explicitly by path:

```python
from pathlib import Path
from runtime.manifest_loader import load_manifest

SMOKE_MANIFEST_DIR = Path("tests/fixtures/smoke_manifests")
manifest = load_manifest(SMOKE_MANIFEST_DIR / "smoke_live_sheet_create_allowed.manifest.json")
```

When a test exercises route-based runtime behavior for a quarantined manifest, pass the fixture directory as the test runtime's `manifest_dir`.

## Release Health Rules

Release health scans active manifests only. It must:

- fail on active critical manifests;
- fail on active validation/load failures;
- ignore quarantined smoke/test fixtures because they are not release manifests;
- keep archived manifests out of the active catalog.

## Operator UI Visibility Rules

The operator catalog shows active manifests only. Test, smoke, broken, and internal policy fixtures are not operator catalog entries and should be loaded only by tests that name their fixture paths explicitly.
