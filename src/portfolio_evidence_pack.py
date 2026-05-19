from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.tool_capability_registry import list_tool_capabilities
from src.operator_scenarios import list_scenarios


PACK_ID = "portfolio_evidence_pack_v1"
PACK_TITLE = "TaskFrame Runtime — Controlled Business Automation Evidence Pack"
PORTFOLIO_DIRNAME = "portfolio_evidence"


def build_portfolio_evidence_pack(
    *,
    runtime_data_dir: str = "runtime_data",
    include_latest_story_pack: bool = True,
    include_latest_readiness_scorecard: bool = True,
) -> dict:
    runtime_root = Path(runtime_data_dir)
    pack_run_id = f"{PACK_ID}_{_now_compact()}_{uuid4().hex[:8]}"
    pack_dir = runtime_root / PORTFOLIO_DIRNAME / pack_run_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    known_limitations = _known_limitations()

    latest_story = _find_latest_story_pack(runtime_root) if include_latest_story_pack else None
    latest_readiness = _find_latest_readiness_scorecard(runtime_root) if include_latest_readiness_scorecard else None
    tool_inventory = _collect_tool_inventory()
    workflow_proof = _collect_workflow_proof(latest_story, runtime_root)

    summary = {
        "pack_id": PACK_ID,
        "pack_run_id": pack_run_id,
        "generated_at": _now_iso(),
        "ok": True,
        "project_name": "TaskFrame Runtime",
        "project_type": "controlled_business_automation_runtime",
        "live_side_effects_claimed": False,
        "production_readiness_claimed": False,
        "included_story_pack": bool(latest_story and latest_story.get("ok")),
        "included_readiness_scorecard": bool(latest_readiness and latest_readiness.get("ok")),
        "workflow_count": len(workflow_proof.get("workflow_rows", [])),
        "tool_count": len(tool_inventory.get("rows", [])),
        "evidence_links": [],
        "known_limitations": known_limitations,
        "story_pack_link": latest_story or {},
        "readiness_scorecard_link": latest_readiness or {},
    }

    artifact_paths: dict[str, str] = {}

    summary_path = pack_dir / "summary.json"
    architecture_path = pack_dir / "architecture.md"
    demo_script_path = pack_dir / "demo_script.md"
    tool_inventory_path = pack_dir / "tool_inventory.md"
    workflow_proof_path = pack_dir / "workflow_proof.md"
    screenshot_checklist_path = pack_dir / "screenshot_checklist.md"
    known_limitations_path = pack_dir / "known_limitations.md"
    index_markdown_path = pack_dir / "index.md"
    index_html_path = pack_dir / "index.html"
    readme_path = pack_dir / "README.md"

    _write_json(summary_path, summary)

    architecture_markdown = _render_architecture_markdown()
    demo_script_markdown = _render_demo_script_markdown()
    tool_inventory_markdown = _render_tool_inventory_markdown(tool_inventory)
    workflow_proof_markdown = _render_workflow_proof_markdown(workflow_proof)
    screenshot_checklist_markdown = _render_screenshot_checklist_markdown()
    known_limitations_markdown = _render_known_limitations_markdown(known_limitations)
    index_markdown = _render_index_markdown(
        summary=summary,
        architecture_path=architecture_path,
        demo_script_path=demo_script_path,
        tool_inventory_path=tool_inventory_path,
        workflow_proof_path=workflow_proof_path,
        screenshot_checklist_path=screenshot_checklist_path,
        known_limitations_path=known_limitations_path,
        latest_story=latest_story,
        latest_readiness=latest_readiness,
        workflow_proof=workflow_proof,
        tool_inventory=tool_inventory,
    )

    architecture_path.write_text(architecture_markdown, encoding="utf-8")
    demo_script_path.write_text(demo_script_markdown, encoding="utf-8")
    tool_inventory_path.write_text(tool_inventory_markdown, encoding="utf-8")
    workflow_proof_path.write_text(workflow_proof_markdown, encoding="utf-8")
    screenshot_checklist_path.write_text(screenshot_checklist_markdown, encoding="utf-8")
    known_limitations_path.write_text(known_limitations_markdown, encoding="utf-8")
    index_markdown_path.write_text(index_markdown, encoding="utf-8")
    index_html_path.write_text(_render_index_html(summary, index_markdown, workflow_proof, tool_inventory, latest_story, latest_readiness), encoding="utf-8")
    readme_path.write_text(_render_readme(summary, latest_story, latest_readiness), encoding="utf-8")

    artifact_paths.update(
        {
            "summary_json_path": str(summary_path),
            "architecture_path": str(architecture_path),
            "demo_script_path": str(demo_script_path),
            "tool_inventory_path": str(tool_inventory_path),
            "workflow_proof_path": str(workflow_proof_path),
            "screenshot_checklist_path": str(screenshot_checklist_path),
            "known_limitations_path": str(known_limitations_path),
            "index_markdown_path": str(index_markdown_path),
            "index_html_path": str(index_html_path),
            "readme_path": str(readme_path),
        }
    )

    linked_artifacts: list[dict[str, Any]] = []
    for artifact_id, artifact_type, path in [
        ("index_markdown", "story_index", index_markdown_path),
        ("index_html", "story_index", index_html_path),
        ("summary_json", "summary_json", summary_path),
        ("architecture", "documentation", architecture_path),
        ("demo_script", "documentation", demo_script_path),
        ("tool_inventory", "documentation", tool_inventory_path),
        ("workflow_proof", "documentation", workflow_proof_path),
        ("screenshot_checklist", "documentation", screenshot_checklist_path),
        ("known_limitations", "documentation", known_limitations_path),
        ("readme", "documentation", readme_path),
    ]:
        linked_artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "path": str(path),
                "exists": path.is_file(),
            }
        )

    if latest_story and latest_story.get("ok"):
        story_link_path = pack_dir / "latest_story_pack_link.json"
        story_link = _story_link_payload(latest_story)
        _write_json(story_link_path, story_link)
        linked_artifacts.append(
            {
                "artifact_id": "latest_story_pack_link",
                "artifact_type": "link_json",
                "path": str(story_link_path),
                "exists": story_link_path.is_file(),
            }
        )
        summary["evidence_links"].append(
            {
                "label": "Latest Story Pack",
                "path": story_link.get("index_html_path", ""),
                "link_json_path": str(story_link_path),
            }
        )

    if latest_readiness and latest_readiness.get("ok"):
        readiness_link_path = pack_dir / "latest_readiness_scorecard_link.json"
        readiness_link = _readiness_link_payload(latest_readiness)
        _write_json(readiness_link_path, readiness_link)
        linked_artifacts.append(
            {
                "artifact_id": "latest_readiness_scorecard_link",
                "artifact_type": "link_json",
                "path": str(readiness_link_path),
                "exists": readiness_link_path.is_file(),
            }
        )
        summary["evidence_links"].append(
            {
                "label": "Latest Readiness Scorecard",
                "path": readiness_link.get("html_path", ""),
                "link_json_path": str(readiness_link_path),
            }
        )

    _write_json(summary_path, summary)

    ok = not errors
    result = {
        "ok": ok,
        "pack_id": PACK_ID,
        "pack_run_id": pack_run_id,
        "pack_dir": str(pack_dir),
        "index_markdown_path": str(index_markdown_path),
        "index_html_path": str(index_html_path),
        "summary_json_path": str(summary_path),
        "architecture_path": str(architecture_path),
        "demo_script_path": str(demo_script_path),
        "tool_inventory_path": str(tool_inventory_path),
        "workflow_proof_path": str(workflow_proof_path),
        "screenshot_checklist_path": str(screenshot_checklist_path),
        "linked_artifacts": linked_artifacts,
        "errors": errors,
    }
    return result


