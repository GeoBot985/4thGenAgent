"""Spec 147 — Readiness Evidence Gate.

Evaluates whether the project may currently claim:
    90%+ controlled demo / portfolio readiness

The gate inspects freshly generated evidence artifacts and applies
deterministic rules. It never runs tests directly.

Usage:
    from src.readiness_evidence_gate import build_readiness_gate, write_gate_report

    result = build_readiness_gate(runtime_data_dir="runtime_data", threshold=90)
    if result["claim_allowed"]:
        write_gate_report(result, runtime_data_dir="runtime_data")
"""
from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.readiness_evidence_contracts import (
    ALLOWED_WORDING,
    CLAIM_CONTROLLED_DEMO_90,
    CLAIM_DISCLAIMER,
    DISALLOWED_CLAIMS,
    EVIDENCE_BOUNDED_VALIDATION,
    EVIDENCE_PILOT_READINESS,
    EVIDENCE_PORTFOLIO_PACK,
    EVIDENCE_READINESS_SCORECARD,
    EVIDENCE_RELEASE_VERIFIER,
    EVIDENCE_STORY_PACK,
    FAIL_CONTROLLED_DEMO_90,
    PASS_CONTROLLED_DEMO_90,
    PRODUCTION_CLAIM_BLOCKED,
    PRODUCTION_NOT_CLAIMED,
    REQUIRED_EVIDENCE,
)

_GATE_SUBDIR = "readiness_gate"
_GATE_JSON = "readiness_gate_report.json"
_GATE_MD = "readiness_gate_report.md"
_GATE_HTML = "readiness_gate_report.html"


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        # Python 3.11+ fromisoformat handles Z
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_fresh(evidence_ts: datetime | None, since_ts: datetime | None) -> bool:
    if since_ts is None:
        return True
    if evidence_ts is None:
        return False
    return evidence_ts >= since_ts


def _get_git_head_timestamp() -> datetime | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            ts = result.stdout.strip()
            return _parse_ts(ts)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        return {}, f"File not found: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}, "File does not contain a JSON object."
        return data, ""
    except Exception as exc:
        return {}, f"Failed to parse JSON: {exc}"


def _find_latest_dir(parent: Path, glob: str) -> Path | None:
    if not parent.is_dir():
        return None
    candidates = sorted(parent.glob(glob), reverse=True)
    return candidates[0] if candidates else None


def _evidence_ts(data: dict[str, Any]) -> datetime | None:
    for key in ("ended_at", "generated_at", "started_at", "timestamp"):
        ts = _parse_ts(str(data.get(key) or ""))
        if ts is not None:
            return ts
    return None


# ---------------------------------------------------------------------------
# Per-artifact inspectors
# ---------------------------------------------------------------------------

def _inspect_bounded_validation(rd: Path, since_ts: datetime | None) -> dict[str, Any]:
    path = rd / "validation" / "bounded_validation_report.json"
    data, err = _load_json(path)
    if err:
        return {"status": "MISSING", "fresh": False, "path": str(path), "error": err}

    ts = _evidence_ts(data)
    fresh = _is_fresh(ts, since_ts)
    ok = bool(data.get("ok", False))
    status = "PASS" if (ok and fresh) else ("STALE" if not fresh else "FAIL")
    result: dict[str, Any] = {
        "status": status,
        "fresh": fresh,
        "path": str(path),
        "ok": ok,
        "summary": data.get("summary", {}),
        "mode": data.get("mode", ""),
    }
    if not ok:
        result["error"] = f"Bounded validation report has ok=False. Failed groups: {data.get('failed_groups', [])}"
    if not fresh:
        result["error"] = "Bounded validation report is stale."
    return result


