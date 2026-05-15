from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.manifest_loader import load_manifest
from src.generated_manifest_smoke_runner import (
    FAILING_CLASSIFICATIONS,
    PASSING_CLASSIFICATIONS,
    smoke_run_manifest_file,
)
from src.manifest_authoring_feedback import explain_manifest_failure
from src.manifest_autofix import propose_manifest_fixes


_SMOKE_SKIPPED_CLASSIFICATION = "NOT_RUN"


def run_manifest_health_check(
    *,
    manifest_dir: str | Path = "manifests",
    runtime_data_dir: str | Path = "runtime_data",
    include_smoke: bool = True,
    smoke_limit: int | None = None,
) -> dict:
    """Run a deterministic health check across the active manifest catalog."""
    manifest_dir_path = Path(manifest_dir)
    smoke_attempts = 0
    items: list[dict] = []

    for manifest_path in _iter_active_manifest_paths(manifest_dir_path):
        can_attempt_smoke = include_smoke and (smoke_limit is None or smoke_attempts < smoke_limit)
        item = check_manifest_health(
            manifest_path,
            runtime_data_dir=runtime_data_dir,
            include_smoke=can_attempt_smoke,
        )
        if include_smoke and item.get("smoke", {}).get("status") in {"PASS", "FAIL"}:
            smoke_attempts += 1
        elif include_smoke and smoke_limit is not None and smoke_attempts >= smoke_limit:
            item = _replace_smoke_with_limit_skip(item)
        items.append(item)

    summary = summarize_manifest_health(items)
    return {
        "ok": True,
        "status": _overall_status(summary),
        "generated_at": _utc_now(),
        "manifest_dir": str(manifest_dir),
        "summary": summary,
        "manifests": items,
    }


def check_manifest_health(
    manifest_path: str | Path,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    include_smoke: bool = True,
) -> dict:
    """Check one manifest file without mutating it."""
    path = Path(manifest_path)
    raw: dict[str, Any] | None = None
    parse_exception: Exception | None = None

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        raw = parsed if isinstance(parsed, dict) else None
        if raw is None:
            raise ValueError("Manifest root must be a JSON object.")
    except Exception as exc:
        parse_exception = exc

    loaded_manifest = None
    validation_errors: list[str] = []
    if parse_exception is None:
        try:
            loaded_manifest = load_manifest(path)
        except Exception as exc:
            validation_errors.append(str(exc))
    else:
        validation_errors.append(str(parse_exception))

    validation = {
        "ok": loaded_manifest is not None,
        "errors": validation_errors,
    }
    analysis_manifest = _analysis_manifest(raw, loaded_manifest)

    initial_guidance = explain_manifest_failure(
        manifest=analysis_manifest,
        validation_result=validation if not validation["ok"] else None,
        exception=parse_exception,
    )

    smoke = _build_smoke_result(
        path=path,
        raw=raw,
        validation=validation,
        guidance=initial_guidance,
        runtime_data_dir=runtime_data_dir,
        include_smoke=include_smoke,
    )

    guidance = explain_manifest_failure(
        manifest=analysis_manifest,
        validation_result=validation if not validation["ok"] else None,
        smoke_result=smoke if smoke["status"] == "FAIL" else None,
        exception=parse_exception,
    )
    repair_guidance = _summarize_guidance(guidance)

    autofix_result = propose_manifest_fixes(analysis_manifest or {}, guidance=guidance)
    autofix = _summarize_autofix(autofix_result)

    manifest_id = _manifest_id(raw, path)
    name = str((raw or {}).get("name") or path.stem)
    health = _classify_health(validation, repair_guidance, smoke)
    manual_fix_required = _manual_fix_required(repair_guidance, autofix)
    repairable = autofix["low_risk_applyable"] > 0

    return {
        "manifest_id": manifest_id,
        "name": name,
        "path": str(path),
        "health": health,
        "validation": validation,
        "repair_guidance": repair_guidance,
        "smoke": smoke,
        "autofix": autofix,
        "repairable": repairable,
        "manual_fix_required": manual_fix_required,
        "next_action": _recommended_next_action(
            health=health,
            validation=validation,
            repair_guidance=repair_guidance,
            smoke=smoke,
            autofix=autofix,
            manual_fix_required=manual_fix_required,
        ),
    }