def _collect_tool_inventory() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        capabilities = list_tool_capabilities()
        for capability in capabilities:
            limitations = getattr(capability, "limitations", []) or []
            rows.append(
                {
                    "tool_id": str(getattr(capability, "tool_id", "")),
                    "display_name": str(getattr(capability, "display_name", "")),
                    "category": str(getattr(capability, "category", "")),
                    "core_or_optional": str(getattr(capability, "core_or_optional", "")),
                    "side_effect_level": str(getattr(capability, "side_effect_level", "")),
                    "auth_required": bool(getattr(capability, "auth_required", False)),
                    "enabled": bool(getattr(capability, "enabled", True)),
                    "limitations": "; ".join(str(item) for item in limitations if str(item).strip()) or "—",
                }
            )
    except Exception as exc:
        errors.append(f"Tool capability registry unavailable: {exc}")
    return {"rows": rows, "errors": errors}


def _collect_workflow_proof(latest_story: dict[str, Any] | None, runtime_root: Path) -> dict[str, Any]:
    latest_story = latest_story if isinstance(latest_story, dict) else {}
    story_summary = latest_story.get("summary", {}) if isinstance(latest_story.get("summary", {}), dict) else {}
    timeline = latest_story.get("timeline", []) if isinstance(latest_story.get("timeline", []), list) else []
    timeline_by_scenario = {
        str(item.get("scenario_id", "")): item
        for item in timeline
        if isinstance(item, dict) and str(item.get("scenario_id", "")).strip()
    }
    latest_story_pack_dir = str(latest_story.get("story_pack_dir", "")).strip()
    latest_story_ok = bool(latest_story.get("ok", False))

    workflow_specs = [
        {
            "workflow_id": "customer_support",
            "scenario_id": "customer_status_approve_execute_dry_run",
            "purpose": "Customer support order status response.",
            "lane": "customer_support",
        },
        {
            "workflow_id": "order_management",
            "scenario_id": "order_validate_new_happy_path",
            "purpose": "Order validation and shipment context.",
            "lane": "order_management",
        },
        {
            "workflow_id": "procurement",
            "scenario_id": "procurement_low_stock_approve_execute_dry_run",
            "purpose": "Low-stock procurement and reorder handling.",
            "lane": "procurement",
        },
        {
            "workflow_id": "supplier_invoice_matching",
            "scenario_id": "supplier_invoice_match_approve_execute_dry_run",
            "purpose": "Supplier invoice three-way matching and exception handling.",
            "lane": "accounting",
        },
        {
            "workflow_id": "accounting",
            "scenario_id": "accounting_payment_reconciliation_approve_execute_dry_run",
            "purpose": "Payment reconciliation and accounting evidence generation.",
            "lane": "accounting",
        },
        {
            "workflow_id": "cross_workflow_story",
            "scenario_id": "cross_workflow_business_demo_v2",
            "purpose": "Cross-workflow business automation story evidence pack.",
            "lane": "cross_workflow",
        },
    ]
    scenario_lookup = {scenario["id"]: scenario for scenario in list_scenarios(include_test_only=False)}
    workflow_rows: list[dict[str, Any]] = []
    for spec in workflow_specs:
        workflow_id = spec["workflow_id"]
        scenario_id = spec["scenario_id"]
        purpose = spec["purpose"]
        lane = spec["lane"]
        scenario = scenario_lookup.get(scenario_id, {})
        row = {
            "workflow_id": workflow_id,
            "scenario_id": scenario_id,
            "purpose": purpose,
            "final_state": "not available in this build",
            "pending_actions": "not available in this build",
            "executed_dry_run_actions": "not available in this build",
            "reports": [],
            "evidence": [],
            "status": "not available in this build",
        }
        if scenario:
            row["purpose"] = str(scenario.get("description", purpose))

        if workflow_id == "cross_workflow_story" and latest_story_ok:
            row.update(
                {
                    "final_state": "COMPLETED" if latest_story_ok else "FAILED",
                    "pending_actions": int(story_summary.get("total_pending_actions", 0) or 0),
                    "executed_dry_run_actions": int(story_summary.get("total_executed_actions", 0) or 0),
                    "reports": [
                        str(latest_story.get("index_markdown_path", "")),
                        str(latest_story.get("index_html_path", "")),
                    ],
                    "evidence": [
                        str(latest_story.get("evidence_manifest_path", "")),
                        str(latest_story.get("summary_json_path", "")),
                    ],
                    "status": "available",
                }
            )
        else:
            matched = timeline_by_scenario.get(scenario_id, {})
            if matched:
                row.update(
                    {
                        "final_state": str(matched.get("state", "not available in this build")),
                        "pending_actions": int(matched.get("pending_action_count", 0) or 0),
                        "executed_dry_run_actions": int(matched.get("executed_action_count", 0) or 0),
                        "reports": [
                            str(matched.get("report_path", "")),
                            str(matched.get("html_report_path", "")),
                        ],
                        "evidence": [str(matched.get("evidence_bundle_path", ""))],
                        "status": "available",
                    }
                )
            elif workflow_id in {"customer_support", "procurement", "accounting"} and latest_story_ok:
                lane_match = next((item for item in timeline if isinstance(item, dict) and str(item.get("lane", "")) == lane), {})
                if lane_match:
                    row.update(
                        {
                            "final_state": str(lane_match.get("state", "not available in this build")),
                            "pending_actions": int(lane_match.get("pending_action_count", 0) or 0),
                            "executed_dry_run_actions": int(lane_match.get("executed_action_count", 0) or 0),
                            "reports": [
                                str(lane_match.get("report_path", "")),
                                str(lane_match.get("html_report_path", "")),
                            ],
                            "evidence": [str(lane_match.get("evidence_bundle_path", ""))],
                            "status": "available",
                        }
                    )
        workflow_rows.append(row)
    return {
        "workflow_rows": workflow_rows,
        "latest_story_pack_dir": latest_story_pack_dir,
        "latest_story_ok": latest_story_ok,
    }


