from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from runtime.command_parser import CommandParseError, parse_command
from runtime.manifest_loader import load_manifest as runtime_load_manifest
from runtime.tool_registry import build_tool_registry
from src.manifest_authoring_feedback import explain_manifest_failure
from src.manifest_autofix import apply_manifest_fix_preview, propose_manifest_fixes
from src.manifest_contract_strict import validate_manifest_strict
from src.generated_manifest_smoke_runner import smoke_run_manifest_candidate

DEFAULT_GALLERY_DIR = Path("tests/fixtures/manifest_regression_gallery")
DEFAULT_RUNTIME_DATA_DIR = Path("runtime_data")
REQUIRED_FIXTURE_KEYS = ("id", "path", "category", "description", "expected_findings", "expected_severity", "expected_strict_status", "expected_autofix")
REQUIRED_CATEGORIES = {
    "valid",
    "structural",
    "command",
    "inputs",
    "validations",
    "completion",
    "side_effects",
    "events",
    "llm",
    "governance",
}
ALLOWED_AUTOFIX_VALUES = {"PROPOSED", "NOT_SUPPORTED", "BLOCKED", "NONE"}


# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------


def load_gallery_index(gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> dict:
    """Load and return gallery_index.json."""
    path = Path(gallery_dir) / "gallery_index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def iter_gallery_fixtures(gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> list[dict]:
    """Return fixture metadata from the gallery index."""
    index = load_gallery_index(gallery_dir)
    fixtures = index.get("fixtures") or []
    return list(fixtures) if isinstance(fixtures, list) else []


def validate_gallery_index(gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> dict:
    """Validate gallery index shape and fixture coverage."""
    errors: list[str] = []
    warnings: list[str] = []
    fixtures = iter_gallery_fixtures(gallery_dir)
    gallery_path = Path(gallery_dir)

    if not gallery_path.is_dir():
        errors.append(f"Gallery directory not found: {gallery_path}")
        return {
            "ok": False,
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "fixture_count": 0,
            "categories": {},
        }

    ids: list[str] = []
    category_counts: Counter[str] = Counter()
    missing_fields: list[str] = []
    path_errors: list[str] = []

    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append("Fixture metadata must be an object.")
            continue
        for field in REQUIRED_FIXTURE_KEYS:
            if field not in fixture:
                missing_fields.append(str(fixture.get("id") or "<unknown>"))
                errors.append(f"Fixture {fixture.get('id', '<unknown>')} is missing field: {field}")
                break

        fixture_id = str(fixture.get("id") or "").strip()
        if fixture_id:
            ids.append(fixture_id)
        category = str(fixture.get("category") or "").strip()
        if category:
            category_counts[category] += 1

        fixture_path = gallery_path / str(fixture.get("path") or "")
        if not fixture_path.exists():
            path_errors.append(str(fixture.get("path") or ""))
            errors.append(f"Fixture file missing: {fixture.get('path')}")

        autofix = fixture.get("expected_autofix")
        if isinstance(autofix, str) and autofix not in ALLOWED_AUTOFIX_VALUES:
            errors.append(f"Fixture {fixture_id} has invalid expected_autofix value: {autofix}")

    if len(ids) != len(set(ids)):
        dups = [item for item, count in Counter(ids).items() if count > 1]
        errors.append(f"Duplicate fixture IDs found: {dups}")

    missing_categories = sorted(REQUIRED_CATEGORIES - set(category_counts))
    if missing_categories:
        errors.append(f"Gallery is missing required categories: {missing_categories}")

    if len(fixtures) < 41:
        errors.append(f"Gallery fixture count is below minimum: {len(fixtures)} < 41")

    if missing_fields:
        warnings.append(f"Fixtures with missing fields: {sorted(set(missing_fields))}")
    if path_errors:
        warnings.append(f"Missing fixture files: {sorted(set(path_errors))}")

    ok = not errors
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "fixture_count": len(fixtures),
        "categories": dict(category_counts),
    }


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


def load_gallery_fixture(fixture: dict, gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> dict:
    """Load one gallery fixture as raw JSON text and parsed manifest, if possible."""
    path = Path(gallery_dir) / str(fixture.get("path") or "")
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "manifest": None, "text": "", "path": str(path), "exception": exc}

    try:
        manifest = json.loads(text)
    except Exception as exc:
        return {"ok": False, "manifest": None, "text": text, "path": str(path), "exception": exc}

    if not isinstance(manifest, dict):
        return {
            "ok": False,
            "manifest": None,
            "text": text,
            "path": str(path),
            "exception": ValueError("Gallery fixture root must be a JSON object."),
        }

    return {"ok": True, "manifest": manifest, "text": text, "path": str(path), "exception": None}


def load_fixture_manifest(fixture: dict, gallery_dir: str | Path = DEFAULT_GALLERY_DIR) -> dict:
    """Backward-compatible alias used by existing manifest authoring regression tests."""
    return load_gallery_fixture(fixture, gallery_dir)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_gallery_fixture(
    fixture_id: str,
    *,
    gallery_dir: str | Path,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
    strict: bool = True,
    smoke: bool = True,
    repair_guidance: bool = True,
    autofix: bool = True,
) -> dict:
    fixture = _get_fixture_by_id(fixture_id, gallery_dir)
    return _run_fixture_record(
        fixture,
        gallery_dir=gallery_dir,
        runtime_data_dir=runtime_data_dir,
        strict=strict,
        smoke=smoke,
        repair_guidance=repair_guidance,
        autofix=autofix,
    )


def run_gallery(
    *,
    gallery_dir: str | Path,
    runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR,
    strict: bool = True,
    smoke: bool = True,
    repair_guidance: bool = True,
    autofix: bool = True,
) -> dict:
    validation = validate_gallery_index(gallery_dir)
    fixtures = iter_gallery_fixtures(gallery_dir)
    results = [
        _run_fixture_record(
            fixture,
            gallery_dir=gallery_dir,
            runtime_data_dir=runtime_data_dir,
            strict=strict,
            smoke=smoke,
            repair_guidance=repair_guidance,
            autofix=autofix,
        )
        for fixture in fixtures
    ]

    total = len(results)
    passed = sum(1 for item in results if item.get("matched_expectations"))
    failed = total - passed
    categories: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    for item in results:
        bucket = categories[item["category"]]
        bucket["total"] += 1
        if item.get("matched_expectations"):
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    ok = validation["ok"] and failed == 0
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "gallery_dir": str(gallery_dir),
        "total_fixtures": total,
        "passed": passed,
        "failed": failed,
        "critical_findings": sum(1 for item in results for finding in item.get("strict_findings", []) if str(finding.get("severity") or "") == "critical"),
        "autofix_proposed_count": sum(1 for item in results if item.get("actual", {}).get("autofix") == "PROPOSED"),
        "autofix_blocked_or_unsupported_count": sum(1 for item in results if item.get("actual", {}).get("autofix") in {"BLOCKED", "NOT_SUPPORTED", "NONE"}),
        "categories": dict(categories),
        "fixtures": results,
        "validation": validation,
    }


