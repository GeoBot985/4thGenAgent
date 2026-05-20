"""Tool pack governance and environment enablement policy."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_PATH = ROOT / "config" / "toolpack_governance.json"

ENVIRONMENTS = ("demo", "dev", "test", "release", "pilot", "live")
CLASSIFICATIONS = ("core", "optional", "experimental", "high_risk", "blocked")

# Which environments are restricted — non-core/optional packs need explicit governance to enter
_RESTRICTED_ENVS = frozenset({"demo", "release", "live"})

# Environments that high_risk and experimental packs must never enter without explicit override
_SAFE_ONLY_ENVS = frozenset({"demo", "release"})


def load_governance() -> dict[str, Any]:
    if not GOVERNANCE_PATH.is_file():
        return {"schema_version": 1, "entries": []}
    try:
        data = json.loads(GOVERNANCE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data.get("entries"), list):
            data["entries"] = []
        return data
    except Exception:
        return {"schema_version": 1, "entries": []}


def save_governance(data: dict[str, Any]) -> None:
    GOVERNANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOVERNANCE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def enable_pack(
    toolpack_id: str,
    *,
    classification: str,
    environments: list[str],
    enabled_by: str = "operator",
    reason: str = "",
) -> dict[str, Any]:
    errors = _validate_enable_args(toolpack_id, classification, environments)
    if errors:
        return {"ok": False, "toolpack_id": toolpack_id, "classification": classification, "environments": [], "errors": errors}

    data = load_governance()
    entries: list[dict[str, Any]] = data.get("entries", [])
    existing = next((e for e in entries if e.get("toolpack_id") == toolpack_id), None)
    now = _now_iso()

    if existing:
        existing["classification"] = classification
        existing["enabled_environments"] = sorted(set(environments))
        existing["updated_by"] = enabled_by
        existing["updated_at"] = now
        if reason:
            existing["reason"] = reason
    else:
        entries.append({
            "toolpack_id": toolpack_id,
            "classification": classification,
            "enabled_environments": sorted(set(environments)),
            "enabled_by": enabled_by,
            "enabled_at": now,
            "reason": reason,
        })

    data["entries"] = entries
    save_governance(data)
    return {
        "ok": True,
        "toolpack_id": toolpack_id,
        "classification": classification,
        "environments": sorted(set(environments)),
        "errors": [],
    }


def disable_pack(
    toolpack_id: str,
    *,
    environments: list[str] | None = None,
    reason: str = "",
    disabled_by: str = "operator",
) -> dict[str, Any]:
    data = load_governance()
    entries: list[dict[str, Any]] = data.get("entries", [])
    existing = next((e for e in entries if e.get("toolpack_id") == toolpack_id), None)
    now = _now_iso()

    if not existing:
        entries.append({
            "toolpack_id": toolpack_id,
            "classification": "blocked",
            "enabled_environments": [],
            "enabled_by": disabled_by,
            "enabled_at": now,
            "reason": reason or "Explicitly disabled.",
        })
    elif environments is None:
        existing["enabled_environments"] = []
        existing["classification"] = "blocked"
        existing["updated_by"] = disabled_by
        existing["updated_at"] = now
        if reason:
            existing["reason"] = reason
    else:
        current = set(existing.get("enabled_environments", []))
        existing["enabled_environments"] = sorted(current - set(environments))
        existing["updated_by"] = disabled_by
        existing["updated_at"] = now
        if reason:
            existing["reason"] = reason

    data["entries"] = entries
    save_governance(data)
    return {"ok": True, "toolpack_id": toolpack_id, "errors": []}


def get_pack_policy(toolpack_id: str) -> dict[str, Any]:
    data = load_governance()
    entry = next((e for e in data.get("entries", []) if e.get("toolpack_id") == toolpack_id), None)
    if entry is None:
        return {
            "toolpack_id": toolpack_id,
            "classification": "unknown",
            "enabled_environments": [],
            "governance_recorded": False,
            "errors": ["No governance entry found."],
        }
    return {
        "toolpack_id": toolpack_id,
        "classification": entry.get("classification", "unknown"),
        "enabled_environments": entry.get("enabled_environments", []),
        "enabled_by": entry.get("enabled_by", ""),
        "enabled_at": entry.get("enabled_at", ""),
        "reason": entry.get("reason", ""),
        "governance_recorded": True,
        "errors": [],
    }


def get_all_policies() -> list[dict[str, Any]]:
    data = load_governance()
    return list(data.get("entries", []))


def check_pack_allowed(toolpack_id: str, environment: str) -> dict[str, Any]:
    if environment not in ENVIRONMENTS:
        return {"ok": False, "allowed": False, "reason": f"Unknown environment: {environment!r}"}
    policy = get_pack_policy(toolpack_id)
    if not policy["governance_recorded"]:
        return {"ok": False, "allowed": False, "reason": "No governance entry — pack not explicitly enabled."}
    classification = policy.get("classification", "unknown")
    if classification == "blocked":
        return {"ok": False, "allowed": False, "classification": classification, "reason": "Pack is blocked."}
    allowed_envs: list[str] = policy.get("enabled_environments", [])
    allowed = environment in allowed_envs
    return {
        "ok": True,
        "allowed": allowed,
        "classification": classification,
        "reason": f"Enabled in: {allowed_envs}." if allowed else f"Not enabled for {environment!r}. Enabled in: {allowed_envs}.",
    }


def build_governance_report() -> dict[str, Any]:
    data = load_governance()
    entries: list[dict[str, Any]] = data.get("entries", [])

    by_classification: dict[str, list[str]] = {c: [] for c in CLASSIFICATIONS}
    by_classification["unknown"] = []
    by_environment: dict[str, list[str]] = {e: [] for e in ENVIRONMENTS}
    violations: list[str] = []

    for entry in entries:
        tid = entry.get("toolpack_id", "")
        cls = entry.get("classification", "unknown")
        envs: list[str] = entry.get("enabled_environments", [])
        by_classification.get(cls, by_classification["unknown"]).append(tid)
        for env in envs:
            if env in by_environment:
                by_environment[env].append(tid)

        if cls in ("high_risk", "experimental") and _SAFE_ONLY_ENVS & set(envs):
            bad = sorted(_SAFE_ONLY_ENVS & set(envs))
            violations.append(f"{tid} ({cls}) enabled in restricted environment(s): {bad}")

        if cls == "blocked" and envs:
            violations.append(f"{tid} is classified blocked but has enabled environments: {envs}")

    ok = not violations
    return {
        "ok": ok,
        "schema_version": data.get("schema_version", 1),
        "total_entries": len(entries),
        "by_classification": by_classification,
        "by_environment": by_environment,
        "violations": violations,
        "status": "PASS" if ok else "FAIL",
    }


def validate_governance_for_release() -> dict[str, Any]:
    """Validate that demo and release environments only contain safe packs."""
    report = build_governance_report()
    data = load_governance()
    entries = data.get("entries", [])

    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    config_exists = GOVERNANCE_PATH.is_file()
    _add_check(checks, "governance_config_exists", config_exists,
               "Governance config found." if config_exists else f"Missing: {GOVERNANCE_PATH}")
    if not config_exists:
        errors.append("Governance config missing.")

    violations = report.get("violations", [])
    _add_check(checks, "no_policy_violations", not violations,
               "No policy violations." if not violations else f"Violations: {violations}")
    errors.extend(violations)

    for restricted_env in ("demo", "release"):
        env_packs = set(report["by_environment"].get(restricted_env, []))
        unsafe = [
            e["toolpack_id"] for e in entries
            if e.get("toolpack_id") in env_packs
            and e.get("classification") in ("high_risk", "experimental", "blocked")
        ]
        _add_check(checks, f"{restricted_env}_env_safe", not unsafe,
                   f"{restricted_env} environment contains no unsafe packs." if not unsafe
                   else f"Unsafe packs in {restricted_env}: {unsafe}")
        errors.extend(f"Unsafe pack in {restricted_env} environment: {p}" for p in unsafe)

    ok = not errors
    return {"ok": ok, "status": "PASS" if ok else "FAIL", "checks": checks, "errors": errors}


def render_governance_markdown(report: dict[str, Any]) -> str:
    lines = ["# Tool Pack Governance Report", ""]
    lines.append(f"**Status:** {report.get('status', 'UNKNOWN')}")
    lines.append(f"**Total entries:** {report.get('total_entries', 0)}")
    lines.append("")

    lines.append("## By Classification")
    lines.append("")
    lines.append("| Classification | Packs |")
    lines.append("|---|---|")
    for cls, packs in report.get("by_classification", {}).items():
        if packs:
            lines.append(f"| {cls} | {', '.join(sorted(packs))} |")
    lines.append("")

    lines.append("## By Environment")
    lines.append("")
    lines.append("| Environment | Enabled Packs |")
    lines.append("|---|---|")
    for env, packs in report.get("by_environment", {}).items():
        lines.append(f"| {env} | {', '.join(sorted(packs)) if packs else '—'} |")
    lines.append("")

    violations = report.get("violations", [])
    if violations:
        lines.append("## Policy Violations")
        lines.append("")
        for v in violations:
            lines.append(f"- {v}")
        lines.append("")

    return "\n".join(lines)


def _validate_enable_args(toolpack_id: str, classification: str, environments: list[str]) -> list[str]:
    errors: list[str] = []
    if not toolpack_id:
        errors.append("toolpack_id is required.")
    if classification not in CLASSIFICATIONS:
        errors.append(f"Invalid classification {classification!r}. Must be one of: {list(CLASSIFICATIONS)}")
    invalid_envs = [e for e in environments if e not in ENVIRONMENTS]
    if invalid_envs:
        errors.append(f"Invalid environments: {invalid_envs}. Must be from: {list(ENVIRONMENTS)}")
    if classification == "blocked" and environments:
        errors.append("Blocked packs cannot have enabled environments.")
    return errors


def _add_check(checks: list[dict[str, Any]], check_id: str, ok: bool, message: str) -> None:
    checks.append({"id": check_id, "status": "PASS" if ok else "FAIL", "message": message})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