def _find_latest_story_pack(runtime_root: Path) -> dict[str, Any] | None:
    candidates = []
    for summary_path in runtime_root.glob("demo_packs/*/story_pack/summary.json"):
        if not summary_path.is_file():
            continue
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        story_pack_dir = summary_path.parent
        index_md = story_pack_dir / "index.md"
        index_html = story_pack_dir / "index.html"
        evidence_manifest = story_pack_dir / "evidence_manifest.json"
        workflow_timeline = story_pack_dir / "workflow_timeline.json"
        candidates.append(
            {
                "summary_path": summary_path,
                "mtime": summary_path.stat().st_mtime,
                "payload": payload,
                "story_pack_dir": story_pack_dir,
                "index_markdown_path": index_md,
                "index_html_path": index_html,
                "evidence_manifest_path": evidence_manifest,
                "workflow_timeline_path": workflow_timeline,
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item["mtime"], reverse=True)
    candidate = candidates[0]
    summary = candidate["payload"] if isinstance(candidate.get("payload"), dict) else {}
    timeline = []
    workflow_timeline_path = candidate["workflow_timeline_path"]
    if workflow_timeline_path.is_file():
        try:
            timeline_payload = json.loads(workflow_timeline_path.read_text(encoding="utf-8"))
            timeline = timeline_payload.get("timeline", []) if isinstance(timeline_payload, dict) else []
        except Exception:
            timeline = []
    return {
        "ok": True,
        "pack_id": str(summary.get("pack_id", "")),
        "pack_run_id": str(summary.get("pack_run_id", "")),
        "story_title": str(summary.get("story_title", "")),
        "story_pack_dir": str(candidate["story_pack_dir"]),
        "index_markdown_path": str(candidate["index_markdown_path"]),
        "index_html_path": str(candidate["index_html_path"]),
        "summary_json_path": str(candidate["summary_path"]),
        "evidence_manifest_path": str(candidate["evidence_manifest_path"]),
        "workflow_timeline_path": str(candidate["workflow_timeline_path"]),
        "summary": summary,
        "timeline": timeline,
    }


def _find_latest_readiness_scorecard(runtime_root: Path) -> dict[str, Any] | None:
    summary_path = runtime_root / "readiness" / "readiness_scorecard.json"
    if not summary_path.is_file():
        return None
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    report_paths = payload.get("report_paths", {}) if isinstance(payload, dict) else {}
    return {
        "ok": bool(payload.get("ok", False)),
        "status": str(payload.get("status", "")),
        "overall_score": payload.get("overall_score", 0),
        "threshold": payload.get("threshold", 90),
        "generated_at": payload.get("generated_at", ""),
        "json_path": str(report_paths.get("json_path", summary_path)),
        "markdown_path": str(report_paths.get("markdown_path", runtime_root / "readiness" / "readiness_scorecard.md")),
        "html_path": str(report_paths.get("html_path", runtime_root / "readiness" / "readiness_scorecard.html")),
        "summary_json_path": str(summary_path),
    }


def _render_index_markdown(
    *,
    summary: dict[str, Any],
    architecture_path: Path,
    demo_script_path: Path,
    tool_inventory_path: Path,
    workflow_proof_path: Path,
    screenshot_checklist_path: Path,
    known_limitations_path: Path,
    latest_story: dict[str, Any] | None,
    latest_readiness: dict[str, Any] | None,
    workflow_proof: dict[str, Any],
    tool_inventory: dict[str, Any],
) -> str:
    story_label = latest_story.get("story_title", "none") if isinstance(latest_story, dict) else "none"
    readiness_status = latest_readiness.get("status", "not available") if isinstance(latest_readiness, dict) else "not available"
    lines = [
        "# TaskFrame Runtime — Portfolio Evidence Pack",
        "",
        "## Executive Summary",
        "",
        "This portfolio pack presents TaskFrame as a controlled business automation runtime. It is evidence for a demo and portfolio system, not proof of production deployment readiness.",
        "",
        f"- Pack ID: {summary.get('pack_id', '')}",
        f"- Pack Run ID: {summary.get('pack_run_id', '')}",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Included Story Pack: {str(bool(summary.get('included_story_pack'))).lower()}",
        f"- Included Readiness Scorecard: {str(bool(summary.get('included_readiness_scorecard'))).lower()}",
        "",
        "## What This Project Demonstrates",
        "",
        "- Manifest-driven workflow execution",
        "- TaskFrame state tracking and evidence capture",
        "- Registered tools with governance and safety controls",
        "- Bounded LLM assistance for fuzzy drafting steps",
        "- Approval-gated side effects and dry-run execution",
        "- Consolidated reporting for reviewers and stakeholders",
        "",
        "## Architecture Overview",
        "",
        f"See [{architecture_path.name}]({architecture_path.name}) for the full runtime model.",
        "",
        "## Demo Workflow Summary",
        "",
        f"Latest story pack included: {story_label}",
        "",
        f"See [{workflow_proof_path.name}]({workflow_proof_path.name}) for workflow-by-workflow proof.",
        "",
        "## Runtime Controls",
        "",
        "- Execution is controlled by manifests, validations, approvals, and governance checks.",
        "- The LLM assists bounded steps; it is not the controller.",
        "- Live side effects remain blocked or approval-staged in this repository state.",
        "",
        "## Tool Inventory",
        "",
        f"Tool count captured: {summary.get('tool_count', 0)}",
        "",
        f"See [{tool_inventory_path.name}]({tool_inventory_path.name}) for the tool capability table.",
        "",
        "## Evidence Links",
        "",
    ]
    for item in summary.get("evidence_links", []):
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('label', 'Evidence')}: {item.get('path', '')}")
    if not summary.get("evidence_links"):
        lines.append("- No linked story/readiness artifacts were available in this build.")
    lines.extend(
        [
            "",
            "## Readiness Status",
            "",
            f"Latest readiness scorecard: {readiness_status}",
            "",
            f"See [{Path(known_limitations_path).name}]({Path(known_limitations_path).name}) for limitations.",
            "",
            "## Known Limitations",
            "",
            "This repository is a controlled portfolio/demo runtime. It is not production live automation.",
            "",
            "## How to Run the Demo",
            "",
            f"- {Path(demo_script_path).name} contains the suggested demo narrative and commands.",
            "",
            "## Screenshot Checklist",
            "",
            f"- {Path(screenshot_checklist_path).name} lists the capture steps for a reviewer-facing walkthrough.",
            "",
            "## Conclusion",
            "",
            "The evidence pack shows a controlled business automation runtime with traceable workflows, approval gates, dry-run execution, and explicit limitations.",
        ]
    )
    return "\n".join(lines)


