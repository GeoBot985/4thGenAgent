from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from runtime.event_source_route_alignment import validate_event_source_route_alignment
from src.manifest_health import run_manifest_health_check, write_manifest_health_report
from src.operator_cross_workflow_demo import get_demo_pack

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THRESHOLD = 90
AREA_BAND_WARN = 75
AREA_BAND_PASS = 90


def build_readiness_scorecard(
    *,
    runtime_data_dir: str = "runtime_data",
    strict: bool = True,
    threshold: int = DEFAULT_THRESHOLD,
) -> dict:
    runtime_root = Path(runtime_data_dir)
    generated_at = _now()
    area_results = _collect_area_results(runtime_root, threshold=threshold)
    area_items = [area_results[area_id] for area_id in AREA_ORDER]
    overall_score = round(sum(float(area.get("score", 0.0)) for area in area_items) / len(area_items), 1) if area_items else 0.0
    blocking_areas = [area["area_id"] for area in area_items if float(area.get("score", 0.0)) < threshold]
    warnings = [f"{area['area_id']}: {area['label']} scored {area['score']:.1f}%" for area in area_items if area.get("status") == "WARN"]
    errors = [f"{area['area_id']}: {area['label']} scored {area['score']:.1f}%" for area in area_items if area.get("status") in {"FAIL", "NOT_ASSESSED"}]
    result = {
        "ok": not blocking_areas,
        "status": _overall_status(area_items, threshold=threshold),
        "threshold": int(threshold),
        "overall_score": overall_score,
        "generated_at": generated_at,
        "areas": {area["area_id"]: area for area in area_items},
        "blocking_areas": blocking_areas,
        "warnings": warnings,
        "errors": errors,
        "report_paths": {},
        "strict": bool(strict),
    }
    report_paths = write_readiness_scorecard(result, runtime_data_dir=runtime_root)
    result["report_paths"] = report_paths
    result["ok"] = not blocking_areas
    if strict and blocking_areas:
        result["status"] = "FAIL"
    return result


def write_readiness_scorecard(result: dict, *, runtime_data_dir: str | Path = "runtime_data") -> dict[str, str]:
    runtime_root = Path(runtime_data_dir)
    readiness_dir = runtime_root / "readiness"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    json_path = readiness_dir / "readiness_scorecard.json"
    markdown_path = readiness_dir / "readiness_scorecard.md"
    html_path = readiness_dir / "readiness_scorecard.html"

    payload = _serialize_result(result)
    report_paths = {
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "html_path": str(html_path),
    }
    payload["report_paths"] = report_paths
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown = render_readiness_scorecard_markdown(payload)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(render_readiness_scorecard_html(payload, markdown), encoding="utf-8")
    return report_paths


def render_readiness_scorecard_markdown(result: dict) -> str:
    areas = result.get("areas", {}) if isinstance(result, dict) else {}
    lines = [
        "# 90% Readiness Scorecard",
        "",
        "## Executive Summary",
        "",
        "This scorecard measures controlled portfolio/demo readiness. It does not certify production deployment readiness.",
        "",
        f"- Generated: {result.get('generated_at', '')}",
        f"- Overall Score: {result.get('overall_score', 0)}",
        f"- Threshold: {result.get('threshold', DEFAULT_THRESHOLD)}",
        f"- Status: {result.get('status', '')}",
        "",
        "## Overall Result",
        "",
        f"- OK: {str(bool(result.get('ok'))).lower()}",
        f"- Blocking Areas: {', '.join(result.get('blocking_areas', [])) or 'none'}",
        "",
        "## Area Scores",
        "",
    ]
    for area_id in AREA_ORDER:
        area = areas.get(area_id, {})
        lines.append(f"- {area.get('label', area_id)} ({area_id}): {area.get('score', 0)}% [{area.get('status', '')}]")
    lines.extend(
        [
            "",
            "## Blocking Areas",
            "",
            ", ".join(result.get("blocking_areas", [])) or "None",
            "",
            "## Detailed Checks",
            "",
        ]
    )
    for area_id in AREA_ORDER:
        area = areas.get(area_id, {})
        lines.append(f"### {area.get('label', area_id)}")
        for check in area.get("checks", []):
            if not isinstance(check, dict):
                continue
            lines.append(
                f"- [{check.get('status', '')}] {check.get('label', check.get('check_id', ''))}: {check.get('message', '')}"
            )
        lines.append("")
    lines.extend(
        [
            "## Evidence",
            "",
        ]
    )
    for area_id in AREA_ORDER:
        area = areas.get(area_id, {})
        for evidence in area.get("evidence", []):
            lines.append(f"- {area_id}: {evidence}")
    lines.extend(
        [
            "",
            "## Known Limitations",
            "",
            "This scorecard reflects the controlled demo and portfolio-ready state of the repository. It is not a declaration of unsupervised production readiness.",
            "",
            "## Recommended Next Specs",
            "",
            "- Spec 114 or later: targeted production-readiness hardening where gaps remain.",
        ]
    )
    return "\n".join(lines)