def _inspect_readiness_scorecard(rd: Path, threshold: int, since_ts: datetime | None) -> dict[str, Any]:
    path = rd / "readiness" / "readiness_scorecard.json"
    data, err = _load_json(path)
    if err:
        return {"status": "MISSING", "fresh": False, "score": 0.0, "path": str(path), "error": err}

    ts = _evidence_ts(data)
    fresh = _is_fresh(ts, since_ts)
    ok = bool(data.get("ok", False))
    score = float(data.get("overall_score", 0) or 0)
    scorecard_status = str(data.get("status", "") or "")
    score_ok = ok and score >= threshold and scorecard_status == "PASS"
    status = "PASS" if (score_ok and fresh) else ("STALE" if not fresh else "FAIL")
    result: dict[str, Any] = {
        "status": status,
        "fresh": fresh,
        "score": score,
        "threshold": threshold,
        "path": str(path),
        "ok": ok,
    }
    if not fresh:
        result["error"] = "Readiness scorecard is stale."
    elif not ok:
        result["error"] = f"Readiness scorecard has ok=False."
    elif score < threshold:
        result["error"] = f"Readiness score {score:.1f} is below threshold {threshold}."
    elif scorecard_status != "PASS":
        result["error"] = f"Readiness scorecard status is '{scorecard_status}', expected 'PASS'."
    return result


def _inspect_story_pack(rd: Path, since_ts: datetime | None) -> dict[str, Any]:
    parent = rd / "demo_packs"
    latest_dir = _find_latest_dir(parent, "cross_workflow_*")
    if latest_dir is None:
        return {"status": "MISSING", "fresh": False, "path": "", "error": "No cross-workflow demo pack directory found."}

    path = latest_dir / "cross_workflow_demo_summary.json"
    data, err = _load_json(path)
    if err:
        return {"status": "MISSING", "fresh": False, "path": str(path), "error": err}

    ts = _evidence_ts(data)
    fresh = _is_fresh(ts, since_ts)
    ok = bool(data.get("ok", False))
    dry_run_only = bool(data.get("dry_run_only", False))
    live_effects = data.get("live_side_effects_performed", None)
    live_effects_claimed = live_effects is True

    passes = ok and dry_run_only and not live_effects_claimed
    status = "PASS" if (passes and fresh) else ("STALE" if not fresh else "FAIL")
    result: dict[str, Any] = {
        "status": status,
        "fresh": fresh,
        "path": str(path),
        "ok": ok,
        "dry_run_only": dry_run_only,
        "pack_run_id": data.get("pack_run_id", ""),
    }
    if not fresh:
        result["error"] = "Cross-workflow story pack is stale."
    elif not ok:
        result["error"] = "Cross-workflow story pack has ok=False."
    elif not dry_run_only:
        result["error"] = "Cross-workflow story pack has dry_run_only=False — live side effects may have occurred."
    elif live_effects_claimed:
        result["error"] = "Cross-workflow story pack reports live_side_effects_performed=True."
    return result


def _inspect_portfolio_pack(rd: Path, since_ts: datetime | None) -> dict[str, Any]:
    parent = rd / "portfolio_evidence"
    latest_dir = _find_latest_dir(parent, "portfolio_evidence_pack_*")
    if latest_dir is None:
        return {"status": "MISSING", "fresh": False, "path": "", "error": "No portfolio evidence pack directory found."}

    path = latest_dir / "summary.json"
    data, err = _load_json(path)
    if err:
        return {"status": "MISSING", "fresh": False, "path": str(path), "error": err}

    ts = _evidence_ts(data)
    fresh = _is_fresh(ts, since_ts)
    ok = bool(data.get("ok", False))
    prod_claimed = bool(data.get("production_readiness_claimed", False))
    has_scorecard = bool(data.get("included_readiness_scorecard", False))
    has_story = bool(data.get("included_story_pack", False))

    passes = ok and not prod_claimed and has_scorecard and has_story
    status = "PASS" if (passes and fresh) else ("STALE" if not fresh else "FAIL")
    result: dict[str, Any] = {
        "status": status,
        "fresh": fresh,
        "path": str(path),
        "ok": ok,
        "production_readiness_claimed": prod_claimed,
        "included_readiness_scorecard": has_scorecard,
        "included_story_pack": has_story,
        "pack_run_id": data.get("pack_run_id", ""),
    }
    if not fresh:
        result["error"] = "Portfolio evidence pack is stale."
    elif not ok:
        result["error"] = "Portfolio evidence pack has ok=False."
    elif prod_claimed:
        result["error"] = "Portfolio evidence pack claims full production readiness — this is disallowed."
    elif not has_scorecard:
        result["error"] = "Portfolio evidence pack does not include latest readiness scorecard."
    elif not has_story:
        result["error"] = "Portfolio evidence pack does not include latest story pack."
    return result