def _render_architecture_markdown() -> str:
    return "\n".join(
        [
            "# Architecture Summary",
            "",
            "## Command / Event",
            "TaskFrame accepts command and event triggers, resolves routes, and binds each incoming request to a manifest-driven workflow.",
            "",
            "## Manifest",
            "The manifest defines the workflow contract: inputs, steps, validations, completion rules, and side-effect policy.",
            "",
            "## TaskFrame",
            "TaskFrame stores workflow state, outputs, validations, pending actions, and evidence for each run.",
            "",
            "## Orchestrator",
            "The orchestrator coordinates execution, but it does not own the domain logic for business decisions.",
            "",
            "## Tools",
            "Registered tools perform deterministic reads, staged writes, and approved dry-run execution. Tool access is governance controlled.",
            "",
            "## Bounded LLM",
            "The LLM is a bounded helper for drafting and extraction. The LLM is not the controller.",
            "",
            "## Validation",
            "Deterministic validations enforce contract shape, completion rules, safety checks, and workflow invariants.",
            "",
            "## Approval Gate",
            "Side effects are approval-gated. Pending actions are staged before execution and can be executed only through approved dry-run paths in this repository state.",
            "",
            "## Evidence Pack",
            "Reports, summaries, and evidence bundles are generated as reviewer-facing artifacts so the business process remains auditable.",
        ]
    )