def render_readiness_scorecard_html(result: dict, markdown: str) -> str:
    areas = result.get("areas", {}) if isinstance(result, dict) else {}
    rows = []
    for area_id in AREA_ORDER:
        area = areas.get(area_id, {})
        rows.append(
            "<tr>"
            f"<td>{escape(str(area.get('label', area_id)))}</td>"
            f"<td>{escape(str(area.get('score', 0)))}</td>"
            f"<td>{escape(str(area.get('status', '')))}</td>"
            f"<td>{escape(', '.join(area.get('gaps', [])) or '—')}</td>"
            f"<td>{escape(', '.join(area.get('recommended_next_specs', [])) or '—')}</td>"
            "</tr>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>90% Readiness Scorecard</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.5}"
        "table{border-collapse:collapse;width:100%;margin:16px 0}"
        "th,td{border:1px solid #ccc;padding:8px;text-align:left}"
        "th{background:#f0f0f0}"
        ".card{border:1px solid #ddd;border-radius:8px;padding:12px;background:#fafafa;margin:8px 0}</style>"
        "</head><body>"
        "<h1>90% Readiness Scorecard</h1>"
        "<div class='card'>"
        f"<strong>Overall Score:</strong> {escape(str(result.get('overall_score', 0)))}<br>"
        f"<strong>Threshold:</strong> {escape(str(result.get('threshold', DEFAULT_THRESHOLD)))}<br>"
        f"<strong>Status:</strong> {escape(str(result.get('status', '')))}<br>"
        f"<strong>Blocking Areas:</strong> {escape(', '.join(result.get('blocking_areas', [])) or 'none')}"
        "</div>"
        "<table><thead><tr><th>Area</th><th>Score</th><th>Status</th><th>Gaps</th><th>Recommended Next Specs</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        "<h2>Known Limitations</h2>"
        "<p>This scorecard measures controlled portfolio/demo readiness. It does not certify production deployment readiness.</p>"
        "<h2>Rendered Markdown</h2><pre style='white-space:pre-wrap'>"
        + escape(markdown)
        + "</pre></body></html>"
    )