def _inspect_release_verifier(rd: Path, since_ts: datetime | None) -> dict[str, Any]:
    path = rd / "audit" / "release_candidate_verification.json"
    data, err = _load_json(path)
    if err:
        return {"status": "MISSING", "fresh": False, "path": str(path), "error": err}

    ts = _evidence_ts(data)
    fresh = _is_fresh(ts, since_ts)
    verdict = str(data.get("verdict", "") or "")
    ok = verdict in {"READY", "READY_WITH_KNOWN_LIMITATIONS"}
    status = "PASS" if (ok and fresh) else ("STALE" if not fresh else ("WARN" if ok else "WARN"))
    return {
        "status": status,
        "fresh": fresh,
        "path": str(path),
        "verdict": verdict,
        "ok": ok,
    }


def _inspect_pilot_readiness(rd: Path, since_ts: datetime | None) -> dict[str, Any] | None:
    parent = rd / "pilot_readiness"
    if not parent.is_dir():
        return None
    latest_dir = _find_latest_dir(parent, "*")
    if latest_dir is None:
        return None
    path = latest_dir / "pilot_readiness_scorecard.json"
    data, err = _load_json(path)
    if err:
        return None
    ts = _evidence_ts(data)
    fresh = _is_fresh(ts, since_ts)
    ok = bool(data.get("ok", False))
    score = float(data.get("overall_score", 0) or 0)
    status = "PASS" if (ok and fresh) else ("STALE" if not fresh else "FAIL")
    return {
        "status": status,
        "fresh": fresh,
        "path": str(path),
        "ok": ok,
        "overall_score": score,
    }


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def build_readiness_gate(
    runtime_data_dir: str = "runtime_data",
    threshold: int = 90,
    strict: bool = False,
    since: str | None = None,
) -> dict[str, Any]:
    """Evaluate the readiness evidence gate.

    Parameters
    ----------
    runtime_data_dir:
        Root of the runtime_data directory.
    threshold:
        Minimum overall_score the readiness scorecard must achieve.
    strict:
        If True, missing release verifier evidence is a blocking failure.
    since:
        ISO8601 timestamp string. All evidence must be newer than this.
        If omitted, the gate attempts to read the git HEAD commit timestamp.
        If git is unavailable, freshness is not enforced.
    """
    rd = Path(runtime_data_dir)

    # Resolve the "since" timestamp
    if since is not None:
        since_ts = _parse_ts(since)
    else:
        since_ts = _get_git_head_timestamp()

    # Inspect each evidence artifact
    bv = _inspect_bounded_validation(rd, since_ts)
    sc = _inspect_readiness_scorecard(rd, threshold, since_ts)
    sp = _inspect_story_pack(rd, since_ts)
    pp = _inspect_portfolio_pack(rd, since_ts)
    rv = _inspect_release_verifier(rd, since_ts)
    pilot = _inspect_pilot_readiness(rd, since_ts)

    evidence: dict[str, Any] = {
        EVIDENCE_BOUNDED_VALIDATION: bv,
        EVIDENCE_READINESS_SCORECARD: sc,
        EVIDENCE_STORY_PACK: sp,
        EVIDENCE_PORTFOLIO_PACK: pp,
        EVIDENCE_RELEASE_VERIFIER: rv,
    }
    if pilot is not None:
        evidence[EVIDENCE_PILOT_READINESS] = pilot

    # Collect blocking failures and warnings
    blocking_failures: list[str] = []
    warnings: list[str] = []

    # Required evidence must all PASS
    for key in REQUIRED_EVIDENCE:
        ev = evidence[key]
        status = ev.get("status", "MISSING")
        if status in ("MISSING", "FAIL", "STALE"):
            msg = ev.get("error") or f"{key.replace('_', ' ').title()} is {status.lower()}."
            blocking_failures.append(msg)

    # Release verifier: warning unless strict
    rv_status = rv.get("status", "MISSING")
    if rv_status in ("MISSING", "STALE"):
        msg = rv.get("error") or "Release verifier evidence is missing or stale."
        if strict:
            blocking_failures.append(msg)
        else:
            warnings.append(f"[WARNING] {msg}")
    elif rv_status == "WARN":
        warnings.append(f"[WARNING] Release verifier verdict: {rv.get('verdict', 'unknown')} (not ideal but acceptable).")

    # Score from readiness scorecard (0 if missing)
    overall_score = float(sc.get("score", 0) or 0)

    # Overall status
    ok = len(blocking_failures) == 0
    gate_status = "PASS" if ok else "FAIL"

    # Claim classification
    if ok:
        classification = PASS_CONTROLLED_DEMO_90
    else:
        classification = FAIL_CONTROLLED_DEMO_90

    # Production readiness: always not claimed
    production_readiness_claimed = False
    production_claim_status = PRODUCTION_NOT_CLAIMED

    # Check for disallowed claims in portfolio pack or story pack
    for ev_key in (EVIDENCE_PORTFOLIO_PACK,):
        ev = evidence[ev_key]
        if ev.get("production_readiness_claimed"):
            production_readiness_claimed = True
            production_claim_status = PRODUCTION_CLAIM_BLOCKED
            if "Portfolio evidence pack claims full production readiness" not in " ".join(blocking_failures):
                blocking_failures.append("Portfolio evidence pack claims full production readiness — this is disallowed.")

    # Recommended next steps
    recommended: list[str] = []
    if not ok:
        for key in REQUIRED_EVIDENCE:
            ev = evidence[key]
            if ev.get("status") in ("MISSING", "FAIL"):
                recommended.append(f"Regenerate {key.replace('_', ' ')} to get a fresh passing artifact.")
            elif ev.get("status") == "STALE":
                recommended.append(f"Re-run the {key.replace('_', ' ')} command to refresh the stale artifact.")

    result: dict[str, Any] = {
        "ok": ok,
        "claim": CLAIM_CONTROLLED_DEMO_90,
        "claim_allowed": ok,
        "threshold": threshold,
        "overall_score": overall_score,
        "status": gate_status,
        "classification": classification,
        "production_readiness_claimed": production_readiness_claimed,
        "production_claim_status": production_claim_status,
        "controlled_demo_readiness_claimed": ok,
        "evidence": evidence,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "recommended_next_steps": recommended,
        "generated_at": _utc_now(),
        "disclaimer": CLAIM_DISCLAIMER,
        "allowed_wording": ALLOWED_WORDING if ok else "",
        "disallowed_claims": DISALLOWED_CLAIMS,
    }
    return result


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def write_gate_report(result: dict[str, Any], runtime_data_dir: str = "runtime_data") -> dict[str, Any]:
    """Write JSON, Markdown, and HTML gate reports. Returns paths."""
    rd = Path(runtime_data_dir)
    gate_dir = rd / _GATE_SUBDIR
    gate_dir.mkdir(parents=True, exist_ok=True)

    json_path = gate_dir / _GATE_JSON
    md_path = gate_dir / _GATE_MD
    html_path = gate_dir / _GATE_HTML

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    md_content = _build_markdown(result)
    md_path.write_text(md_content, encoding="utf-8")
    html_path.write_text(_build_html(result, md_content), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "html_path": str(html_path),
    }