def write_gallery_report(result: dict, *, runtime_data_dir: str | Path = DEFAULT_RUNTIME_DATA_DIR) -> dict:
    out_dir = Path(runtime_data_dir) / "manifest_regression_gallery"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "json_path": "", "markdown_path": "", "error": str(exc)}

    json_path = out_dir / "gallery_report.json"
    md_path = out_dir / "gallery_report.md"
    try:
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        md_path.write_text(_build_gallery_markdown(result), encoding="utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "json_path": str(json_path) if json_path.exists() else "",
            "markdown_path": str(md_path) if md_path.exists() else "",
            "error": str(exc),
        }
    return {"ok": True, "json_path": str(json_path), "markdown_path": str(md_path)}


# ---------------------------------------------------------------------------
# Internal fixture execution
# ---------------------------------------------------------------------------


def _run_fixture_record(
    fixture: dict,
    *,
    gallery_dir: str | Path,
    runtime_data_dir: str | Path,
    strict: bool,
    smoke: bool,
    repair_guidance: bool,
    autofix: bool,
) -> dict:
    fixture_id = str(fixture.get("id") or "").strip()
    category = str(fixture.get("category") or "").strip()
    expected_findings = [str(item) for item in (fixture.get("expected_findings") or []) if str(item).strip()]
    expected_strict_status = str(fixture.get("expected_strict_status") or "PASS").strip() or "PASS"
    expected_autofix = _normalize_expected_autofix(fixture.get("expected_autofix"))
    expected_smoke = str(fixture.get("expected_smoke_classification") or "").strip()

    load_result = load_gallery_fixture(fixture, gallery_dir)
    errors: list[str] = []
    warnings: list[str] = []
    manifest: dict[str, Any] | None = load_result.get("manifest") if load_result.get("ok") else None
    parse_exception = load_result.get("exception")

    if not load_result["ok"] and parse_exception is not None:
        strict_result = {
            "ok": False,
            "status": "FAIL",
            "manifest_id": fixture_id,
            "errors": [str(parse_exception)],
            "warnings": [],
            "findings": [_finding("json_parse_error", "error", "manifest", str(parse_exception), "Fix the JSON syntax.", "exception")],
        }
        smoke_result = {"status": "SKIPPED", "classification": "SKIPPED", "reason": "malformed JSON"}
        guidance = explain_manifest_failure(exception=parse_exception)
        autofix_result = {"status": "NOT_SUPPORTED", "proposals": [], "warnings": ["Malformed JSON fixtures are not autofixable."]}
    else:
        strict_result = validate_manifest_strict(
            manifest or {},
            manifest_path=str(Path(gallery_dir) / str(fixture.get("path") or "")),
            active_catalog=True,
            event_routes=_load_event_routes(),
            tool_registry=build_tool_registry(include_external=True, config_path="config/enabled_toolpacks.json"),
        ) if strict else {"ok": True, "status": "PASS", "errors": [], "warnings": [], "findings": []}
        smoke_result = _run_smoke(manifest or {}, gallery_dir=gallery_dir, runtime_data_dir=runtime_data_dir) if smoke else {"status": "SKIPPED", "classification": "SKIPPED", "reason": "smoke disabled"}
        guidance = explain_manifest_failure(
            manifest=manifest or {},
            strict_result=strict_result if strict else None,
            exception=parse_exception if isinstance(parse_exception, Exception) else None,
        ) if repair_guidance and manifest is not None else {"ok": True, "status": "NO_FINDINGS", "severity": "info", "findings": [], "next_action": ""}
        if autofix and manifest is not None:
            autofix_result = propose_manifest_fixes(manifest, guidance=guidance)
        else:
            autofix_result = {"status": "NONE", "proposals": [], "warnings": []}

    strict_findings = list((strict_result or {}).get("findings") or [])
    guidance_findings = list((guidance or {}).get("findings") or [])
    actual_strict_findings = _dedupe_findings(strict_findings)
    actual_guidance_findings = _dedupe_findings(guidance_findings)
    actual_findings = actual_strict_findings
    actual_finding_ids = [str(item.get("id") or "") for item in actual_findings if str(item.get("id") or "").strip()]
    guidance_finding_ids = [str(item.get("id") or "") for item in actual_guidance_findings if str(item.get("id") or "").strip()]
    strict_status = str((strict_result or {}).get("status") or "PASS")
    top_severity = _top_severity(actual_findings)
    smoke_classification = str((smoke_result or {}).get("classification") or "")
    actual_autofix = _classify_autofix(autofix_result)

    matched_expectations = True
    missing_expected = [item for item in expected_findings if item not in actual_finding_ids]
    if expected_strict_status and strict_status != expected_strict_status:
        matched_expectations = False
        errors.append(f"Expected strict status {expected_strict_status}, got {strict_status}")
    if missing_expected:
        matched_expectations = False
        errors.append(f"Missing expected findings: {missing_expected}")
    if expected_smoke and smoke_classification and expected_smoke != smoke_classification:
        matched_expectations = False
        errors.append(f"Expected smoke classification {expected_smoke}, got {smoke_classification}")
    if expected_autofix and actual_autofix != expected_autofix:
        matched_expectations = False
        errors.append(f"Expected autofix {expected_autofix}, got {actual_autofix}")

    if not strict_result.get("ok", True):
        warnings.extend(strict_result.get("warnings") or [])

    return {
        "fixture_id": fixture_id,
        "ok": matched_expectations,
        "category": category,
        "expected": {
            "findings": expected_findings,
            "strict_status": expected_strict_status,
            "autofix": expected_autofix,
            "smoke_classification": expected_smoke or None,
        },
        "actual": {
            "strict_status": strict_status,
            "findings": actual_finding_ids,
            "top_severity": top_severity,
            "smoke_classification": smoke_classification or None,
            "autofix": actual_autofix,
        },
        "guidance_findings": guidance_finding_ids,
        "matched_expectations": matched_expectations,
        "errors": errors,
        "warnings": warnings,
        "strict_findings": strict_findings,
        "repair_guidance": guidance,
        "smoke": smoke_result,
        "autofix_result": autofix_result,
        "path": str(Path(gallery_dir) / str(fixture.get("path") or "")),
    }


