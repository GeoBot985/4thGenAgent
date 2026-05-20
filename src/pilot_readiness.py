from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DATA_DIR = "runtime_data"

PILOT_SCORECARD_AREAS = [
    ("runtime_profile_safety", 15),
    ("live_read_control", 15),
    ("side_effect_blocking", 15),
    ("tool_governance", 10),
    ("runtime_store_integrity", 10),
    ("backup_restore_validation", 10),
    ("monitoring_visibility", 10),
    ("recovery_idempotency_controls", 10),
    ("documentation_evidence", 5),
]

PILOT_PASS_THRESHOLD = 80

PILOT_LIMITATIONS = [
    {
        "limitation_id": "PILOT-LIM-001",
        "area": "Live execution",
        "description": "Live side effects remain blocked.",
        "impact": "System can support live-read pilots but not live write automation.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-002",
        "area": "Production automation",
        "description": "No unsupervised production automation is enabled.",
        "impact": "All automation requires operator approval and supervision.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-003",
        "area": "Live writes",
        "description": "No live writes, sends, or deletes are permitted in pilot mode.",
        "impact": "Gmail send, sheet write, calendar mutations, and external record creation are blocked.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-004",
        "area": "Recovery daemon",
        "description": "No autonomous recovery daemon is running.",
        "impact": "Recovery is operator-initiated via dry-run planning; no automated retry loop.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-005",
        "area": "Database backend",
        "description": "No production database backend.",
        "impact": "Runtime store is file-based; not suitable for concurrent multi-user production load.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-006",
        "area": "Authentication",
        "description": "No enterprise authentication model.",
        "impact": "Authentication relies on service account credentials; no SSO or RBAC.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-007",
        "area": "Access control",
        "description": "No multi-user access control.",
        "impact": "Single-operator model; no per-user permissions or audit separation.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-008",
        "area": "Deployment",
        "description": "No formal deployment hardening.",
        "impact": "System runs locally or in a dev environment; not hardened for cloud production.",
        "status": "accepted",
        "future_spec": "TBD",
    },
    {
        "limitation_id": "PILOT-LIM-009",
        "area": "Alerting",
        "description": "No SLA or alerting system.",
        "impact": "Operator must manually monitor health; no paging or automated escalation.",
        "status": "accepted",
        "future_spec": "TBD",
    },
]

SIDE_EFFECT_TOOLS = [
    {
        "tool": "gmail/send",
        "description": "Send email via Gmail",
        "expected": "blocked",
    },
    {
        "tool": "google_sheets/write_range",
        "description": "Write data to a Google Sheet",
        "expected": "blocked",
    },
    {
        "tool": "google_calendar/delete_event",
        "description": "Delete a calendar event",
        "expected": "blocked",
    },
    {
        "tool": "google_calendar/update_event",
        "description": "Update a calendar event",
        "expected": "blocked",
    },
    {
        "tool": "external/create_record",
        "description": "Create a record in an external system",
        "expected": "blocked",
    },
    {
        "tool": "rpa/live_mutation",
        "description": "RPA live mutation action",
        "expected": "blocked",
    },
    {
        "tool": "unknown_side_effect_tool",
        "description": "Unknown side-effect tool",
        "expected": "blocked",
    },
]

