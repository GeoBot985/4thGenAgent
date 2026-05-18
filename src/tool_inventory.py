from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.tool_registry import build_tool_registry
from src.toolpack_loader import discover_toolpacks


ROOT = Path(__file__).resolve().parents[1]


def build_tool_inventory_report(
    *,
    runtime_data_dir: str | Path = "runtime_data",
) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    inventory_dir = runtime_root / "tool_inventory"
    inventory_dir.mkdir(parents=True, exist_ok=True)

    registry = build_tool_registry(include_migrated_toolpacks=True, include_external=True, include_legacy_fallback=True)
    discovery = discover_toolpacks(include_disabled=True)
    lifecycle_dir = runtime_root / "toolpacks" / "lifecycle"

    tools: list[dict[str, Any]] = []
    for tool_key, spec in sorted(registry.items()):
        tools.append(
            {
                "tool": tool_key,
                "source": str(spec.get("source", "legacy_fallback")),
                "toolpack_id": str(spec.get("toolpack_id", "")),
                "side_effect": bool(spec.get("side_effect", False)),
                "requires_approval": bool(spec.get("requires_approval", False)),
                "allow_live_side_effect": bool(spec.get("allow_live_side_effect", False)),
                "output_type": str(spec.get("output_type", "")),
                "module": str(spec.get("module", "")),
                "function": str(spec.get("function", "")),
            }
        )

    toolpacks: list[dict[str, Any]] = []
    for pack in discovery.get("toolpacks", []):
        if not isinstance(pack, dict):
            continue
        toolpack_id = str(pack.get("toolpack_id", "")).strip()
        if not toolpack_id:
            continue
        lifecycle = _evaluate_lifecycle_summary(toolpack_id, pack, runtime_root)
        lifecycle_report_md = lifecycle_dir / f"{toolpack_id}_lifecycle.md"
        toolpacks.append(
            {
                "toolpack_id": toolpack_id,
                "status": str(lifecycle.get("status", "UNKNOWN")),
                "enabled_environments": list(lifecycle.get("enabled_environments", [])),
                "classification": str(lifecycle.get("classification", str(pack.get("core_or_optional", "optional")))),
                "tool_count": int(pack.get("tool_count", 0) or 0),
                "last_lifecycle_check": str(lifecycle.get("generated_at", "")),
                "last_lifecycle_report": str(lifecycle_report_md.as_posix()),
                "path": str(pack.get("path", "")),
                "enabled": bool(pack.get("enabled", False)),
                "registered": bool(pack.get("registered", False)),
                "valid": bool(pack.get("valid", False)),
                "source": "external_toolpack",
            }
        )

    summary = {
        "total_tools": len(tools),
        "migrated_toolpack_tools": sum(1 for item in tools if item["source"] == "migrated_toolpack"),
        "legacy_fallback_tools": sum(1 for item in tools if item["source"] == "legacy_fallback"),
        "external_enabled_tools": sum(1 for item in tools if item["source"] == "external_toolpack"),
        "total_toolpacks": len(toolpacks),
        "optional_disabled_tools": sum(
            int(item.get("tool_count", 0) or 0)
            for item in discovery.get("toolpacks", [])
            if isinstance(item, dict) and not item.get("registered", False) and str(item.get("core_or_optional", "optional")) == "optional"
        ),
        "side_effect_tools": sum(1 for item in tools if item["side_effect"]),
        "live_side_effect_allowed": sum(
            1
            for item in tools
            if item["allow_live_side_effect"] and item["source"] != "legacy_fallback"
        ),
    }

    report = {
        "report_type": "tool_inventory",
        "version": 1,
        "generated_at": _utc_now(),
        "ok": True,
        "summary": summary,
        "tools": tools,
        "toolpacks": toolpacks,
        "warnings": [],
        "blockers": [],
    }

    json_path = inventory_dir / "tool_inventory.json"
    markdown_path = inventory_dir / "tool_inventory.md"
    docs_path = ROOT / "docs" / "tool_inventory.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown = render_tool_inventory_markdown(report, json_path=json_path, markdown_path=markdown_path)
    markdown_path.write_text(markdown, encoding="utf-8")
    docs_path.write_text(markdown, encoding="utf-8")
    report["json_path"] = str(json_path)
    report["markdown_path"] = str(markdown_path)
    report["docs_path"] = str(docs_path)
    return report