def _run_smoke(manifest: dict, *, gallery_dir: str | Path, runtime_data_dir: str | Path) -> dict:
    sample_inputs = _sample_inputs_for_manifest(manifest)
    try:
        return smoke_run_manifest_candidate(
            manifest,
            runtime_data_dir=runtime_data_dir,
            manifest_dir="manifests",
            dry_run=True,
            sample_inputs=sample_inputs,
        )
    except Exception as exc:
        return {"status": "FAIL", "classification": "EXECUTION_FAILED", "errors": [str(exc)], "reason": str(exc), "checks": []}


def _sample_inputs_for_manifest(manifest: dict) -> dict[str, Any]:
    inputs = manifest.get("inputs")
    sample: dict[str, Any] = {}
    if isinstance(inputs, list):
        for item in inputs:
            if isinstance(item, str) and item.strip():
                sample[item.strip()] = _placeholder_for_input(item.strip())
    elif isinstance(inputs, dict):
        for item in list(inputs.get("required") or []) + list(inputs.get("optional") or []):
            if isinstance(item, str) and item.strip():
                sample[item.strip()] = _placeholder_for_input(item.strip())
    sample.update(_sample_inputs_from_manifest(manifest))
    return sample


def _sample_inputs_from_manifest(manifest: dict) -> dict[str, Any]:
    metadata = manifest.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("sample_inputs"), dict):
        return dict(metadata["sample_inputs"])
    if isinstance(manifest.get("sample_inputs"), dict):
        return dict(manifest["sample_inputs"])
    return {}