def _render_demo_script_markdown() -> str:
    return "\n".join(
        [
            "# Demo Script",
            "",
            "## Setup",
            "Open the operator UI or use the CLI in a clean-clone environment.",
            "",
            "## What to Show First",
            "Show the demo selector, tool capability registry, and the current safety controls.",
            "",
            "## Run Cross-Workflow Demo",
            "Run the connected business story through customer support, procurement, and accounting.",
            "",
            "## Open Story Evidence Pack",
            "Open the consolidated story pack generated by the cross-workflow demo.",
            "",
            "## Open Readiness Scorecard",
            "Open the 90% readiness scorecard to show the measured readiness posture.",
            "",
            "## Explain Controls",
            "Explain manifests, TaskFrames, bounded LLM usage, governance, approvals, and dry-run execution.",
            "",
            "## Explain Limitations",
            "State clearly that this is a controlled portfolio demo, not production live automation.",
            "",
            "## Closing Summary",
            "Summarize the evidence pack and highlight the traceable runtime controls.",
            "",
            "Suggested CLI commands:",
            "",
            "- `taskframe demo cross-workflow-v2`",
            "- `taskframe readiness`",
            "- `taskframe portfolio-pack`",
        ]
    )


def _render_tool_inventory_markdown(tool_inventory: dict[str, Any]) -> str:
    rows = tool_inventory.get("rows", []) if isinstance(tool_inventory, dict) else []
    lines = [
        "# Tool Inventory",
        "",
        "This table lists available tools from the tool capability registry.",
        "",
        "| Tool ID | Display Name | Category | Core/Optional | Side Effect Level | Auth Required | Enabled | Limitations |",
        "|---|---|---|---|---|---|---|---|",
    ]
    if not rows:
        lines.append("| registry_error | Tool capability registry unavailable | — | — | — | — | — | See errors in pack summary |")
    else:
        for item in rows:
            lines.append(
                "| {tool_id} | {display_name} | {category} | {core_or_optional} | {side_effect_level} | {auth_required} | {enabled} | {limitations} |".format(
                    tool_id=item.get("tool_id", ""),
                    display_name=item.get("display_name", ""),
                    category=item.get("category", ""),
                    core_or_optional=item.get("core_or_optional", ""),
                    side_effect_level=item.get("side_effect_level", ""),
                    auth_required="yes" if item.get("auth_required") else "no",
                    enabled="yes" if item.get("enabled") else "no",
                    limitations=item.get("limitations", ""),
                )
            )
    return "\n".join(lines)