def render_tool_inventory_markdown(report: dict[str, Any], *, json_path: Path, markdown_path: Path) -> str:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    tools = report.get("tools", []) if isinstance(report, dict) else []
    lines = [
        "# Tool Inventory Report",
        "",
        f"Generated: {report.get('generated_at', '')}",
        "",
        f"Report JSON: {json_path.as_posix()}",
        f"Report Markdown: {markdown_path.as_posix()}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for label, key in [
        ("Total tools", "total_tools"),
        ("Migrated tool-pack tools", "migrated_toolpack_tools"),
        ("Legacy fallback tools", "legacy_fallback_tools"),
        ("External enabled tools", "external_enabled_tools"),
        ("Total tool packs", "total_toolpacks"),
        ("Optional disabled tools", "optional_disabled_tools"),
        ("Side-effect tools", "side_effect_tools"),
        ("Live side-effect allowed", "live_side_effect_allowed"),
    ]:
        lines.append(f"| {label} | {int(summary.get(key, 0) or 0)} |")
    lines.extend([
        "",
        "## Tools",
        "",
        "| Tool | Source | Pack | Side Effect | Requires Approval | Live Side Effect | Output Type |",
        "|---|---|---|---:|---:|---:|---|",
    ])
    for item in tools:
        lines.append(
            "| {tool} | {source} | {toolpack_id} | {side_effect} | {requires_approval} | {allow_live_side_effect} | {output_type} |".format(
                tool=item.get("tool", ""),
                source=item.get("source", ""),
                toolpack_id=item.get("toolpack_id", ""),
                side_effect="yes" if item.get("side_effect") else "no",
                requires_approval="yes" if item.get("requires_approval") else "no",
                allow_live_side_effect="yes" if item.get("allow_live_side_effect") else "no",
                output_type=item.get("output_type", ""),
            )
        )
    lines.extend([
        "",
        "## Tool Packs",
        "",
        "| Tool Pack | Status | Environments | Classification | Tool Count | Last Check | Lifecycle Report |",
        "|---|---|---|---|---:|---|---|",
    ])
    for pack in report.get("toolpacks", []):
        lines.append(
            "| {toolpack_id} | {status} | {enabled_environments} | {classification} | {tool_count} | {last_lifecycle_check} | {last_lifecycle_report} |".format(
                toolpack_id=pack.get("toolpack_id", ""),
                status=pack.get("status", ""),
                enabled_environments=", ".join(pack.get("enabled_environments", [])) or "none",
                classification=pack.get("classification", ""),
                tool_count=int(pack.get("tool_count", 0) or 0),
                last_lifecycle_check=pack.get("last_lifecycle_check", ""),
                last_lifecycle_report=pack.get("last_lifecycle_report", ""),
            )
        )
    return "\n".join(lines) + "\n"


def _utc_now() -> str:
    from runtime.taskframe import utc_now

    return utc_now()


def _evaluate_lifecycle_summary(toolpack_id: str, pack: dict[str, Any], runtime_root: Path) -> dict[str, Any]:
    try:
        from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

        result = evaluate_toolpack_lifecycle(
            pack.get("path", ""),
            environment="dev",
            config_path=Path("config/enabled_toolpacks.json"),
            runtime_data_dir=runtime_root,
            include_contract_tests=False,
            include_health=False,
            include_manifest_smoke=False,
        )
        return {
            "status": result.get("status", "UNKNOWN"),
            "enabled_environments": list(result.get("stage_details", {}).get("governance_policy", {}).get("enabled_environments", [])),
            "classification": str(result.get("stage_details", {}).get("governance_policy", {}).get("classification", pack.get("core_or_optional", "optional"))),
            "generated_at": result.get("generated_at", ""),
        }
    except Exception:
        return {
            "status": "UNKNOWN",
            "enabled_environments": [],
            "classification": str(pack.get("core_or_optional", "optional")),
            "generated_at": _utc_now(),
        }