def _placeholder_for_input(name: str) -> Any:
    lower = name.lower()
    if any(token in lower for token in ("email", "message", "text", "body", "reply")):
        return f"sample {name}"
    if any(token in lower for token in ("id", "ref", "code", "key")):
        return f"{name}_sample"
    if any(token in lower for token in ("count", "limit", "days", "amount")):
        return 1
    return f"sample_{name}"


def _smoke_findings(smoke_result: dict) -> list[dict]:
    if not isinstance(smoke_result, dict):
        return []
    classification = str(smoke_result.get("classification") or "").strip()
    if not classification or smoke_result.get("status") != "FAIL":
        return []
    result = explain_manifest_failure(smoke_result=smoke_result)
    findings = result.get("findings") or []
    return [finding for finding in findings if isinstance(finding, dict)]


def _classify_autofix(result: dict) -> str:
    proposals = list(result.get("proposals") or [])
    if not proposals:
        warnings = [str(item) for item in (result.get("warnings") or [])]
        if warnings and any("malformed" in item.lower() for item in warnings):
            return "NOT_SUPPORTED"
        return "NONE"
    if any(p.get("status") == "PROPOSED" and p.get("risk") == "low" for p in proposals):
        return "PROPOSED"
    if any(p.get("status") == "NOT_SUPPORTED" for p in proposals):
        return "NOT_SUPPORTED"
    return "BLOCKED"