def _render_workflow_proof_markdown(workflow_proof: dict[str, Any]) -> str:
    rows = workflow_proof.get("workflow_rows", []) if isinstance(workflow_proof, dict) else []
    lines = [
        "# Workflow Proof",
        "",
        "This section summarizes the available business workflows and links them to the latest evidence where available.",
        "",
        "| Workflow | Scenario / Workflow ID | Purpose | Final State | Pending Actions | Executed Dry-Run Actions | Reports / Evidence Links |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in rows:
        links = [str(link) for link in (item.get("reports", []) or []) + (item.get("evidence", []) or []) if str(link).strip()]
        lines.append(
            "| {workflow_id} | {scenario_id} | {purpose} | {final_state} | {pending_actions} | {executed_dry_run_actions} | {links} |".format(
                workflow_id=item.get("workflow_id", ""),
                scenario_id=item.get("scenario_id", ""),
                purpose=item.get("purpose", ""),
                final_state=item.get("final_state", ""),
                pending_actions=item.get("pending_actions", ""),
                executed_dry_run_actions=item.get("executed_dry_run_actions", ""),
                links=", ".join(links) if links else "not available in this build",
            )
        )
    return "\n".join(lines)


def _render_screenshot_checklist_markdown() -> str:
    return "\n".join(
        [
            "# Screenshot Checklist",
            "",
            "- Operator console home/demo view",
            "- Tool capability registry",
            "- Cross-workflow demo selection",
            "- Cross-workflow demo completed",
            "- Approval/dry-run evidence",
            "- Story evidence pack index.html",
            "- Readiness scorecard",
            "- Portfolio evidence pack index.html",
            "- Manifest workbench",
            "- Release verification output",
            "- Portfolio pack review notes",
        ]
    )


def _render_known_limitations_markdown(known_limitations: list[str]) -> str:
    lines = [
        "# Known Limitations",
        "",
        "This is a controlled portfolio/demo runtime, not production live automation.",
        "",
    ]
    for limitation in known_limitations:
        lines.append(f"- {limitation}")
    return "\n".join(lines)


def _render_index_html(
    summary: dict[str, Any],
    markdown: str,
    workflow_proof: dict[str, Any],
    tool_inventory: dict[str, Any],
    latest_story: dict[str, Any] | None,
    latest_readiness: dict[str, Any] | None,
) -> str:
    workflow_rows = workflow_proof.get("workflow_rows", []) if isinstance(workflow_proof, dict) else []
    tool_rows = tool_inventory.get("rows", []) if isinstance(tool_inventory, dict) else []

    workflow_html_rows = []
    for item in workflow_rows:
        workflow_html_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('workflow_id', '')))}</td>"
            f"<td>{escape(str(item.get('scenario_id', '')))}</td>"
            f"<td>{escape(str(item.get('final_state', '')))}</td>"
            f"<td>{escape(str(item.get('pending_actions', '')))}</td>"
            f"<td>{escape(str(item.get('executed_dry_run_actions', '')))}</td>"
            "</tr>"
        )

    tool_html_rows = []
    for item in tool_rows:
        tool_html_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('tool_id', '')))}</td>"
            f"<td>{escape(str(item.get('display_name', '')))}</td>"
            f"<td>{escape(str(item.get('category', '')))}</td>"
            f"<td>{escape(str(item.get('core_or_optional', '')))}</td>"
            f"<td>{escape(str(item.get('side_effect_level', '')))}</td>"
            f"<td>{escape('yes' if item.get('auth_required') else 'no')}</td>"
            f"<td>{escape('yes' if item.get('enabled') else 'no')}</td>"
            f"<td>{escape(str(item.get('limitations', '')))}</td>"
            "</tr>"
        )

    evidence_links = summary.get("evidence_links", []) if isinstance(summary, dict) else []
    evidence_html = "".join(
        f"<li><strong>{escape(str(item.get('label', 'Evidence')))}:</strong> {escape(str(item.get('path', '')))}</li>"
        for item in evidence_links
        if isinstance(item, dict)
    ) or "<li>No linked story/readiness artifacts were available in this build.</li>"

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(PACK_TITLE)}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.5;background:#fff;color:#111}"
        ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}"
        ".card{border:1px solid #ddd;border-radius:10px;padding:12px;background:#fafafa}"
        "table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #ccc;padding:8px;text-align:left}"
        "th{background:#f0f0f0}code,pre{background:#f6f6f6;border-radius:6px}pre{padding:12px;overflow:auto}"
        "</style></head><body>"
        f"<h1>{escape(PACK_TITLE)}</h1>"
        "<p>This portfolio pack is evidence for a controlled demo system. It must not be represented as proof of production readiness.</p>"
        "<div class='cards'>"
        f"<div class='card'><strong>Pack ID</strong><br>{escape(str(summary.get('pack_id', '')))}</div>"
        f"<div class='card'><strong>Pack Run ID</strong><br>{escape(str(summary.get('pack_run_id', '')))}</div>"
        f"<div class='card'><strong>Story Pack</strong><br>{escape('included' if summary.get('included_story_pack') else 'not included')}</div>"
        f"<div class='card'><strong>Readiness Scorecard</strong><br>{escape('included' if summary.get('included_readiness_scorecard') else 'not included')}</div>"
        f"<div class='card'><strong>Tool Count</strong><br>{escape(str(summary.get('tool_count', 0)))}</div>"
        f"<div class='card'><strong>Workflow Count</strong><br>{escape(str(summary.get('workflow_count', 0)))}</div>"
        "</div>"
        "<h2>Executive Summary</h2>"
        f"<p>Generated at {escape(str(summary.get('generated_at', '')))} for a controlled business automation runtime.</p>"
        "<h2>Architecture Overview</h2>"
        "<ul>"
        "<li>Command/Event intake and manifest-driven workflow execution</li>"
        "<li>TaskFrame state tracking and evidence capture</li>"
        "<li>Bounded LLM assistance, not LLM control</li>"
        "<li>Approval-gated side effects and dry-run execution</li>"
        "</ul>"
        "<h2>Workflow Table</h2>"
        "<table><thead><tr><th>Workflow</th><th>Scenario / Workflow ID</th><th>Final State</th><th>Pending Actions</th><th>Executed Dry-Run Actions</th></tr></thead><tbody>"
        + "".join(workflow_html_rows)
        + "</tbody></table>"
        "<h2>Tool Summary</h2>"
        "<table><thead><tr><th>Tool ID</th><th>Display Name</th><th>Category</th><th>Core/Optional</th><th>Side Effect Level</th><th>Auth Required</th><th>Enabled</th><th>Limitations</th></tr></thead><tbody>"
        + "".join(tool_html_rows)
        + "</tbody></table>"
        "<h2>Evidence Links</h2><ul>"
        + evidence_html
        + "</ul>"
        "<h2>Readiness Status</h2>"
        f"<p>Latest readiness scorecard: {escape(str(latest_readiness.get('status', 'not available') if isinstance(latest_readiness, dict) else 'not available'))}</p>"
        "<h2>Known Limitations</h2>"
        f"<p>{escape('This is a controlled portfolio/demo runtime, not production live automation.')}</p>"
        "<h2>Rendered Markdown</h2><pre>"
        + escape(markdown)
        + "</pre></body></html>"
    )


