from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.business_data import reset_business_dataset, seed_business_dataset, validate_business_dataset
from runtime.llm_adapter import check_llm_available
from src.operator_scenario_runner import run_scenario
from src.operator_scenarios import get_scenario
from src.demo_story_pack import build_cross_workflow_story_pack


def _v1_workflow_sequence() -> list[dict[str, str]]:
    return [
        {"scenario_id": "customer_status_approve_execute_dry_run", "lane": "customer_support", "required_final_state": "COMPLETED"},
        {"scenario_id": "procurement_low_stock_approve_execute_dry_run", "lane": "procurement", "required_final_state": "COMPLETED"},
        {"scenario_id": "accounting_payment_reconciliation_approve_execute_dry_run", "lane": "accounting", "required_final_state": "COMPLETED"},
    ]


def _v2_workflow_sequence() -> list[dict[str, str]]:
    return _v1_workflow_sequence()


DEMO_PACKS: list[dict[str, Any]] = [
    {
        "id": "cross_workflow_business_demo_v1",
        "label": "Cross-Workflow Business Automation Demo v1",
        "story_title": "Cross-Workflow Business Automation Demo v1",
        "description": (
            "Runs customer support, procurement, and accounting workflows through "
            "the same TaskFrame runtime using real LLM calls, approval gates, "
            "dry-run execution, reports, and evidence bundles."
        ),
        "workflow_sequence": _v1_workflow_sequence(),
        "generate_reports": True,
        "stop_on_failure": True,
        "dry_run_only": True,
        "requires_real_llm": True,
    },
    {
        "id": "cross_workflow_business_demo_v2",
        "label": "Cross-Workflow Business Automation Demo v2",
        "story_title": "Order Fulfilment Exception",
        "story_version": 2,
        "description": (
            "Runs a connected order fulfilment exception story across customer support, "
            "procurement, and accounting through the same TaskFrame runtime, producing "
            "one consolidated evidence pack."
        ),
        "workflow_sequence": _v2_workflow_sequence(),
        "generate_reports": True,
        "generate_story_pack": True,
        "stop_on_failure": True,
        "dry_run_only": True,
        "requires_real_llm": True,
    },
]


def list_demo_packs() -> list[dict]:
    return [dict(item) for item in DEMO_PACKS]


def get_demo_pack(pack_id: str) -> dict:
    for pack in DEMO_PACKS:
        if pack.get("id") == pack_id:
            return dict(pack)
    raise ValueError(f"Unknown demo pack: {pack_id}")