def write_manifest_health_report(
    result: dict,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    report_name: str = "manifest_health_report",
) -> dict:
    """Write JSON and Markdown catalog health reports."""
    out_dir = Path(runtime_data_dir) / "manifest_health"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "json_path": "", "markdown_path": "", "error": str(exc)}

    json_path = out_dir / f"{report_name}.json"
    markdown_path = out_dir / f"{report_name}.md"
    try:
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        markdown_path.write_text(_build_markdown_report(result), encoding="utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "json_path": str(json_path) if json_path.exists() else "",
            "markdown_path": str(markdown_path) if markdown_path.exists() else "",
            "error": str(exc),
        }

    return {
        "ok": True,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def summarize_manifest_health(items: list[dict]) -> dict:
    """Pure aggregate helper used by tests and report rendering."""
    return {
        "total": len(items),
        "healthy": sum(1 for item in items if item.get("health") == "HEALTHY"),
        "warnings": sum(1 for item in items if item.get("health") == "WARNING"),
        "failed": sum(1 for item in items if item.get("health") == "FAILED"),
        "validation_passed": sum(1 for item in items if item.get("validation", {}).get("ok")),
        "validation_failed": sum(1 for item in items if not item.get("validation", {}).get("ok")),
        "smoke_passed": sum(1 for item in items if item.get("smoke", {}).get("status") == "PASS"),
        "smoke_failed": sum(1 for item in items if item.get("smoke", {}).get("status") == "FAIL"),
        "smoke_skipped": sum(1 for item in items if item.get("smoke", {}).get("status") == "SKIPPED"),
        "repairable": sum(1 for item in items if bool(item.get("repairable"))),
        "manual_fix_required": sum(1 for item in items if bool(item.get("manual_fix_required"))),
        "critical": sum(1 for item in items if item.get("health") == "CRITICAL"),
    }


def _iter_active_manifest_paths(manifest_dir: Path) -> list[Path]:
    paths = sorted(manifest_dir.glob("*.manifest.json")) if manifest_dir.is_dir() else []
    if _is_default_manifest_dir(manifest_dir):
        extra_dir = Path("config/manifests")
        if extra_dir.is_dir():
            paths.extend(sorted(extra_dir.glob("*.json")))
    return paths


def _build_smoke_result(
    *,
    path: Path,
    raw: dict[str, Any] | None,
    validation: dict,
    guidance: dict,
    runtime_data_dir: str | Path,
    include_smoke: bool,
) -> dict:
    if not validation.get("ok"):
        return _skipped_smoke("manifest failed to load")

    if _guidance_has_severity(guidance, "critical"):
        return _skipped_smoke("critical repair finding")

    if not include_smoke:
        return _skipped_smoke("smoke disabled or smoke_limit reached")

    required_inputs = _required_inputs(raw or {})
    sample_inputs = _sample_inputs(raw or {})
    missing_inputs = [item for item in required_inputs if item not in sample_inputs]
    if missing_inputs:
        return _skipped_smoke(f"required sample inputs missing: {', '.join(missing_inputs)}")

    trigger_type = _trigger_type(raw or {})
    if trigger_type == "event" and not sample_inputs and not _sample_event(raw or {}):
        return _skipped_smoke("event trigger has no sample event/input")

    if _requires_external_setup(raw or {}, path):
        return _skipped_smoke("manifest requires external/live setup")

    result = smoke_run_manifest_file(path, runtime_data_dir=runtime_data_dir)
    classification = str(result.get("classification") or "")
    if result.get("ok") and classification in PASSING_CLASSIFICATIONS:
        return {
            "status": "PASS",
            "classification": classification,
            "reason": "",
            "state": str(result.get("state") or ""),
        }
    return {
        "status": "FAIL",
        "classification": classification or "EXECUTION_FAILED",
        "reason": "; ".join(str(item) for item in (result.get("errors") or [])),
        "state": str(result.get("state") or ""),
    }


def _summarize_guidance(guidance: dict) -> dict:
    findings = list(guidance.get("findings") or [])
    return {
        "status": str(guidance.get("status") or "NO_FINDINGS"),
        "severity": str(guidance.get("severity") or "info"),
        "finding_count": len(findings),
        "top_findings": [str(item.get("id") or "") for item in findings[:3]],
        "findings": findings,
    }


def _summarize_autofix(result: dict) -> dict:
    proposals = list(result.get("proposals") or [])
    supported = [item for item in proposals if item.get("status") == "PROPOSED"]
    unsupported = [item for item in proposals if item.get("status") != "PROPOSED"]
    low_risk = [item for item in supported if item.get("risk") == "low"]
    return {
        "proposal_count": int(result.get("proposal_count", len(proposals))),
        "supported_count": int(result.get("supported_count", len(supported))),
        "unsupported_count": int(result.get("unsupported_count", len(unsupported))),
        "low_risk_applyable": len(low_risk),
        "top_supported": [str(item.get("finding_id") or "") for item in supported[:3]],
        "top_unsupported": [str(item.get("finding_id") or "") for item in unsupported[:3]],
        "proposals": proposals,
    }


def _classify_health(validation: dict, repair_guidance: dict, smoke: dict) -> str:
    findings = list(repair_guidance.get("findings") or [])
    severities = {str(item.get("severity") or "") for item in findings}
    finding_ids = {str(item.get("id") or "") for item in findings}
    smoke_classification = str(smoke.get("classification") or "")

    if "live_execution_enabled" in finding_ids or "critical" in severities:
        return "CRITICAL"
    if not validation.get("ok"):
        return "FAILED"
    if "error" in severities:
        return "FAILED"
    if smoke.get("status") == "FAIL" and smoke_classification in FAILING_CLASSIFICATIONS:
        return "FAILED"
    if smoke.get("status") == "SKIPPED":
        return "SMOKE_SKIPPED"
    if "warning" in severities:
        return "WARNING"
    return "HEALTHY"


def _manual_fix_required(repair_guidance: dict, autofix: dict) -> bool:
    findings = list(repair_guidance.get("findings") or [])
    has_error_or_critical = any(str(item.get("severity") or "") in {"error", "critical"} for item in findings)
    return has_error_or_critical and autofix.get("low_risk_applyable", 0) == 0


def _recommended_next_action(
    *,
    health: str,
    validation: dict,
    repair_guidance: dict,
    smoke: dict,
    autofix: dict,
    manual_fix_required: bool,
) -> str:
    finding_ids = set(repair_guidance.get("top_findings") or [])
    if "live_execution_enabled" in finding_ids or health == "CRITICAL":
        return "Disable live execution."
    if not validation.get("ok"):
        return "Fix JSON/schema before smoke testing."
    if autofix.get("low_risk_applyable", 0) > 0:
        return "Open Auto-Fix Preview."
    if manual_fix_required:
        return "Manual fix required."
    if smoke.get("status") == "SKIPPED":
        return "Run smoke test manually with sample inputs."
    if health == "WARNING":
        return "Review warning findings."
    if repair_guidance.get("finding_count", 0) > 0:
        return "Open Repair Guidance."
    return "No action required."


def _replace_smoke_with_limit_skip(item: dict) -> dict:
    if item.get("smoke", {}).get("status") != "SKIPPED":
        return item
    if item.get("smoke", {}).get("reason") != "smoke disabled or smoke_limit reached":
        return item
    copied = dict(item)
    copied["smoke"] = _skipped_smoke("smoke_limit reached")
    copied["health"] = _classify_health(copied.get("validation", {}), copied.get("repair_guidance", {}), copied["smoke"])
    copied["next_action"] = _recommended_next_action(
        health=copied["health"],
        validation=copied.get("validation", {}),
        repair_guidance=copied.get("repair_guidance", {}),
        smoke=copied["smoke"],
        autofix=copied.get("autofix", {}),
        manual_fix_required=bool(copied.get("manual_fix_required")),
    )
    return copied


def _build_markdown_report(result: dict) -> str:
    summary = result.get("summary") or {}
    lines = [
        "# Manifest Health Report",
        "",
        f"Generated: {result.get('generated_at', '')}",
        "",
        f"Verdict: {result.get('status', 'UNKNOWN')}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total manifests | {summary.get('total', 0)} |",
        f"| Healthy | {summary.get('healthy', 0)} |",
        f"| Warnings | {summary.get('warnings', 0)} |",
        f"| Failed | {summary.get('failed', 0)} |",
        f"| Repairable | {summary.get('repairable', 0)} |",
        f"| Manual fix required | {summary.get('manual_fix_required', 0)} |",
        f"| Critical | {summary.get('critical', 0)} |",
        "",
        "## Manifest Results",
        "",
        "| Health | Manifest | Validation | Smoke | Repairable | Top Findings | Next Action |",
        "|---|---|---|---|---:|---|---|",
    ]
    for item in result.get("manifests") or []:
        lines.append(
            "| {health} | {manifest_id} | {validation} | {smoke} | {repairable} | {findings} | {next_action} |".format(
                health=item.get("health", ""),
                manifest_id=item.get("manifest_id", ""),
                validation="PASS" if item.get("validation", {}).get("ok") else "FAIL",
                smoke=item.get("smoke", {}).get("status", ""),
                repairable=item.get("autofix", {}).get("low_risk_applyable", 0),
                findings=", ".join(item.get("repair_guidance", {}).get("top_findings") or []),
                next_action=item.get("next_action", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _overall_status(summary: dict) -> str:
    if summary.get("failed", 0) or summary.get("critical", 0) or summary.get("validation_failed", 0):
        return "HAS_FAILURES"
    if summary.get("warnings", 0):
        return "HAS_WARNINGS"
    return "HEALTHY"


def _manifest_id(raw: dict[str, Any] | None, path: Path) -> str:
    if isinstance(raw, dict):
        value = raw.get("manifest_id", raw.get("id"))
        if value:
            return str(value)
    return path.name.replace(".manifest.json", "")


def _analysis_manifest(raw: dict[str, Any] | None, loaded_manifest: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return raw
    if loaded_manifest is None or not _is_custom_event_manifest(raw):
        return raw

    completion = dict(getattr(loaded_manifest, "completion", {}) or {})
    if "success_outputs" not in completion and isinstance(completion.get("required_outputs"), list):
        completion["success_outputs"] = list(completion.get("required_outputs") or [])

    steps = []
    for step in getattr(loaded_manifest, "steps", []) or []:
        steps.append(
            {
                "id": str(getattr(step, "id", "") or ""),
                "command": str(getattr(step, "command", "") or ""),
            }
        )

    return {
        "manifest_id": str(getattr(loaded_manifest, "manifest_id", "") or ""),
        "name": str(getattr(loaded_manifest, "name", "") or ""),
        "version": getattr(loaded_manifest, "version", 1),
        "trigger": dict(getattr(loaded_manifest, "trigger", {}) or {}),
        "inputs": list(getattr(loaded_manifest, "inputs", []) or []),
        "steps": steps,
        "validations": list(getattr(loaded_manifest, "validations", []) or []),
        "completion": completion,
        "live_execution": dict(getattr(loaded_manifest, "live_execution", {}) or {}),
    }


def _required_inputs(raw: dict[str, Any]) -> list[str]:
    inputs = raw.get("inputs")
    if isinstance(inputs, list):
        result: list[str] = []
        for item in inputs:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict) and item.get("required", True) and item.get("name"):
                result.append(str(item["name"]).strip())
        return result
    if isinstance(inputs, dict):
        required = inputs.get("required") or []
        if isinstance(required, list):
            return [str(item).strip() for item in required if str(item).strip()]
    return []


def _sample_inputs(raw: dict[str, Any]) -> dict[str, Any]:
    direct = raw.get("sample_inputs")
    if isinstance(direct, dict):
        return direct
    metadata = raw.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("sample_inputs"), dict):
        return dict(metadata["sample_inputs"])
    return {}


def _sample_event(raw: dict[str, Any]) -> dict[str, Any]:
    direct = raw.get("sample_event")
    if isinstance(direct, dict):
        return direct
    metadata = raw.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("sample_event"), dict):
        return dict(metadata["sample_event"])
    return {}


def _trigger_type(raw: dict[str, Any]) -> str:
    trigger = raw.get("trigger")
    if isinstance(trigger, dict):
        return str(trigger.get("type") or "").strip().lower()
    return str(raw.get("trigger_type") or "").strip().lower()


def _requires_external_setup(raw: dict[str, Any], path: Path) -> bool:
    if bool(raw.get("requires_external_setup")) or bool(raw.get("health_skip_smoke")):
        return True
    metadata = raw.get("metadata")
    if isinstance(metadata, dict) and (
        bool(metadata.get("requires_external_setup")) or bool(metadata.get("health_skip_smoke"))
    ):
        return True
    manifest_id = str(raw.get("manifest_id") or raw.get("id") or "")
    return manifest_id.startswith("live.") or path.name.startswith("live_")


def _guidance_has_severity(guidance: dict, severity: str) -> bool:
    return any(str(item.get("severity") or "") == severity for item in (guidance.get("findings") or []))


def _skipped_smoke(reason: str) -> dict:
    return {
        "status": "SKIPPED",
        "classification": _SMOKE_SKIPPED_CLASSIFICATION,
        "reason": reason,
        "state": "",
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_default_manifest_dir(manifest_dir: Path) -> bool:
    try:
        return manifest_dir.resolve() == Path("manifests").resolve()
    except Exception:
        return str(manifest_dir) == "manifests"


def _is_custom_event_manifest(raw: dict[str, Any]) -> bool:
    return "id" in raw and "trigger_type" in raw and "steps" in raw and "manifest_id" not in raw