def _collect_area_results(runtime_root: Path, *, threshold: int) -> dict[str, dict[str, Any]]:
    readiness_dir = runtime_root / "readiness"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    areas = {
        "core_architecture": _evaluate_area(
            "core_architecture",
            "Core Architecture",
            threshold,
            [
                _text_absence_check(
                    "orchestrator_has_no_domain_logic",
                    "Orchestrator has no domain logic",
                    ROOT / "runtime" / "orchestrator.py",
                    forbidden_terms=[
                        "supplier_invoice",
                        "google_workspace",
                        "procurement_low_stock_reorder",
                        "accounting_payment_reconciliation",
                        "order.validate_new",
                    ],
                    source="runtime/orchestrator.py",
                ),
                _file_function_check("taskframe_contract_exists", "TaskFrame contract exists", ROOT / "runtime" / "taskframe.py", ["TaskFrame"], source="runtime/taskframe.py"),
                _file_function_check("tool_result_contract_exists", "Tool result contract exists", ROOT / "runtime" / "tool_result_contract.py", ["build_tool_evidence", "validate_tool_result_contract"], source="runtime/tool_result_contract.py"),
                _text_contains_check("approval_model_exists", "Approval model exists", ROOT / "src" / "operator_approval_actions.py", ["approve_pending_action", "reject_pending_action"], source="src/operator_approval_actions.py"),
                _text_contains_check("llm_is_bounded_tool_not_controller", "LLM is bounded tool, not controller", ROOT / "docs" / "portfolio_summary.md", ["bounded LLM", "LLM"], source="docs/portfolio_summary.md"),
            ],
            recommended_next_specs=["Spec 114: production hardening if needed"],
        ),
        "manifest_runtime": _evaluate_area(
            "manifest_runtime",
            "Manifest Runtime",
            threshold,
            [
                _manifest_health_check(readiness_dir),
                _cli_text_check("strict_manifest_contract_available", "Strict manifest contract available", ROOT / "src" / "taskframe_cli.py", ["validate-strict"], source="src/taskframe_cli.py"),
                _file_exists_check("completion_gate_consistency_tests_pass", "Completion gate consistency tests exist", ROOT / "tests" / "test_completion_gate_consistency.py", source="tests/test_completion_gate_consistency.py"),
                _file_exists_check("manifest_regression_gallery_exists", "Manifest regression gallery exists", ROOT / "src" / "manifest_regression_gallery.py", source="src/manifest_regression_gallery.py"),
                _file_function_check("manifest_repair_guidance_available", "Manifest repair guidance available", ROOT / "src" / "manifest_authoring_feedback.py", ["explain_manifest_failure"], source="src/manifest_authoring_feedback.py"),
            ],
            recommended_next_specs=["Spec 107+ for further manifest hardening"],
        ),
        "event_routing": _evaluate_area(
            "event_routing",
            "Event Routing",
            threshold,
            [
                _route_alignment_check(),
                _file_exists_check("event_queue_available", "Event queue available", ROOT / "runtime" / "event_queue.py", source="runtime/event_queue.py"),
                _cli_text_check("event_replay_available", "Event replay available", ROOT / "src" / "taskframe_cli.py", ["replay-dry-run"], source="src/taskframe_cli.py"),
                _file_text_contains_check("duplicate_event_detection_available", "Duplicate event detection available", ROOT / "runtime" / "event_queue.py", ["DUPLICATE_EVENT"], source="runtime/event_queue.py"),
                _file_exists_check("event_source_contracts_exist", "Event source contracts exist", ROOT / "runtime" / "event_source_registry.py", source="runtime/event_source_registry.py"),
            ],
            recommended_next_specs=["Spec 114: routing observability"],
        ),
        "business_workflows": _evaluate_area(
            "business_workflows",
            "Business Workflows",
            threshold,
            [
                _scenario_check("customer_workflow_available", "Customer workflow available", "customer_status_approve_execute_dry_run", source="src/operator_scenarios.py"),
                _scenario_check("procurement_workflow_available", "Procurement workflow available", "procurement_low_stock_approve_execute_dry_run", source="src/operator_scenarios.py"),
                _scenario_check("accounting_workflow_available", "Accounting workflow available", "accounting_payment_reconciliation_approve_execute_dry_run", source="src/operator_scenarios.py"),
                _manifest_exists_check("order_management_workflow_available", "Order management workflow available", ROOT / "manifests" / "order.validate_new.manifest.json", source="manifests/order.validate_new.manifest.json"),
                _manifest_exists_check("supplier_invoice_matching_available", "Supplier invoice matching available", ROOT / "manifests" / "supplier_invoice_match.manifest.json", source="manifests/supplier_invoice_match.manifest.json"),
                _demo_pack_check("cross_workflow_demo_v2_available", "Cross-workflow demo v2 available", "cross_workflow_business_demo_v2", source="src/operator_cross_workflow_demo.py"),
            ],
            recommended_next_specs=["Spec 114+: scenario expansion or portfolio refinement"],
        ),
        "tooling": _evaluate_area(
            "tooling",
            "Tooling",
            threshold,
            [
                _file_function_check("tool_result_contract_enforced", "Tool result contract enforced", ROOT / "runtime" / "tool_result_contract.py", ["validate_tool_result_contract"], source="runtime/tool_result_contract.py"),
                _file_exists_check("external_toolpack_lifecycle_available", "External toolpack lifecycle available", ROOT / "src" / "toolpack_lifecycle.py", source="src/toolpack_lifecycle.py"),
                _manifest_text_contains_check("google_workspace_read_only_pack_available", "Google Workspace read-only pack available", ROOT / "tool_packs" / "google_workspace" / "toolpack.json", ["read_only_external_api", "google_workspace"], source="tool_packs/google_workspace/toolpack.json"),
                _file_exists_check("tool_governance_runtime_enforced", "Tool governance runtime enforced", ROOT / "runtime" / "tool_governance.py", source="runtime/tool_governance.py"),
                _file_exists_check("tool_health_checks_available", "Tool health checks available", ROOT / "runtime" / "tool_health.py", source="runtime/tool_health.py"),
            ],
            recommended_next_specs=["Spec 114+: continue governance hardening"],
        ),
        "release_verification": _evaluate_area(
            "release_verification",
            "Release Verification",
            threshold,
            [
                _file_exists_check("release_candidate_verifier_exists", "Release candidate verifier exists", ROOT / "tools" / "run_release_candidate_verification.py", source="tools/run_release_candidate_verification.py"),
                _file_exists_check("golden_demo_verification_exists", "Golden demo verification exists", ROOT / "scripts" / "run_golden_demo.py", source="scripts/run_golden_demo.py"),
                _file_text_contains_check("tool_governance_release_check_exists", "Tool governance release check exists", ROOT / "tools" / "run_release_candidate_verification.py", ["toolpack_governance"], source="tools/run_release_candidate_verification.py"),
                _file_text_contains_check("manifest_health_release_check_exists", "Manifest health release check exists", ROOT / "tools" / "run_release_candidate_verification.py", ["manifest_health_cli_strict"], source="tools/run_release_candidate_verification.py"),
                _file_text_contains_check("cross_workflow_story_v2_check_exists", "Cross-workflow story v2 check exists", ROOT / "tools" / "run_release_candidate_verification.py", ["cross_workflow_story_v2"], source="tools/run_release_candidate_verification.py"),
            ],
            recommended_next_specs=["Spec 114+: deeper production release automation"],
        ),
        "production_readiness": _evaluate_area(
            "production_readiness",
            "Production Readiness",
            threshold,
            [
                _runtime_profile_check(),
                _file_text_contains_check("live_side_effects_blocked_by_default", "Live side effects blocked by default", ROOT / "docs" / "known_limitations.md", ["live execution is disabled by default", "approval-gated"], source="docs/known_limitations.md"),
                _file_text_contains_check("controlled_live_read_profile_defined", "Controlled live-read profile defined", ROOT / "config" / "runtime_profile.json", ["governance_enforced", "demo"], source="config/runtime_profile.json"),
                _file_text_contains_check("secrets_hygiene_checks_exist", "Secrets hygiene checks exist", ROOT / "tools" / "run_release_candidate_verification.py", ["config_secrets_hygiene"], source="tools/run_release_candidate_verification.py"),
                _file_exists_check("config_profiles_exist", "Config profiles exist", ROOT / "src" / "config_profiles.py", source="src/config_profiles.py"),
                _file_text_contains_check("known_limitations_documented", "Known limitations documented", ROOT / "docs" / "known_limitations.md", ["not production claims", "live execution is disabled by default"], source="docs/known_limitations.md"),
            ],
            recommended_next_specs=["Spec 114+: production deployment hardening"],
        ),
    }
    return areas