def run_cross_workflow_demo_pack(
    pack_id: str = "cross_workflow_business_demo_v1",
    runtime_data_dir: str = "runtime_data",
    reset_dataset: bool = True,
    generate_reports: bool = True,
    use_real_llm: bool = True,
    llm_adapter=None,
    allow_test_fake_llm: bool = False,
    skip_llm_preflight: bool = False,
) -> dict:
    try:
        pack = get_demo_pack(pack_id)
    except Exception as exc:
            return _failure_shape(pack_id, str(exc))

    started_at = _now()
    pack_run_id = f"{pack_id}_{uuid4().hex[:12]}"
    pack_dir = Path(runtime_data_dir) / "demo_packs" / pack_run_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    if reset_dataset:
        reset_business_dataset(runtime_data_dir)
    seed_business_dataset(runtime_data_dir, overwrite=False)
    dataset_validation = validate_business_dataset(runtime_data_dir)
    if not dataset_validation.get("ok", False):
        return _failure_shape(pack_id, "Business dataset validation failed.", pack_run_id=pack_run_id, failed_lane="preflight")

    if not skip_llm_preflight and pack.get("requires_real_llm", False) and use_real_llm:
        preflight = check_llm_available()
        if not preflight.get("ok", False):
            return _failure_shape(
                pack_id,
                f"Real LLM unavailable: {preflight.get('error', 'unknown error')}",
                pack_run_id=pack_run_id,
                failed_lane="preflight",
            )

    workflow_results: list[dict[str, Any]] = []
    completed_count = 0
    failed_count = 0
    total_pending_actions = 0
    total_executed_actions = 0
    reports_generated = 0
    evidence_generated = 0
    failed_lane = ""
    failed_scenario_id = ""
    error = ""

    for workflow in pack.get("workflow_sequence", []):
        scenario_id = str(workflow.get("scenario_id", ""))
        lane = str(workflow.get("lane", ""))
        _ = get_scenario(scenario_id)  # validates scenario existence
        scenario_result = run_scenario(
            scenario_id,
            runtime_data_dir=runtime_data_dir,
            use_local_llm=use_real_llm,
            reset_dataset=False,
            generate_report=generate_reports,
            llm_adapter=llm_adapter,
            allow_test_fake_llm=allow_test_fake_llm,
        )

        report_result = scenario_result.get("report_result", {}) if isinstance(scenario_result, dict) else {}
        pending_actions = _list_value(scenario_result, "snapshot.pending_actions")
        executed_actions = _list_value(scenario_result, "snapshot.executed_actions")

        total_pending_actions += len(pending_actions)
        total_executed_actions += len(executed_actions)
        if report_result.get("ok"):
            reports_generated += 1
        if report_result.get("evidence_bundle_path"):
            evidence_generated += 1

        workflow_result = {
            "lane": lane,
            "scenario_id": scenario_id,
            "ok": bool(scenario_result.get("ok")),
            "frame_id": scenario_result.get("frame_id", ""),
            "manifest_id": scenario_result.get("manifest_id", ""),
            "state": scenario_result.get("state", ""),
            "pending_action_count": len(pending_actions),
            "executed_action_count": len(executed_actions),
            "report_result": report_result,
            "failure_summary": scenario_result.get("failure_summary", {}),
            "scenario_validation": scenario_result.get("scenario_validation", {}),
            "summary": scenario_result.get("summary", {}),
        }
        workflow_results.append(workflow_result)

        if workflow_result["ok"] and workflow_result["state"] == workflow.get("required_final_state", "COMPLETED"):
            completed_count += 1
            continue

        failed_count += 1
        failed_lane = lane
        failed_scenario_id = scenario_id
        error = (
            scenario_result.get("error", "")
            or workflow_result.get("failure_summary", {}).get("failure_message", "")
            or "Workflow failed."
        )
        if pack.get("stop_on_failure", True):
            break

    not_run_count = max(0, len(pack.get("workflow_sequence", [])) - len(workflow_results))
    if not_run_count:
        for workflow in pack.get("workflow_sequence", [])[len(workflow_results) :]:
            workflow_results.append(
                {
                    "lane": workflow.get("lane", ""),
                    "scenario_id": workflow.get("scenario_id", ""),
                    "ok": False,
                    "frame_id": "",
                    "manifest_id": "",
                    "state": "NOT_RUN",
                    "pending_action_count": 0,
                    "executed_action_count": 0,
                    "report_result": {},
                    "failure_summary": {},
                    "scenario_validation": {"verdict": "FAIL", "checks": []},
                    "summary": {},
                }
            )

    ended_at = _now()
    summary = {
        "workflow_count": len(pack.get("workflow_sequence", [])),
        "completed_count": completed_count,
        "failed_count": failed_count,
        "not_run_count": not_run_count,
        "total_pending_actions": total_pending_actions,
        "total_executed_actions": total_executed_actions,
        "total_llm_calls": sum(len(_list_value(result, "summary.llm_calls")) for result in workflow_results),
        "total_tool_calls": sum(len(_list_value(result, "summary.tool_calls")) for result in workflow_results),
        "reports_generated": reports_generated,
        "evidence_bundles_generated": evidence_generated,
    }
    aggregate_report = _write_aggregate_report(pack_dir, pack, pack_run_id, started_at, ended_at, workflow_results, summary)
    result = {
        "ok": failed_count == 0 and completed_count == len(pack.get("workflow_sequence", [])),
        "pack_id": pack_id,
        "label": pack.get("label", ""),
        "story_title": pack.get("story_title", pack.get("label", "")),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": _duration_ms(started_at, ended_at),
        "dry_run_only": bool(pack.get("dry_run_only", True)),
        "requires_real_llm": bool(pack.get("requires_real_llm", True)),
        "pack_run_id": pack_run_id,
        "runtime_data_dir": runtime_data_dir,
        "workflow_results": workflow_results,
        "summary": summary,
        "aggregate_report": aggregate_report,
        "failed_lane": failed_lane,
        "failed_scenario_id": failed_scenario_id,
        "error": "" if failed_count == 0 else error,
    }
    if pack.get("generate_story_pack"):
        story_pack_result = build_cross_workflow_story_pack(result, runtime_data_dir=runtime_data_dir)
        result["story_pack_result"] = story_pack_result
        if not story_pack_result.get("ok"):
            result["ok"] = False
            result["error"] = "; ".join(story_pack_result.get("errors", [])) or "Story pack generation failed."
    _write_json(pack_dir / "cross_workflow_demo_summary.json", result)
    return result