def _normalize_expected_autofix(value: Any) -> str:
    if isinstance(value, str):
        upper = value.strip().upper()
        return upper if upper in ALLOWED_AUTOFIX_VALUES else "NONE"
    if isinstance(value, dict):
        if value.get("supported") is False:
            return str(value.get("status") or "NOT_SUPPORTED")
        if value.get("supported") is True:
            return str(value.get("status") or "PROPOSED")
    return "NONE"


def _top_severity(findings: list[dict]) -> str:
    order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    if not findings:
        return "info"
    return min((str(f.get("severity") or "info") for f in findings), key=lambda sev: order.get(sev, 99))


def _dedupe_findings(findings: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        key = (str(finding.get("id") or ""), str(finding.get("location") or ""), str(finding.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result


def _finding(finding_id: str, severity: str, location: str, message: str, suggested_fix: str, source: str) -> dict:
    return {
        "id": finding_id,
        "severity": severity,
        "location": location,
        "message": message,
        "suggested_fix": suggested_fix,
        "example": "",
        "source": source,
    }


def _load_event_routes() -> dict | None:
    path = Path("config/event_routes.json")
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _get_fixture_by_id(fixture_id: str, gallery_dir: str | Path) -> dict:
    fixtures = iter_gallery_fixtures(gallery_dir)
    match = next((fixture for fixture in fixtures if str(fixture.get("id") or "") == fixture_id), None)
    if match is None:
        raise KeyError(f"Fixture '{fixture_id}' not found in gallery index.")
    return match


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _build_gallery_markdown(result: dict) -> str:
    lines = [
        "# Manifest Regression Gallery Report",
        "",
        "## Summary",
        "",
        f"- Total fixtures: {result.get('total_fixtures', 0)}",
        f"- Passed expectations: {result.get('passed', 0)}",
        f"- Failed expectations: {result.get('failed', 0)}",
        f"- Categories covered: {len(result.get('categories') or {})}",
        f"- Critical findings: {result.get('critical_findings', 0)}",
        f"- Autofix proposed count: {result.get('autofix_proposed_count', 0)}",
        f"- Autofix blocked/not supported count: {result.get('autofix_blocked_or_unsupported_count', 0)}",
        "",
        "## Category Summary",
        "",
        "| Category | Total | Passed | Failed |",
        "|---|---:|---:|---:|",
    ]
    for category, data in sorted((result.get("categories") or {}).items()):
        lines.append(f"| {category} | {data.get('total', 0)} | {data.get('passed', 0)} | {data.get('failed', 0)} |")

    failed = [item for item in result.get("fixtures") or [] if not item.get("matched_expectations")]
    lines.extend(["", "## Failed Fixtures", ""])
    if failed:
        for item in failed:
            lines.append(f"- `{item.get('fixture_id', '')}`: {', '.join(item.get('errors') or [])}")
    else:
        lines.append("- None")

    lines.extend(["", "## Full Fixture Results", "", "| Fixture | Category | Strict | Smoke | Autofix | Matched |", "|---|---|---|---|---|---|"])
    for item in result.get("fixtures") or []:
        lines.append(
            f"| {item.get('fixture_id', '')} | {item.get('category', '')} | {item.get('actual', {}).get('strict_status', '')} | "
            f"{item.get('actual', {}).get('smoke_classification', '') or ''} | {item.get('actual', {}).get('autofix', '')} | "
            f"{'yes' if item.get('matched_expectations') else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)
