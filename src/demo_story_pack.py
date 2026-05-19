from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_cross_workflow_story_pack(
    pack_result: dict,
    *,
    runtime_data_dir: str = "runtime_data",
) -> dict:
    pack_result = pack_result if isinstance(pack_result, dict) else {}
    pack_id = str(pack_result.get("pack_id", "")).strip()
    pack_run_id = str(pack_result.get("pack_run_id", "")).strip()
    story_title = str(pack_result.get("story_title") or pack_result.get("label") or pack_result.get("title") or "").strip()
    if not pack_id or not pack_run_id or not story_title:
        return _failure(pack_run_id=pack_run_id, errors=["Pack result is missing pack_id, pack_run_id, or story_title."])
    if not pack_result.get("ok", False):
        return _failure(pack_run_id=pack_run_id, errors=[str(pack_result.get("error", "Pack result is not ok.")) or "Pack result is not ok."])

    pack_dir = Path(runtime_data_dir) / "demo_packs" / pack_run_id / "story_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _now()
    workflow_results = pack_result.get("workflow_results", [])
    summary = pack_result.get("summary", {}) if isinstance(pack_result.get("summary", {}), dict) else {}

    timeline = _build_timeline(pack_result)
    timeline_path = pack_dir / "workflow_timeline.json"
    _write_json(timeline_path, {
        "pack_id": pack_id,
        "pack_run_id": pack_run_id,
        "generated_at": generated_at,
        "timeline": timeline,
    })

    summary_json = {
        "pack_id": pack_id,
        "pack_run_id": pack_run_id,
        "story_title": story_title,
        "started_at": str(pack_result.get("started_at", "")),
        "ended_at": str(pack_result.get("ended_at", "")),
        "duration_ms": int(pack_result.get("duration_ms", 0) or 0),
        "ok": bool(pack_result.get("ok", False)),
        "dry_run_only": bool(pack_result.get("dry_run_only", True)),
        "live_side_effects_performed": bool(pack_result.get("live_side_effects_performed", False)),
        "workflow_count": int(summary.get("workflow_count", len(workflow_results)) or 0),
        "completed_count": int(summary.get("completed_count", 0) or 0),
        "failed_count": int(summary.get("failed_count", 0) or 0),
        "total_pending_actions": int(summary.get("total_pending_actions", 0) or 0),
        "total_executed_actions": int(summary.get("total_executed_actions", 0) or 0),
        "total_llm_calls": int(summary.get("total_llm_calls", 0) or 0),
        "total_tool_calls": int(summary.get("total_tool_calls", 0) or 0),
        "reports_generated": int(summary.get("reports_generated", 0) or 0),
        "evidence_bundles_generated": int(summary.get("evidence_bundles_generated", 0) or 0),
        "workflow_results": workflow_results,
    }
    summary_json_path = pack_dir / "summary.json"
    _write_json(summary_json_path, summary_json)

    index_markdown_path = pack_dir / "index.md"
    index_html_path = pack_dir / "index.html"
    artifact_specs = _build_artifact_specs(pack_result, pack_dir, timeline)
    markdown = _render_markdown(pack_result, summary_json, artifact_specs, timeline)
    index_markdown_path.write_text(markdown, encoding="utf-8")
    index_html_path.write_text(_render_html(pack_result, summary_json, artifact_specs, timeline, markdown), encoding="utf-8")

    screenshots_path = pack_dir / "screenshots_checklist.md"
    screenshots_path.write_text(_render_screenshots_checklist(), encoding="utf-8")

    readme_path = pack_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Cross-Workflow Story Pack",
                "",
                "This folder is a consolidated evidence pack for the cross-workflow demo run.",
                "",
                f"- Pack ID: {pack_id}",
                f"- Pack Run ID: {pack_run_id}",
                f"- Story Title: {story_title}",
                "",
                "Open `index.html` for the reviewer-facing overview.",
            ]
        ),
        encoding="utf-8",
    )

    evidence_manifest = _finalize_evidence_manifest(artifact_specs, pack_result, generated_at)
    evidence_manifest_path = pack_dir / "evidence_manifest.json"
    _write_json(evidence_manifest_path, evidence_manifest)
    if evidence_manifest.get("errors"):
        return _failure(pack_run_id=pack_run_id, errors=[str(item) for item in evidence_manifest.get("errors", []) if item])

    linked_artifacts = [artifact for artifact in evidence_manifest.get("artifacts", []) if isinstance(artifact, dict)]
    return {
        "ok": True,
        "pack_run_id": pack_run_id,
        "story_pack_dir": str(pack_dir),
        "index_markdown_path": str(index_markdown_path),
        "index_html_path": str(index_html_path),
        "summary_json_path": str(summary_json_path),
        "evidence_manifest_path": str(evidence_manifest_path),
        "linked_artifacts": linked_artifacts,
        "errors": [],
    }