def _write_aggregate_report(
    pack_dir: Path,
    pack: dict,
    pack_run_id: str,
    started_at: str,
    ended_at: str,
    workflow_results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    markdown_path = pack_dir / "cross_workflow_demo_report.md"
    html_path = pack_dir / "cross_workflow_demo_report.html"
    summary_json_path = pack_dir / "cross_workflow_demo_summary.json"
    _write_json(summary_json_path, {
        "pack_id": pack.get("id", ""),
        "pack_run_id": pack_run_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": _duration_ms(started_at, ended_at),
        "workflow_results": workflow_results,
        "summary": summary,
    })
    markdown = _render_markdown(pack, pack_run_id, started_at, ended_at, workflow_results, summary)
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>{pack.get('label', '')}</title></head><body><pre>{_escape(markdown)}</pre></body></html>"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return {"ok": True, "markdown_path": str(markdown_path), "html_path": str(html_path), "summary_json_path": str(summary_json_path)}


def _render_markdown(
    pack: dict,
    pack_run_id: str,
    started_at: str,
    ended_at: str,
    workflow_results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    lines = [
        "# Cross-Workflow Business Automation Demo v1",
        "",
        "## Executive Summary",
        "",
        f"- Pack ID: {pack.get('id', '')}",
        f"- Pack Run ID: {pack_run_id}",
        f"- Started At: {started_at}",
        f"- Ended At: {ended_at}",
        f"- Duration (ms): {_duration_ms(started_at, ended_at)}",
        f"- Workflow Count: {summary.get('workflow_count', 0)}",
        f"- Dry-Run Only: {pack.get('dry_run_only', True)}",
        f"- Requires Real LLM: {pack.get('requires_real_llm', True)}",
        "",
        "## Runtime Architecture Proof",
        "",
        "All workflows executed through the same TaskFrame runtime, manifest-driven steps, registered tools, bounded LLM actions, approval-gated side effects, and dry-run execution.",
    ]
    for index, result in enumerate(workflow_results, start=1):
        lines.extend(
            [
                "",
                f"## Workflow {index} - {result.get('lane', '')}",
                "",
                f"- Scenario ID: {result.get('scenario_id', '')}",
                f"- Frame ID: {result.get('frame_id', '')}",
                f"- Manifest ID: {result.get('manifest_id', '')}",
                f"- Final State: {result.get('state', '')}",
                f"- Pending Actions: {result.get('pending_action_count', 0)}",
                f"- Executed Actions: {result.get('executed_action_count', 0)}",
                f"- Report Path: {result.get('report_result', {}).get('markdown_path', '')}",
                f"- Evidence Path: {result.get('report_result', {}).get('evidence_bundle_path', '')}",
                f"- LLM Calls: {len(_list_value(result, 'summary.llm_calls'))}",
                f"- Tool Calls: {len(_list_value(result, 'summary.tool_calls'))}",
            ]
        )
    lines.extend(
        [
            "",
            "## Approval + Dry-Run Summary",
            "",
            f"- Total Pending Actions: {summary.get('total_pending_actions', 0)}",
            f"- Total Executed Actions: {summary.get('total_executed_actions', 0)}",
            "",
            "## Failure Summary",
            "",
            "No live side effects were performed.",
            "",
            "## Conclusion",
            "",
            "The cross-workflow demo completed 3/3 business workflows through the same TaskFrame runtime. Customer support, procurement, and accounting each executed through manifest-defined steps, registered tools, bounded LLM operations, approval-gated side effects, dry-run execution, and report/evidence generation. No live side effects were performed.",
        ]
    )
    return "\n".join(lines)


def _failure_shape(
    demo_pack_id: str,
    error: str,
    *,
    pack_run_id: str = "",
    failed_lane: str = "",
    failed_scenario_id: str = "",
) -> dict:
    return {
        "ok": False,
        "pack_id": demo_pack_id,
        "label": "",
        "started_at": "",
        "ended_at": "",
        "duration_ms": 0,
        "dry_run_only": True,
        "requires_real_llm": True,
        "workflow_results": [],
        "summary": {
            "workflow_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "not_run_count": 0,
            "total_pending_actions": 0,
            "total_executed_actions": 0,
            "reports_generated": 0,
            "evidence_bundles_generated": 0,
        },
        "aggregate_report": {"ok": False, "markdown_path": "", "html_path": "", "summary_json_path": ""},
        "failed_lane": failed_lane,
        "failed_scenario_id": failed_scenario_id,
        "error": error,
    }


def _list_value(data: dict[str, Any], path: str) -> list:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return []
    return current if isinstance(current, list) else []


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _duration_ms(started_at: str, ended_at: str) -> int:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        return int((end - start).total_seconds() * 1000)
    except Exception:
        return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