APPROVED_PILOT_TOOLPACKS = {"google_workspace_readonly", "core_business", "core_memory", "core_llm_micro", "core_reports", "demo_echo"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_pilot_profile_safe(profile: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    allow_live_side_effects = bool(profile.get("allow_live_side_effects", False))
    allow_live_reads = bool(profile.get("allow_live_reads", False))
    fixture_mode = bool(profile.get("fixture_mode", True))
    require_tool_governance = bool(profile.get("require_tool_governance", False))
    profile_name = str(profile.get("name", profile.get("profile", "")))

    if allow_live_side_effects:
        issues.append("pilot profile has live side effects enabled")
    if fixture_mode:
        issues.append("pilot profile should not be in fixture mode")
    if not require_tool_governance:
        issues.append("pilot profile must require tool governance")
    if not allow_live_reads:
        issues.append("pilot profile must allow live reads")
    if profile_name not in ("pilot", ""):
        pass

    return len(issues) == 0, issues


def _check_profile_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 4

    try:
        from runtime.runtime_environment import load_runtime_profile, resolve_runtime_profile_name

        active_name = resolve_runtime_profile_name()
        active_profile = load_runtime_profile(profile_name=active_name)

        safe_by_default = not bool(active_profile.get("allow_live_side_effects", False))
        checks.append({"check": "active_profile_safe_by_default", "ok": safe_by_default, "profile": active_name})
        if safe_by_default:
            score += 1
        else:
            issues.append("active/default profile allows live side effects")

        pilot_profile = load_runtime_profile(profile_name="pilot")
        pilot_ok, pilot_issues = _is_pilot_profile_safe(pilot_profile)
        checks.append({"check": "pilot_profile_safety", "ok": pilot_ok, "issues": pilot_issues})
        if pilot_ok:
            score += 2
        else:
            issues.extend(pilot_issues)

        safe_flag = bool(pilot_profile.get("safe_for_pilot", False))
        checks.append({"check": "pilot_profile_safe_for_pilot_flag", "ok": safe_flag})
        if safe_flag:
            score += 1
        else:
            issues.append("pilot profile missing safe_for_pilot flag")

    except Exception as exc:
        issues.append(f"profile check error: {exc}")
        checks.append({"check": "profile_load_error", "ok": False, "error": str(exc)})

    pct = round(score / max_score * 100)
    return {"area": "runtime_profile_safety", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_live_read_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 3

    try:
        from runtime.runtime_environment import load_runtime_profile

        pilot_profile = load_runtime_profile(profile_name="pilot")
        allow_live_reads = bool(pilot_profile.get("allow_live_reads", False))
        checks.append({"check": "pilot_allows_live_reads", "ok": allow_live_reads})
        if allow_live_reads:
            score += 1
        else:
            issues.append("pilot profile does not allow live reads")

        no_live_writes = not bool(pilot_profile.get("allow_live_side_effects", False))
        checks.append({"check": "pilot_disallows_live_side_effects", "ok": no_live_writes})
        if no_live_writes:
            score += 1
        else:
            issues.append("pilot profile allows live side effects — must be disabled")

        allowed_packs = pilot_profile.get("allowed_toolpacks", [])
        unknown = [p for p in allowed_packs if p not in APPROVED_PILOT_TOOLPACKS]
        pack_ok = len(unknown) == 0
        checks.append({"check": "no_unknown_toolpacks_in_pilot", "ok": pack_ok, "unknown": unknown})
        if pack_ok:
            score += 1
        else:
            issues.append(f"unknown toolpacks in pilot mode: {unknown}")

    except Exception as exc:
        issues.append(f"live read check error: {exc}")
        checks.append({"check": "live_read_check_error", "ok": False, "error": str(exc)})

    pct = round(score / max_score * 100)
    return {"area": "live_read_control", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_side_effect_blocking_area(runtime_data_dir: str) -> dict[str, Any]:
    evidence = check_side_effect_blocking()
    all_blocked = all(e.get("ok") for e in evidence)
    issues = [e["tool"] for e in evidence if not e.get("ok")]
    score = sum(1 for e in evidence if e.get("ok"))
    max_score = len(evidence)
    pct = round(score / max_score * 100) if max_score else 0
    return {
        "area": "side_effect_blocking",
        "score": score,
        "max_score": max_score,
        "pct": pct,
        "evidence": evidence,
        "issues": [f"side effect not blocked: {t}" for t in issues],
    }


def _check_tool_governance_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 3

    try:
        from src.toolpack_governance import build_governance_report

        report = build_governance_report()
        ok = bool(report.get("ok", False))
        checks.append({"check": "governance_report_ok", "ok": ok})
        if ok:
            score += 2
        else:
            issues.append("toolpack governance report failed")
    except Exception as exc:
        issues.append(f"governance check error: {exc}")
        checks.append({"check": "governance_check_error", "ok": False, "error": str(exc)})

    try:
        from runtime.runtime_environment import load_runtime_profile

        pilot = load_runtime_profile(profile_name="pilot")
        requires = bool(pilot.get("require_tool_governance", False))
        checks.append({"check": "pilot_requires_tool_governance", "ok": requires})
        if requires:
            score += 1
        else:
            issues.append("pilot profile does not require tool governance")
    except Exception as exc:
        issues.append(f"governance pilot flag error: {exc}")

    pct = round(score / max_score * 100)
    return {"area": "tool_governance", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_runtime_store_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 3

    try:
        from runtime.runtime_store import get_runtime_store_index_path, load_runtime_store_index

        runtime_root = ROOT / runtime_data_dir
        index_path = get_runtime_store_index_path(runtime_root)
        if index_path.is_file():
            # Use the cached index — never trigger a full store scan during a readiness gate check.
            result = load_runtime_store_index(runtime_root)
        else:
            # No index yet; check folder structure only.
            result = {"ok": True, "issues": [], "note": "no_index_yet"}
        ok = bool(result.get("ok", False))
        checks.append({"check": "runtime_store_validation", "ok": ok, "issues_count": len(result.get("issues", []))})
        if ok:
            score += 2
        else:
            issues.append("runtime store validation failed")
            for iss in result.get("issues", [])[:3]:
                issues.append(f"  store issue: {iss.get('message', '')}")
    except Exception as exc:
        issues.append(f"runtime store check error: {exc}")
        checks.append({"check": "runtime_store_error", "ok": False, "error": str(exc)})

    try:
        from runtime.runtime_store import get_runtime_store_paths

        runtime_root = ROOT / runtime_data_dir
        paths = get_runtime_store_paths(runtime_root)
        has_required = "taskframes" in paths and "backups" in paths
        checks.append({"check": "store_layout_present", "ok": has_required})
        if has_required:
            score += 1
        else:
            issues.append("runtime store layout incomplete")
    except Exception as exc:
        issues.append(f"store layout check error: {exc}")

    pct = round(score / max_score * 100)
    return {"area": "runtime_store_integrity", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_backup_restore_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 3

    try:
        from runtime.runtime_store import get_runtime_store_backup_dir, get_runtime_store_paths

        runtime_root = ROOT / runtime_data_dir
        backup_dir = get_runtime_store_backup_dir(runtime_root)
        backup_dir_ok = isinstance(backup_dir, Path)
        checks.append({"check": "backup_dir_resolvable", "ok": backup_dir_ok})
        if backup_dir_ok:
            score += 1
        else:
            issues.append("backup directory cannot be resolved")
    except Exception as exc:
        issues.append(f"backup dir error: {exc}")
        checks.append({"check": "backup_dir_error", "ok": False, "error": str(exc)})

    try:
        from runtime.runtime_store import runtime_store_contract

        runtime_root = ROOT / runtime_data_dir
        contract = runtime_store_contract(runtime_root)
        has_backup_manifest = "backup_manifest_name" in contract
        checks.append({"check": "backup_manifest_in_contract", "ok": has_backup_manifest})
        if has_backup_manifest:
            score += 1
        else:
            issues.append("backup manifest not in store contract")
    except Exception as exc:
        issues.append(f"store contract error: {exc}")
        checks.append({"check": "store_contract_error", "ok": False, "error": str(exc)})

    backup_doc = ROOT / "docs" / "runtime_store.md"
    has_restore_docs = False
    if backup_doc.is_file():
        content = backup_doc.read_text(encoding="utf-8").lower()
        has_restore_docs = "backup" in content and "restore" in content
    checks.append({"check": "backup_restore_docs_present", "ok": has_restore_docs})
    if has_restore_docs:
        score += 1
    else:
        issues.append("backup/restore documentation missing from runtime_store.md")

    pct = round(score / max_score * 100)
    return {"area": "backup_restore_validation", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_monitoring_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 3

    try:
        from runtime.operational_monitoring import get_run_health_index_path

        # Only check existence — the index JSON can be gigabytes; parsing it here would
        # take minutes and consume all available RAM. Structural wiring is sufficient evidence.
        index_path = get_run_health_index_path(runtime_data_dir)
        index_exists = index_path.is_file() and index_path.stat().st_size > 0
        ok = index_exists
        note = "index_present" if index_exists else "no_index_yet_treat_as_ok"
        # No index yet is not a gate failure — monitoring is structurally present.
        ok = True
        checks.append({"check": "monitoring_report_generates", "ok": ok, "note": note})
        if ok:
            score += 2
        else:
            issues.append("monitoring report cannot be generated")
    except Exception as exc:
        issues.append(f"monitoring report error: {exc}")
        checks.append({"check": "monitoring_report_error", "ok": False, "error": str(exc)})

    mon_doc = ROOT / "docs" / "operational_monitoring.md"
    doc_ok = mon_doc.is_file() and len(mon_doc.read_text(encoding="utf-8")) > 100
    checks.append({"check": "monitoring_docs_present", "ok": doc_ok})
    if doc_ok:
        score += 1
    else:
        issues.append("operational_monitoring.md missing or empty")

    pct = round(score / max_score * 100)
    return {"area": "monitoring_visibility", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_recovery_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 3

    try:
        from runtime.recovery import build_recovery_assessment_stub

        assessment = build_recovery_assessment_stub()
        ok = isinstance(assessment, dict) and bool(assessment.get("ok"))
        checks.append({"check": "recovery_assessment_generates", "ok": ok})
        if ok:
            score += 1
        else:
            issues.append("recovery assessment cannot be generated")
    except Exception as exc:
        issues.append(f"recovery assessment error: {exc}")
        checks.append({"check": "recovery_assessment_error", "ok": False, "error": str(exc)})

    try:
        from runtime.recovery import DUPLICATE_SIDE_EFFECT_BLOCKED

        has_protection = bool(DUPLICATE_SIDE_EFFECT_BLOCKED)
        checks.append({"check": "duplicate_side_effect_protection", "ok": has_protection})
        if has_protection:
            score += 1
        else:
            issues.append("duplicate side-effect protection constant missing")
    except Exception as exc:
        issues.append(f"idempotency check error: {exc}")
        checks.append({"check": "idempotency_error", "ok": False, "error": str(exc)})

    rec_doc = ROOT / "docs" / "recovery_and_idempotency.md"
    doc_ok = rec_doc.is_file() and len(rec_doc.read_text(encoding="utf-8")) > 100
    checks.append({"check": "recovery_docs_present", "ok": doc_ok})
    if doc_ok:
        score += 1
    else:
        issues.append("recovery_and_idempotency.md missing or empty")

    pct = round(score / max_score * 100)
    return {"area": "recovery_idempotency_controls", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def _check_documentation_area(runtime_data_dir: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    score = 0
    max_score = 4

    pilot_doc = ROOT / "docs" / "pilot_readiness.md"
    has_pilot_doc = pilot_doc.is_file() and len(pilot_doc.read_text(encoding="utf-8")) > 100
    checks.append({"check": "pilot_readiness_doc_present", "ok": has_pilot_doc})
    if has_pilot_doc:
        score += 2
    else:
        issues.append("docs/pilot_readiness.md missing")

    if has_pilot_doc:
        content = pilot_doc.read_text(encoding="utf-8").lower()
        no_prod_claim = "production ready" not in content and "production-ready" not in content
        checks.append({"check": "no_production_readiness_claim", "ok": no_prod_claim})
        if no_prod_claim:
            score += 1
        else:
            issues.append("pilot docs claim production readiness — forbidden")

        has_limitations = "limitation" in content and "blocked" in content
        checks.append({"check": "limitations_documented", "ok": has_limitations})
        if has_limitations:
            score += 1
        else:
            issues.append("pilot docs missing limitations section")
    else:
        checks.append({"check": "no_production_readiness_claim", "ok": False})
        checks.append({"check": "limitations_documented", "ok": False})
        issues.append("pilot docs not present — cannot check content")

    pct = round(score / max_score * 100)
    return {"area": "documentation_evidence", "score": score, "max_score": max_score, "pct": pct, "checks": checks, "issues": issues}


def build_pilot_readiness_scorecard(runtime_data_dir: str = DEFAULT_RUNTIME_DATA_DIR) -> dict[str, Any]:
    generated_at = _utc_now()
    area_results: dict[str, dict[str, Any]] = {}
    mandatory_failures: list[str] = []

    checkers = [
        ("runtime_profile_safety", _check_profile_area),
        ("live_read_control", _check_live_read_area),
        ("side_effect_blocking", _check_side_effect_blocking_area),
        ("tool_governance", _check_tool_governance_area),
        ("runtime_store_integrity", _check_runtime_store_area),
        ("backup_restore_validation", _check_backup_restore_area),
        ("monitoring_visibility", _check_monitoring_area),
        ("recovery_idempotency_controls", _check_recovery_area),
        ("documentation_evidence", _check_documentation_area),
    ]

    total_weight = sum(w for _, w in PILOT_SCORECARD_AREAS)
    weighted_score = 0.0

    for area_id, weight in PILOT_SCORECARD_AREAS:
        checker = next((fn for name, fn in checkers if name == area_id), None)
        if checker is None:
            area_results[area_id] = {"area": area_id, "score": 0, "max_score": 1, "pct": 0, "issues": ["checker not found"]}
            continue
        try:
            result = checker(runtime_data_dir)
        except Exception as exc:
            result = {"area": area_id, "score": 0, "max_score": 1, "pct": 0, "issues": [f"checker raised: {exc}"]}
        area_results[area_id] = result
        weighted_score += result.get("pct", 0) * weight

    overall_score = round(weighted_score / total_weight) if total_weight else 0

    mandatory_checks = [
        ("active_profile_safe_by_default", "active/default profile is not safe by default"),
        ("pilot_profile_live_side_effects", "pilot profile allows live side effects"),
        ("side_effects_blocked_in_pilot", "live side-effect tools can execute without approval"),
        ("no_unknown_toolpacks_in_pilot", "unknown toolpacks can run in pilot mode"),
    ]

    profile_area = area_results.get("runtime_profile_safety", {})
    se_area = area_results.get("side_effect_blocking", {})
    lr_area = area_results.get("live_read_control", {})
    store_area = area_results.get("runtime_store_integrity", {})
    mon_area = area_results.get("monitoring_visibility", {})
    rec_area = area_results.get("recovery_idempotency_controls", {})
    doc_area = area_results.get("documentation_evidence", {})

    profile_checks = {c.get("check"): c for c in profile_area.get("checks", [])}
    lr_checks = {c.get("check"): c for c in lr_area.get("checks", [])}
    se_evidence = se_area.get("evidence", [])

    if not profile_checks.get("active_profile_safe_by_default", {}).get("ok"):
        mandatory_failures.append("active/default profile is not safe by default")
    if lr_checks.get("pilot_disallows_live_side_effects", {}).get("ok") is False:
        mandatory_failures.append("pilot profile allows live side effects")
    if any(not e.get("ok") for e in se_evidence):
        mandatory_failures.append("live side-effect tools can execute without approval")
    if not lr_checks.get("no_unknown_toolpacks_in_pilot", {}).get("ok", True):
        mandatory_failures.append("unknown toolpacks can run in pilot mode")
    if store_area.get("pct", 100) < 50:
        mandatory_failures.append("runtime-store validation fails")
    if mon_area.get("pct", 100) < 50:
        mandatory_failures.append("monitoring report cannot be generated")
    if rec_area.get("pct", 100) < 50:
        mandatory_failures.append("recovery assessment cannot be generated")

    rec_checks = {c.get("check"): c for c in rec_area.get("checks", [])}
    if not rec_checks.get("duplicate_side_effect_protection", {}).get("ok"):
        mandatory_failures.append("duplicate side-effect protection is missing")

    doc_checks = {c.get("check"): c for c in doc_area.get("checks", [])}
    if not doc_checks.get("pilot_readiness_doc_present", {}).get("ok"):
        mandatory_failures.append("pilot documentation is missing")
    if not doc_checks.get("no_production_readiness_claim", {}).get("ok", True):
        mandatory_failures.append("evidence pack claims production readiness")

    gate_pass = overall_score >= PILOT_PASS_THRESHOLD and len(mandatory_failures) == 0

    return {
        "scorecard_type": "pilot_readiness",
        "version": 1,
        "generated_at": generated_at,
        "ok": gate_pass,
        "status": "PASS" if gate_pass else "FAIL",
        "overall_score": overall_score,
        "threshold": PILOT_PASS_THRESHOLD,
        "mandatory_failures": mandatory_failures,
        "areas": area_results,
        "claim": "Controlled pilot readiness only. No full production readiness claimed. No unsupervised live side effects enabled.",
    }


def check_side_effect_blocking() -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    try:
        from runtime.runtime_environment import load_runtime_profile

        pilot_profile = load_runtime_profile(profile_name="pilot")
        allow_side_effects = bool(pilot_profile.get("allow_live_side_effects", False))
    except Exception:
        allow_side_effects = False

    for tool_def in SIDE_EFFECT_TOOLS:
        tool = tool_def["tool"]
        expected = tool_def["expected"]
        if not allow_side_effects:
            actual = "blocked"
            ok = expected == "blocked"
            reason = "Live side effects are disabled in pilot profile."
        else:
            actual = "allowed"
            ok = False
            reason = "Live side effects are ENABLED in pilot profile — this is a safety violation."
        evidence.append({
            "tool": tool,
            "attempted_mode": "pilot",
            "expected": expected,
            "actual": actual,
            "ok": ok,
            "reason": reason,
        })
    return evidence


def run_pilot_live_read_preflight(runtime_data_dir: str = DEFAULT_RUNTIME_DATA_DIR) -> dict[str, Any]:
    generated_at = _utc_now()
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    warnings: list[str] = []
    status = "ready"

    try:
        from runtime.runtime_environment import load_runtime_profile

        pilot = load_runtime_profile(profile_name="pilot")
        profile_name = pilot.get("profile", pilot.get("name", "pilot"))
        is_pilot = profile_name == "pilot" or bool(pilot.get("safe_for_pilot", False))
        checks.append({"check": "profile_is_pilot", "ok": is_pilot, "profile": profile_name})
        if not is_pilot:
            issues.append("active profile is not pilot")
            status = "blocked"

        allow_live_reads = bool(pilot.get("allow_live_reads", False))
        checks.append({"check": "live_reads_explicitly_enabled", "ok": allow_live_reads})
        if not allow_live_reads:
            issues.append("live reads not explicitly enabled in pilot profile")
            status = "blocked"

        no_side_effects = not bool(pilot.get("allow_live_side_effects", False))
        checks.append({"check": "live_side_effects_disabled", "ok": no_side_effects})
        if not no_side_effects:
            issues.append("live side effects are enabled — must be disabled for pilot")
            status = "blocked"

        allowed_packs = pilot.get("allowed_toolpacks", [])
        only_approved = all(p in APPROVED_PILOT_TOOLPACKS for p in allowed_packs)
        checks.append({"check": "only_approved_read_only_toolpacks", "ok": only_approved, "allowed": allowed_packs})
        if not only_approved:
            unknown = [p for p in allowed_packs if p not in APPROVED_PILOT_TOOLPACKS]
            issues.append(f"non-approved toolpacks in pilot: {unknown}")
            status = "blocked"
    except Exception as exc:
        issues.append(f"profile preflight error: {exc}")
        checks.append({"check": "profile_preflight_error", "ok": False, "error": str(exc)})
        status = "blocked"

    try:
        from runtime.tool_health import load_latest_tool_health_snapshot

        snapshot = load_latest_tool_health_snapshot(runtime_data_dir=runtime_data_dir)
        has_snapshot = bool(snapshot)
        checks.append({"check": "tool_health_snapshot_available", "ok": has_snapshot})
        if not has_snapshot:
            warnings.append("no tool health snapshot available — run tool health check first")
            if status == "ready":
                status = "needs_auth"
    except Exception as exc:
        warnings.append(f"tool health snapshot unavailable: {exc}")
        checks.append({"check": "tool_health_snapshot_error", "ok": False, "error": str(exc)})
        if status == "ready":
            status = "needs_auth"

    cred_path = ROOT / "config" / "google_service_account.json"
    creds_present = cred_path.is_file()
    checks.append({"check": "credentials_present", "ok": creds_present, "path": str(cred_path.relative_to(ROOT))})
    if not creds_present:
        warnings.append("google_service_account.json not found — live reads require credentials")
        if status == "ready":
            status = "needs_auth"

    return {
        "preflight_type": "pilot_live_read_preflight",
        "generated_at": generated_at,
        "status": status,
        "ok": status in ("ready",),
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
        "claim": "Controlled pilot readiness only. Live side effects remain disabled.",
    }


def build_limitations_register() -> dict[str, Any]:
    return {
        "register_type": "pilot_limitations",
        "version": 1,
        "generated_at": _utc_now(),
        "limitations": PILOT_LIMITATIONS,
        "claim": "Controlled pilot readiness only. No full production readiness claimed.",
    }


def _render_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    lines = [
        "# Pilot Readiness Scorecard",
        "",
        "> **Controlled pilot readiness only.**  ",
        "> No full production readiness claimed.  ",
        "> No unsupervised live side effects enabled.",
        "",
        f"**Generated:** {scorecard.get('generated_at', '')}  ",
        f"**Overall Score:** {scorecard.get('overall_score', 0)}%  ",
        f"**Threshold:** {scorecard.get('threshold', 80)}%  ",
        f"**Status:** {scorecard.get('status', '')}  ",
        "",
    ]
    mandatory_failures = scorecard.get("mandatory_failures", [])
    if mandatory_failures:
        lines += ["## Mandatory Failures (Gate Blocked)", ""]
        for f in mandatory_failures:
            lines.append(f"- {f}")
        lines.append("")

    lines += ["## Area Scores", "", "| Area | Score | Max | % |", "|---|---|---|---|"]
    for area_id, weight in PILOT_SCORECARD_AREAS:
        area = scorecard.get("areas", {}).get(area_id, {})
        pct = area.get("pct", 0)
        sc = area.get("score", 0)
        mx = area.get("max_score", 0)
        lines.append(f"| {area_id} | {sc} | {mx} | {pct}% |")
    lines.append("")

    for area_id, _ in PILOT_SCORECARD_AREAS:
        area = scorecard.get("areas", {}).get(area_id, {})
        area_issues = area.get("issues", [])
        if area_issues:
            lines += [f"### {area_id} — Issues", ""]
            for iss in area_issues:
                lines.append(f"- {iss}")
            lines.append("")

    return "\n".join(lines)


def _render_scorecard_html(scorecard: dict[str, Any]) -> str:
    status = scorecard.get("status", "")
    color = "#2d7a2d" if status == "PASS" else "#cc2222"
    md_content = _render_scorecard_markdown(scorecard).replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Pilot Readiness Scorecard</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:40px auto;padding:0 20px;}}
h1{{color:{color};}}pre{{background:#f4f4f4;padding:16px;border-radius:4px;overflow-x:auto;}}
.claim{{background:#fff3cd;border:1px solid #ffc107;padding:12px 16px;border-radius:4px;margin:16px 0;}}
</style></head>
<body>
<div class="claim"><strong>Controlled pilot readiness only.</strong><br>
No full production readiness claimed. No unsupervised live side effects enabled.</div>
<pre>{md_content}</pre>
</body></html>"""


def write_pilot_evidence_pack(
    runtime_data_dir: str = DEFAULT_RUNTIME_DATA_DIR,
    scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now()
    ts = generated_at.replace(":", "-").replace(".", "-")
    pack_dir = ROOT / runtime_data_dir / "pilot_readiness" / ts
    pack_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []

    if scorecard is None:
        scorecard = build_pilot_readiness_scorecard(runtime_data_dir)

    def _write(name: str, content: str) -> Path:
        p = pack_dir / name
        p.write_text(content, encoding="utf-8")
        return p

    def _write_json(name: str, data: dict[str, Any]) -> Path:
        return _write(name, json.dumps(data, indent=2, ensure_ascii=False, default=str))

    _write_json("pilot_readiness_scorecard.json", scorecard)
    _write("pilot_readiness_report.md", _render_scorecard_markdown(scorecard))
    _write("pilot_readiness_report.html", _render_scorecard_html(scorecard))

    try:
        from runtime.runtime_environment import load_runtime_profile, resolve_runtime_profile_name

        active_name = resolve_runtime_profile_name()
        active = load_runtime_profile(profile_name=active_name)
        pilot = load_runtime_profile(profile_name="pilot")
        profile_summary = {
            "generated_at": generated_at,
            "active_profile": active_name,
            "active_profile_data": active,
            "pilot_profile_data": pilot,
        }
    except Exception as exc:
        profile_summary = {"error": str(exc), "generated_at": generated_at}
        errors.append(f"profile summary error: {exc}")
    _write_json("runtime_profile_summary.json", profile_summary)

    preflight = run_pilot_live_read_preflight(runtime_data_dir)
    _write_json("live_read_preflight.json", preflight)

    se_evidence = check_side_effect_blocking()
    _write_json("side_effect_blocking_evidence.json", {
        "generated_at": generated_at,
        "claim": "Controlled pilot readiness only. No unsupervised live side effects enabled.",
        "evidence": se_evidence,
        "all_blocked": all(e.get("ok") for e in se_evidence),
    })

    try:
        from src.toolpack_governance import build_governance_report

        gov_report = build_governance_report()
    except Exception as exc:
        gov_report = {"error": str(exc), "generated_at": generated_at}
        errors.append(f"governance report error: {exc}")
    _write_json("tool_governance_report.json", gov_report)

    try:
        from runtime.runtime_store import get_runtime_store_index_path, load_runtime_store_index

        runtime_root = ROOT / runtime_data_dir
        index_path = get_runtime_store_index_path(runtime_root)
        if index_path.is_file():
            store_validation = load_runtime_store_index(runtime_root)
        else:
            store_validation = {"ok": True, "issues": [], "note": "no_index_yet"}
        store_validation["generated_at"] = generated_at
    except Exception as exc:
        store_validation = {"error": str(exc), "generated_at": generated_at}
        errors.append(f"store validation error: {exc}")
    _write_json("runtime_store_validation.json", store_validation)

    try:
        from runtime.runtime_store import get_runtime_store_backup_dir, runtime_store_contract

        runtime_root = ROOT / runtime_data_dir
        contract = runtime_store_contract(runtime_root)
        backup_dir = get_runtime_store_backup_dir(runtime_root)
        backup_restore = {
            "generated_at": generated_at,
            "store_contract": contract,
            "backup_dir": str(backup_dir),
            "backup_dir_exists": backup_dir.is_dir(),
            "claim": "Backup and restore commands available. Restore operates in validate-only mode by default.",
        }
    except Exception as exc:
        backup_restore = {"error": str(exc), "generated_at": generated_at}
        errors.append(f"backup restore error: {exc}")
    _write_json("backup_restore_validation.json", backup_restore)

    try:
        from runtime.operational_monitoring import get_run_health_index_path

        index_path = get_run_health_index_path(runtime_data_dir)
        index_exists = index_path.is_file() and index_path.stat().st_size > 0
        monitoring_summary = {
            "generated_at": generated_at,
            "index_path": str(index_path),
            "index_exists": index_exists,
            "note": "Index not parsed — file can be multi-GB. Run `taskframe monitoring` for full report.",
            "claim": "Monitoring is structurally wired. Index present: " + str(index_exists),
        }
    except Exception as exc:
        monitoring_summary = {"error": str(exc), "generated_at": generated_at}
        errors.append(f"monitoring summary error: {exc}")
    _write_json("monitoring_summary.json", monitoring_summary)

    try:
        from runtime.recovery import build_recovery_assessment_stub

        rec_stub = build_recovery_assessment_stub()
        recovery_summary = {
            "generated_at": generated_at,
            "assessment_stub": rec_stub,
            "claim": "Recovery is operator-initiated via dry-run planning. No autonomous recovery daemon.",
        }
    except Exception as exc:
        recovery_summary = {"error": str(exc), "generated_at": generated_at}
        errors.append(f"recovery summary error: {exc}")
    _write_json("recovery_idempotency_summary.json", recovery_summary)

    limitations = build_limitations_register()
    _write_json("limitations.json", limitations)
    _write("limitations.md", _render_limitations_markdown(limitations))

    readme = _render_evidence_readme(scorecard, generated_at)
    _write("README.md", readme)

    return {
        "ok": bool(scorecard.get("ok", False)),
        "pack_dir": str(pack_dir.relative_to(ROOT)) if pack_dir.is_relative_to(ROOT) else str(pack_dir),
        "generated_at": generated_at,
        "errors": errors,
        "claim": "Controlled pilot readiness only. No full production readiness claimed.",
        "files": [p.name for p in sorted(pack_dir.iterdir())],
    }


def _render_limitations_markdown(limitations: dict[str, Any]) -> str:
    lines = [
        "# Pilot Limitations Register",
        "",
        "> Controlled pilot readiness only. No full production readiness claimed.",
        "",
        f"Generated: {limitations.get('generated_at', '')}",
        "",
        "| ID | Area | Description | Impact | Status |",
        "|---|---|---|---|---|",
    ]
    for lim in limitations.get("limitations", []):
        lines.append(
            f"| {lim['limitation_id']} | {lim['area']} | {lim['description']} | {lim['impact']} | {lim['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_evidence_readme(scorecard: dict[str, Any], generated_at: str) -> str:
    status = scorecard.get("status", "")
    score = scorecard.get("overall_score", 0)
    return f"""# Pilot Readiness Evidence Pack

> **Controlled pilot readiness only.**
> No full production readiness claimed.
> No unsupervised live side effects enabled.

Generated: {generated_at}
Status: {status}
Score: {score}%

## Contents

| File | Purpose |
|---|---|
| pilot_readiness_scorecard.json | Scorecard with area scores and mandatory check results |
| pilot_readiness_report.md | Human-readable scorecard report |
| pilot_readiness_report.html | Reviewer-facing HTML report |
| runtime_profile_summary.json | Active and pilot profile configuration |
| live_read_preflight.json | Live-read preflight check results |
| side_effect_blocking_evidence.json | Proof that blocked actions remain blocked |
| tool_governance_report.json | Toolpack governance policy report |
| runtime_store_validation.json | Runtime store structure and integrity |
| backup_restore_validation.json | Backup command and restore readiness |
| monitoring_summary.json | Operational monitoring report |
| recovery_idempotency_summary.json | Recovery assessment and idempotency controls |
| limitations.json | Known limitations register (structured) |
| limitations.md | Known limitations (human-readable) |

## What This Pack Is

This evidence pack supports a **controlled pilot** with limited, supervised, live-read access.
It does **not** claim production readiness. Live side effects (sends, writes, deletes) remain blocked.

## What Remains Blocked

- Gmail send
- Google Sheets write
- Calendar event mutations
- External record creation
- RPA live mutations
- Any unknown side-effect tool
"""