def _render_readme(summary: dict[str, Any], latest_story: dict[str, Any] | None, latest_readiness: dict[str, Any] | None) -> str:
    story_path = str(latest_story.get("index_html_path", "")) if isinstance(latest_story, dict) else ""
    readiness_path = str(latest_readiness.get("html_path", "")) if isinstance(latest_readiness, dict) else ""
    return "\n".join(
        [
            "# Portfolio Evidence Pack",
            "",
            "This folder contains a public-facing evidence pack for the TaskFrame runtime.",
            "",
            f"- Pack ID: {summary.get('pack_id', '')}",
            f"- Pack Run ID: {summary.get('pack_run_id', '')}",
            "",
            "Open `index.html` first.",
            "",
            f"Latest story pack: {story_path or 'not included'}",
            f"Latest readiness scorecard: {readiness_path or 'not included'}",
        ]
    )


def _story_link_payload(latest_story: dict[str, Any]) -> dict[str, Any]:
    return {
        "pack_id": latest_story.get("pack_id", ""),
        "pack_run_id": latest_story.get("pack_run_id", ""),
        "story_title": latest_story.get("story_title", ""),
        "story_pack_dir": latest_story.get("story_pack_dir", ""),
        "index_markdown_path": latest_story.get("index_markdown_path", ""),
        "index_html_path": latest_story.get("index_html_path", ""),
        "summary_json_path": latest_story.get("summary_json_path", ""),
        "evidence_manifest_path": latest_story.get("evidence_manifest_path", ""),
        "workflow_timeline_path": latest_story.get("workflow_timeline_path", ""),
    }


def _readiness_link_payload(latest_readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": latest_readiness.get("status", ""),
        "overall_score": latest_readiness.get("overall_score", 0),
        "threshold": latest_readiness.get("threshold", 90),
        "json_path": latest_readiness.get("json_path", ""),
        "markdown_path": latest_readiness.get("markdown_path", ""),
        "html_path": latest_readiness.get("html_path", ""),
        "summary_json_path": latest_readiness.get("summary_json_path", ""),
    }


def _known_limitations() -> list[str]:
    return [
        "This is a controlled portfolio/demo runtime, not production live automation.",
        "Live side effects are blocked or approval-staged.",
        "External systems may require credentials.",
        "Some workflows use seeded demo data.",
        "RPA is not part of the default release path.",
        "Production deployment would require security, monitoring, tenancy, and operational hardening.",
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
