# Manifest Regression Gallery

The manifest regression gallery is the curated fixture suite for keeping manifest parsing, strict validation, repair guidance, smoke classification, and autofix behavior stable as the runtime evolves.

## Purpose

- preserve known bad, edge-case, and unsafe manifests as regression fixtures
- verify strict validation stays aligned with current runtime behavior
- classify smoke failures consistently
- document which manifest issues are autofixable and which are not

## Fixture categories

- valid
- structural
- command
- inputs
- validations
- completion
- side_effects
- events
- llm
- governance

## Index schema

Each fixture entry declares:

- `id`
- `path`
- `category`
- `description`
- `expected_findings`
- `expected_severity`
- `expected_strict_status`
- `expected_autofix`

Optional fields may include smoke classification, repair guidance text checks, and notes.

## Running the gallery

```bash
python -m src.taskframe_cli manifests gallery list
python -m src.taskframe_cli manifests gallery validate
python -m src.taskframe_cli manifests gallery run --fixture completion_output_missing
python -m src.taskframe_cli manifests gallery report
```

Reports are written to:

- `runtime_data/manifest_regression_gallery/gallery_report.json`
- `runtime_data/manifest_regression_gallery/gallery_report.md`

## How it works

For each fixture the gallery:

1. loads the manifest
2. runs strict contract validation
3. collects repair guidance
4. optionally runs smoke classification
5. checks autofix expectations
6. records the result in JSON and Markdown reports

Strict validation failures are release-gated. Repair guidance is informational. Autofix is intentionally limited; unknown tools, unsafe live execution, and malformed JSON are not blindly rewritten.

## Adding a fixture

1. add the manifest under `tests/fixtures/manifest_regression_gallery/`
2. add an entry to `gallery_index.json`
3. choose the narrowest category that matches the failure mode
4. set expectations to the actual strict, smoke, and autofix behavior

## Release verification

The release verifier runs the full gallery and blocks release if fixture expectations drift, the index is invalid, or the report cannot be generated.