def _build_timeline(pack_result: dict) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for sequence, workflow in enumerate(pack_result.get("workflow_results", []) or [], start=1):
        if not isinstance(workflow, dict):
            continue
        report_result = workflow.get("report_result", {}) if isinstance(workflow.get("report_result", {}), dict) else {}
        summary = workflow.get("summary", {}) if isinstance(workflow.get("summary", {}), dict) else {}
        timeline.append(
            {
                "sequence": sequence,
                "lane": str(workflow.get("lane", "")),
                "scenario_id": str(workflow.get("scenario_id", "")),
                "frame_id": str(workflow.get("frame_id", "")),
                "manifest_id": str(workflow.get("manifest_id", "")),
                "state": str(workflow.get("state", "")),
                "pending_action_count": int(workflow.get("pending_action_count", 0) or 0),
                "executed_action_count": int(workflow.get("executed_action_count", 0) or 0),
                "llm_call_count": len(summary.get("llm_calls", []) if isinstance(summary.get("llm_calls", []), list) else []),
                "tool_call_count": len(summary.get("tool_calls", []) if isinstance(summary.get("tool_calls", []), list) else []),
                "report_path": str(report_result.get("markdown_path", "")),
                "html_report_path": str(report_result.get("html_path", "")),
                "evidence_bundle_path": str(report_result.get("evidence_bundle_path", "")),
                "approval_pack_path": str(_approval_pack_report_path(workflow, pack_result)),
            }
        )
    return timeline