def _evaluate_area(
    area_id: str,
    label: str,
    threshold: int,
    checks: list[dict[str, Any]],
    *,
    recommended_next_specs: list[str],
) -> dict[str, Any]:
    total_weight = sum(float(check.get("score_weight", 1) or 1) for check in checks)
    if total_weight <= 0:
        return {
            "area_id": area_id,
            "label": label,
            "score": 0.0,
            "status": "NOT_ASSESSED",
            "threshold": int(threshold),
            "checks": [],
            "evidence": [],
            "gaps": ["No checks available."],
            "recommended_next_specs": recommended_next_specs,
        }
    earned = sum(float(check.get("earned", 0.0) or 0.0) for check in checks)
    score = round((earned / total_weight) * 100.0, 1)
    status = _area_status(score, has_checks=True)
    evidence = []
    gaps = []
    for check in checks:
        evidence.extend(list(check.get("evidence", [])))
        if check.get("status") != "PASS":
            gaps.append(f"{check.get('check_id', '')}: {check.get('message', '')}".strip(": "))
    return {
        "area_id": area_id,
        "label": label,
        "score": score,
        "status": status,
        "threshold": int(threshold),
        "checks": checks,
        "evidence": evidence,
        "gaps": gaps,
        "recommended_next_specs": recommended_next_specs,
    }


