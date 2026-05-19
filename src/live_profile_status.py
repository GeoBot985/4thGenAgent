from __future__ import annotations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def build_controlled_live_profile_status(
    *,
    runtime_data_dir: str = "runtime_data",
) -> dict:
    from src.controlled_live_profile import (
        CONTROLLED_LIVE_READ_PROFILE,
        ALLOWED_LIVE_READ_TOOLS,
        BLOCKED_LIVE_SIDE_EFFECT_TOOLS,
    )
    warnings: list[str] = []
    errors: list[str] = []

    # Check governance
    governance_ok = True
    try:
        from runtime.runtime_environment import load_runtime_profile
        runtime_profile = load_runtime_profile()
        governance_ok = bool(runtime_profile.get("governance_enforced", True))
    except Exception as exc:
        governance_ok = False
        errors.append(f"Could not load runtime profile: {exc}")

    # Google workspace readiness
    google_workspace_readiness = _check_google_workspace_readiness()

    return {
        "ok": not bool(errors),
        "profile_id": CONTROLLED_LIVE_READ_PROFILE["profile_id"],
        "allow_live_reads": CONTROLLED_LIVE_READ_PROFILE["allow_live_reads"],
        "allow_live_side_effects": CONTROLLED_LIVE_READ_PROFILE["allow_live_side_effects"],
        "governance_ok": governance_ok,
        "google_workspace_readiness": google_workspace_readiness,
        "blocked_tool_classes": CONTROLLED_LIVE_READ_PROFILE["blocked_tool_classes"],
        "allowed_read_tools": ALLOWED_LIVE_READ_TOOLS,
        "blocked_side_effect_tools": BLOCKED_LIVE_SIDE_EFFECT_TOOLS,
        "warnings": warnings,
        "errors": errors,
    }


def _check_google_workspace_readiness() -> dict:
    """Returns readiness dict without requiring real credentials."""
    try:
        from tool_packs.google_workspace.health import check_health
        health = check_health(live=False)
        return {
            "available": True,
            "health_ok": health.get("ok", False),
            "details": health,
        }
    except Exception as exc:
        return {"available": False, "health_ok": False, "details": {"error": str(exc)}}


def write_controlled_live_profile_report(
    *,
    runtime_data_dir: str = "runtime_data",
) -> dict[str, Path]:
    """Generate JSON + Markdown + HTML reports. Returns dict of written paths."""
    import json
    status = build_controlled_live_profile_status(runtime_data_dir=runtime_data_dir)
    out_dir = Path(runtime_data_dir) / "live_profiles"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "controlled_live_read_status.json"
    md_path = out_dir / "controlled_live_read_status.md"
    html_path = out_dir / "controlled_live_read_status.html"

    json_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_md(status), encoding="utf-8")
    html_path.write_text(_render_html(status), encoding="utf-8")
    return {"json": json_path, "md": md_path, "html": html_path}


def _render_md(status: dict) -> str:
    lines = [
        "# Controlled Live Read Profile",
        "",
        "## Summary",
        "",
        f"- Profile ID: `{status['profile_id']}`",
        f"- Live reads allowed: {str(status['allow_live_reads']).lower()}",
        f"- Live side effects allowed: {str(status['allow_live_side_effects']).lower()}",
        f"- Governance OK: {str(status['governance_ok']).lower()}",
        "",
        "## Allowed Live Reads",
        "",
    ]
    for tool in status.get("allowed_read_tools", []):
        lines.append(f"- `{tool}`")
    lines += ["", "## Blocked Side Effects", ""]
    for tool in status.get("blocked_side_effect_tools", []):
        lines.append(f"- `{tool}`")
    lines += ["", "## Governance Status", "",
              f"- Governance enforced: {str(status['governance_ok']).lower()}",
              "", "## Tool Readiness", ""]
    gw = status.get("google_workspace_readiness", {})
    lines.append(f"- Google Workspace available: {str(gw.get('available', False)).lower()}")
    lines.append(f"- Google Workspace health OK: {str(gw.get('health_ok', False)).lower()}")
    lines += ["", "## Credential Status", "",
              "- Credentials are not checked without live credentials configured.",
              "", "## Safety Rules", "",
              "- Live reads may access real external data.",
              "- Live writes, sends, deletes, and RPA actions remain blocked.",
              "", "## Known Limitations", "",
              "- This profile does not allow production live automation or live side effects.",
              "- Real Google credentials are required to use live read tools.",
              "- RPA is always blocked in this profile.",
              ]
    if status.get("errors"):
        lines += ["", "## Errors", ""]
        for err in status["errors"]:
            lines.append(f"- {err}")
    if status.get("warnings"):
        lines += ["", "## Warnings", ""]
        for w in status["warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def _render_html(status: dict) -> str:
    import html as html_module
    body = html_module.escape(_render_md(status)).replace("\n", "<br>\n")
    return f"<!DOCTYPE html>\n<html><head><title>Controlled Live Read Profile</title></head>\n<body>\n<pre>{body}</pre>\n</body></html>\n"