def _build_artifact_specs(pack_result: dict, pack_dir: Path, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    pack_run_id = str(pack_result.get("pack_run_id", "")).strip()
    for item in timeline:
        lane = item.get("lane", "")
        frame_id = item.get("frame_id", "")
        manifest_id = item.get("manifest_id", "")
        report_path = item.get("report_path", "")
        html_report_path = item.get("html_report_path", "")
        evidence_bundle_path = item.get("evidence_bundle_path", "")
        approval_pack_path = item.get("approval_pack_path", "")
        artifacts.extend(
            [
                _artifact_entry(f"{lane}.taskframe_report", lane, "taskframe_report", report_path, frame_id, manifest_id),
                _artifact_entry(f"{lane}.taskframe_html_report", lane, "taskframe_html_report", html_report_path, frame_id, manifest_id),
                _artifact_entry(f"{lane}.evidence_bundle", lane, "evidence_bundle", evidence_bundle_path, frame_id, manifest_id),
                _artifact_entry(f"{lane}.approval_pack", lane, "approval_pack", approval_pack_path, frame_id, manifest_id),
            ]
        )

    artifacts.extend(
        [
            _artifact_entry("summary_json", "story_pack", "summary_json", str(pack_dir / "summary.json"), "", pack_result.get("pack_id", "")),
            _artifact_entry("story_index_md", "story_pack", "story_index", str(pack_dir / "index.md"), "", pack_result.get("pack_id", "")),
            _artifact_entry("story_index_html", "story_pack", "story_index", str(pack_dir / "index.html"), "", pack_result.get("pack_id", "")),
            _artifact_entry("workflow_timeline", "story_pack", "workflow_timeline", str(pack_dir / "workflow_timeline.json"), "", pack_result.get("pack_id", "")),
        ]
    )
    return artifacts


def _finalize_evidence_manifest(artifacts: list[dict[str, Any]], pack_result: dict, generated_at: str) -> dict:
    errors: list[str] = []
    for item in artifacts:
        path = str(item.get("path", ""))
        item["exists"] = Path(path).is_file() if path else False
        if path and not item["exists"]:
            errors.append(f"Missing artifact: {path}")
    return {
        "pack_run_id": str(pack_result.get("pack_run_id", "")).strip(),
        "generated_at": generated_at,
        "artifacts": artifacts,
        "errors": errors,
    }


def _render_markdown(pack_result: dict, summary_json: dict, artifact_specs: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> str:
    lines = [
        "# Cross-Workflow Business Automation Demo v2",
        "",
        "## Executive Summary",
        "",
        f"- Pack ID: {summary_json.get('pack_id', '')}",
        f"- Pack Run ID: {summary_json.get('pack_run_id', '')}",
        f"- Story Title: {summary_json.get('story_title', '')}",
        f"- Duration (ms): {summary_json.get('duration_ms', 0)}",
        f"- Dry-Run Only: {str(summary_json.get('dry_run_only', True)).lower()}",
        f"- Live Side Effects Performed: {str(summary_json.get('live_side_effects_performed', False)).lower()}",
        f"- Workflow Count: {summary_json.get('workflow_count', 0)}",
        f"- Completed Count: {summary_json.get('completed_count', 0)}",
        f"- Failed Count: {summary_json.get('failed_count', 0)}",
        "",
        "## Business Scenario",
        "",
        "A customer issue moves across customer support, procurement, and accounting using the same manifest-driven runtime. The demo shows bounded LLM assistance, deterministic validation, approval-gated side effects, and dry-run execution only.",
        "",
        "## Workflow Timeline",
        "",
    ]
    for item in timeline:
        lines.append(
            f"- {item.get('sequence', 0)}. {item.get('lane', '')}: {item.get('scenario_id', '')} -> {item.get('state', '')}"
        )
    lines.extend(
        [
            "",
            "## Runtime Architecture Proof",
            "",
            "Each lane ran through TaskFrames, registered tools, validations, approval packs, and evidence bundle generation. No live side effects were performed.",
            "",
            "## Approval and Dry-Run Controls",
            "",
            "- Approval gates were preserved for every staged side effect.",
            "- Executed actions ran in dry-run mode only.",
            "- No live tool call was required for the story pack.",
            "",
            "## LLM Usage Summary",
            "",
            f"- LLM Calls: {summary_json.get('total_llm_calls', 0)}",
            "- The LLM was used only for bounded drafting assistance.",
            "- The LLM did not decide workflow outcomes.",
            "",
            "## Tool Usage Summary",
            "",
            f"- Tool Calls: {summary_json.get('total_tool_calls', 0)}",
            "- Tools performed deterministic data reads, validations, and approval-staged write preparation.",
            "",
            "## Evidence Index",
            "",
        ]
    )
    for artifact in artifact_specs:
        if not isinstance(artifact, dict):
            continue
        lines.append(f"- {artifact.get('artifact_id', '')}: {artifact.get('artifact_type', '')} -> {artifact.get('path', '')}")
    lines.extend(
        [
            "",
            "## Failure / Limitation Notes",
            "",
            "This is a controlled portfolio demo using seeded data, approval-gated side effects, and dry-run execution. It is not live production automation.",
            "",
            "## Conclusion",
            "",
            "The demo shows one connected business story executed through the same runtime with traceable TaskFrames, deterministic tools, bounded LLM assistance, staged approvals, and a consolidated evidence pack.",
        ]
    )
    return "\n".join(lines)


def _render_html(pack_result: dict, summary_json: dict, artifact_specs: list[dict[str, Any]], timeline: list[dict[str, Any]], markdown: str) -> str:
    rows = []
    for item in timeline:
        rows.append(
            "<tr>"
            f"<td>{_escape(str(item.get('sequence', 0)))}</td>"
            f"<td>{_escape(str(item.get('lane', '')))}</td>"
            f"<td>{_escape(str(item.get('scenario_id', '')))}</td>"
            f"<td>{_escape(str(item.get('state', '')))}</td>"
            f"<td>{_escape(str(item.get('pending_action_count', 0)))}</td>"
            f"<td>{_escape(str(item.get('executed_action_count', 0)))}</td>"
            f"<td>{_escape(str(item.get('report_path', '')))}</td>"
            f"<td>{_escape(str(item.get('evidence_bundle_path', '')))}</td>"
            "</tr>"
        )
    artifact_rows = []
    for item in artifact_specs:
        if not isinstance(item, dict):
            continue
        artifact_rows.append(
            "<tr>"
            f"<td>{_escape(str(item.get('artifact_id', '')))}</td>"
            f"<td>{_escape(str(item.get('artifact_type', '')))}</td>"
            f"<td>{_escape(str(item.get('path', '')))}</td>"
            f"<td>{_escape(str(item.get('exists', False)).lower())}</td>"
            "</tr>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_escape(str(summary_json.get('story_title', 'Cross-Workflow Business Automation Demo v2')))}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.5} "
        ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0}"
        ".card{border:1px solid #ddd;border-radius:8px;padding:12px;background:#fafafa}"
        "table{border-collapse:collapse;width:100%;margin:16px 0} th,td{border:1px solid #ccc;padding:8px;text-align:left}"
        "th{background:#f0f0f0}</style></head><body>"
        f"<h1>{_escape(str(summary_json.get('story_title', 'Cross-Workflow Business Automation Demo v2')))}</h1>"
        "<p><strong>Dry-run only:</strong> true<br><strong>Live side effects performed:</strong> false</p>"
        "<div class='cards'>"
        f"<div class='card'><strong>Pack ID</strong><br>{_escape(str(summary_json.get('pack_id', '')))}</div>"
        f"<div class='card'><strong>Pack Run ID</strong><br>{_escape(str(summary_json.get('pack_run_id', '')))}</div>"
        f"<div class='card'><strong>Workflows</strong><br>{_escape(str(summary_json.get('workflow_count', 0)))}</div>"
        f"<div class='card'><strong>Reports</strong><br>{_escape(str(summary_json.get('reports_generated', 0)))}</div>"
        "</div>"
        "<h2>Workflow Timeline</h2>"
        "<table><thead><tr><th>#</th><th>Lane</th><th>Scenario</th><th>State</th><th>Pending</th><th>Executed</th><th>Report</th><th>Evidence</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        "<h2>Evidence Links</h2><table><thead><tr><th>Artifact</th><th>Type</th><th>Path</th><th>Exists</th></tr></thead><tbody>"
        + "".join(artifact_rows)
        + "</tbody></table>"
        "<h2>Limitation Note</h2><p>This is a controlled portfolio demo using seeded data, approval-gated side effects, and dry-run execution only.</p>"
        "<h2>Rendered Markdown</h2><pre style='white-space:pre-wrap'>"
        + _escape(markdown)
        + "</pre></body></html>"
    )


def _render_screenshots_checklist() -> str:
    return "\n".join(
        [
            "# Screenshot Checklist",
            "",
            "- Operator console before running demo",
            "- Demo selection: Cross-Workflow Business Automation Demo v2",
            "- Workflow completed state",
            "- Approval / dry-run evidence",
            "- Generated story pack folder",
            "- Story pack index.html",
            "- Evidence manifest",
            "- Individual TaskFrame report",
        ]
    )


def _artifact_entry(artifact_id: str, workflow_lane: str, artifact_type: str, path: str, frame_id: str, manifest_id: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "workflow_lane": workflow_lane,
        "artifact_type": artifact_type,
        "path": path,
        "exists": Path(path).is_file() if path else False,
        "frame_id": frame_id,
        "manifest_id": manifest_id,
    }


def _approval_pack_report_path(workflow: dict, pack_result: dict) -> str:
    frame_id = str(workflow.get("frame_id", "")).strip()
    runtime_data_dir = str(pack_result.get("runtime_data_dir", "runtime_data"))
    if not frame_id:
        return ""
    return str(Path(runtime_data_dir) / "runs" / frame_id / "reports" / "approval_pack_report.md")


def _failure(*, pack_run_id: str, errors: list[str]) -> dict:
    return {
        "ok": False,
        "pack_run_id": pack_run_id,
        "story_pack_dir": "",
        "index_markdown_path": "",
        "index_html_path": "",
        "summary_json_path": "",
        "evidence_manifest_path": "",
        "linked_artifacts": [],
        "errors": errors,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