def _build_markdown(result: dict[str, Any]) -> str:
    status = result.get("status", "UNKNOWN")
    score = result.get("overall_score", 0)
    threshold = result.get("threshold", 90)
    claim = result.get("claim", "")
    ok = result.get("ok", False)
    classification = result.get("classification", "")
    generated_at = result.get("generated_at", "")
    blocking = result.get("blocking_failures", [])
    warnings = result.get("warnings", [])
    recommended = result.get("recommended_next_steps", [])
    evidence = result.get("evidence", {})
    allowed_wording = result.get("allowed_wording", "")
    disallowed = result.get("disallowed_claims", [])
    disclaimer = result.get("disclaimer", "")

    lines: list[str] = [
        "# Readiness Evidence Gate Report",
        "",
        f"**Generated:** {generated_at}  ",
        f"**Claim:** {claim}  ",
        f"**Verdict:** {status}  ",
        f"**Classification:** {classification}  ",
        f"**Overall Score:** {score:.1f} / {threshold} threshold  ",
        f"**Claim Allowed:** {'Yes' if ok else 'No'}  ",
        "",
        "---",
        "",
        "## Evidence Summary",
        "",
        "| Artifact | Status | Fresh | Path |",
        "|---|---|---|---|",
    ]
    for key, ev in evidence.items():
        ev_status = ev.get("status", "?")
        ev_fresh = "Yes" if ev.get("fresh") else "No"
        ev_path = ev.get("path", "")
        lines.append(f"| {key.replace('_', ' ').title()} | {ev_status} | {ev_fresh} | `{ev_path}` |")

    lines += ["", "## Freshness Details", ""]
    for key, ev in evidence.items():
        ts_ok = "Fresh" if ev.get("fresh") else "Stale / Unknown"
        lines.append(f"- **{key.replace('_', ' ').title()}**: {ts_ok}")

    if blocking:
        lines += ["", "## Blocking Failures", ""]
        for bf in blocking:
            lines.append(f"- {bf}")

    if warnings:
        lines += ["", "## Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")

    if recommended:
        lines += ["", "## Recommended Next Steps", ""]
        for step in recommended:
            lines.append(f"1. {step}")

    lines += ["", "---", "", "## Claim Classification", ""]
    lines.append(f"**{classification}**")
    lines.append("")
    lines.append(f"> {disclaimer}")

    if ok and allowed_wording:
        lines += ["", "## Allowed Portfolio Wording", ""]
        lines.append(f"> {allowed_wording}")

    lines += ["", "## Disallowed Claims", ""]
    lines.append("The following claims are **not** permitted without a separate production-readiness gate:")
    lines.append("")
    for claim_text in disallowed:
        lines.append(f"- {claim_text}")

    return "\n".join(lines) + "\n"


def _build_html(result: dict[str, Any], md_content: str) -> str:
    status = result.get("status", "UNKNOWN")
    colour = "#2d8a4e" if status == "PASS" else "#b03030"
    title = "Readiness Evidence Gate"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.6}}
h1{{color:{colour}}}
.badge{{display:inline-block;padding:.25em .75em;border-radius:4px;font-weight:700;background:{colour};color:#fff}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.4em .75em;text-align:left}}
th{{background:#f0f0f0}}
blockquote{{background:#f9f9f9;border-left:4px solid #ccc;padding:.5em 1em;margin:1em 0}}
pre{{background:#f4f4f4;padding:1em;overflow-x:auto}}
</style>
</head>
<body>
<h1>{title} <span class="badge">{status}</span></h1>
<pre>{md_content}</pre>
</body>
</html>
"""