def _overall_status(areas: list[dict[str, Any]], *, threshold: int) -> str:
    if not areas:
        return "NOT_ASSESSED"
    if any(area.get("status") == "FAIL" for area in areas):
        return "FAIL"
    if any(float(area.get("score", 0.0)) < threshold for area in areas):
        return "WARN"
    return "PASS"


def _area_status(score: float, *, has_checks: bool) -> str:
    if not has_checks:
        return "NOT_ASSESSED"
    if score >= AREA_BAND_PASS:
        return "PASS"
    if score >= AREA_BAND_WARN:
        return "WARN"
    return "FAIL"


def _file_exists_check(check_id: str, label: str, path: Path, *, source: str) -> dict[str, Any]:
    exists = path.is_file()
    return _check_dict(check_id, label, exists, [str(path)], source, f"{path.as_posix()} {'exists' if exists else 'is missing'}")


def _manifest_exists_check(check_id: str, label: str, path: Path, *, source: str) -> dict[str, Any]:
    exists = path.is_file()
    return _check_dict(check_id, label, exists, [str(path)], source, f"{path.as_posix()} {'exists' if exists else 'is missing'}")


def _manifest_text_contains_check(check_id: str, label: str, path: Path, terms: list[str], *, source: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    missing = [term for term in terms if term.lower() not in text]
    ok = path.is_file() and not missing
    message = f"Missing terms: {', '.join(missing)}" if missing else f"Required terms found in {path.as_posix()}."
    evidence = [str(path)]
    return _check_dict(check_id, label, ok, evidence, source, message)


def _file_text_contains_check(check_id: str, label: str, path: Path, terms: list[str], *, source: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    missing = [term for term in terms if term.lower() not in text]
    ok = path.is_file() and not missing
    message = f"Missing terms: {', '.join(missing)}" if missing else f"Required terms found in {path.as_posix()}."
    evidence = [str(path)]
    return _check_dict(check_id, label, ok, evidence, source, message)


def _text_contains_check(check_id: str, label: str, path: Path, terms: list[str], *, source: str) -> dict[str, Any]:
    return _file_text_contains_check(check_id, label, path, terms, source=source)


def _file_function_check(check_id: str, label: str, path: Path, functions: list[str], *, source: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    missing = [fn for fn in functions if fn not in text]
    ok = path.is_file() and not missing
    message = f"Missing functions: {', '.join(missing)}" if missing else f"Required functions found in {path.as_posix()}."
    return _check_dict(check_id, label, ok, [str(path)], source, message)


def _cli_text_check(check_id: str, label: str, path: Path, terms: list[str], *, source: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    missing = [term for term in terms if term.lower() not in text]
    ok = path.is_file() and not missing
    message = f"Missing terms: {', '.join(missing)}" if missing else f"Required CLI terms found in {path.as_posix()}."
    return _check_dict(check_id, label, ok, [str(path), "CLI"], source, message)


def _route_alignment_check() -> dict[str, Any]:
    result = validate_event_source_route_alignment(routes_path=ROOT / "config" / "event_routes.json")
    ok = bool(result.get("ok", False))
    message = "Event source route alignment passes." if ok else "Event source route alignment failed."
    evidence = [str(ROOT / "config" / "event_routes.json"), "runtime.event_source_route_alignment.validate_event_source_route_alignment"]
    return _check_dict("event_routes_validate", "Event routes validate", ok, evidence, "runtime.event_source_route_alignment", message)


def _runtime_profile_check() -> dict[str, Any]:
    path = ROOT / "config" / "runtime_profile.json"
    if not path.is_file():
        return _check_dict("runtime_profile_configured", "Runtime profile configured", False, [str(path)], "config/runtime_profile.json", "Runtime profile file missing.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _check_dict("runtime_profile_configured", "Runtime profile configured", False, [str(path)], "config/runtime_profile.json", f"Invalid JSON: {exc}")
    ok = bool(data.get("governance_enforced", False)) and str(data.get("environment", "")).strip() == "demo"
    message = "Runtime profile is configured for controlled demo readiness." if ok else "Runtime profile is not configured for controlled demo readiness."
    return _check_dict("runtime_profile_configured", "Runtime profile configured", ok, [str(path)], "config/runtime_profile.json", message)


def _manifest_health_check(readiness_dir: Path) -> dict[str, Any]:
    result = run_manifest_health_check(
        manifest_dir=ROOT / "manifests",
        runtime_data_dir=readiness_dir.parent,
        strict_contract=True,
        include_smoke=False,
    )
    report = write_manifest_health_report(result, runtime_data_dir=readiness_dir.parent, report_name="manifest_health_strict")
    ok = bool(result.get("ok", False))
    evidence = [
        str(Path(str(report.get("json_path", "")))) if report.get("json_path") else "",
        str(Path(str(report.get("markdown_path", "")))) if report.get("markdown_path") else "",
        "src.manifest_health.run_manifest_health_check",
    ]
    evidence = [item for item in evidence if item]
    message = "Manifest health check passes in strict mode without smoke." if ok else "Manifest health check failed."
    return _check_dict("active_manifest_catalog_health_passes", "Active manifest catalog health passes", ok, evidence, "src.manifest_health", message)


def _scenario_check(check_id: str, label: str, scenario_id: str, *, source: str) -> dict[str, Any]:
    text_path = ROOT / "src" / "operator_scenarios.py"
    text = text_path.read_text(encoding="utf-8") if text_path.is_file() else ""
    ok = scenario_id in text
    return _check_dict(check_id, label, ok, [str(text_path), scenario_id], source, f"Scenario '{scenario_id}' {'found' if ok else 'missing'} in operator_scenarios.py.")


def _demo_pack_check(check_id: str, label: str, pack_id: str, *, source: str) -> dict[str, Any]:
    try:
        pack = get_demo_pack(pack_id)
        ok = pack.get("id") == pack_id
        evidence = [str(ROOT / "src" / "operator_cross_workflow_demo.py"), pack_id]
        return _check_dict(check_id, label, ok, evidence, source, f"Demo pack '{pack_id}' {'registered' if ok else 'missing'}.")
    except Exception as exc:
        return _check_dict(check_id, label, False, [str(ROOT / "src" / "operator_cross_workflow_demo.py")], source, str(exc))


def _text_absence_check(check_id: str, label: str, path: Path, forbidden_terms: list[str], *, source: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lower() if path.is_file() else ""
    found = [term for term in forbidden_terms if term.lower() in text]
    ok = path.is_file() and not found
    message = f"Forbidden terms present: {', '.join(found)}" if found else f"No domain logic detected in {path.as_posix()}."
    return _check_dict(check_id, label, ok, [str(path)], source, message)


def _check_dict(check_id: str, label: str, ok: bool, evidence: list[str], source: str, message: str, *, score_weight: int = 1) -> dict[str, Any]:
    status = "PASS" if ok else "FAIL"
    earned = float(score_weight if ok else 0.0)
    return {
        "check_id": check_id,
        "label": label,
        "status": status,
        "score_weight": score_weight,
        "earned": earned,
        "message": message,
        "evidence": [item for item in evidence if item],
        "source": source,
    }


def _serialize_result(result: dict) -> dict:
    payload = dict(result)
    areas = payload.get("areas", {})
    if isinstance(areas, dict):
        payload["areas"] = {key: _serialize_area(value) for key, value in areas.items()}
    return payload


def _serialize_area(area: Any) -> Any:
    if not isinstance(area, dict):
        return area
    payload = dict(area)
    checks = payload.get("checks", [])
    payload["checks"] = [dict(check) for check in checks if isinstance(check, dict)]
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


AREA_ORDER = [
    "core_architecture",
    "manifest_runtime",
    "event_routing",
    "business_workflows",
    "tooling",
    "release_verification",
    "production_readiness",
]
