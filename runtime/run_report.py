from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .artifact_cleanup import load_taskframe_safe
from .evidence_bundle import build_evidence_bundle
from .failure_summary import build_failure_summary
from .failure_summary import classify_workbench_failure
from .persistence import ensure_dir, load_taskframe_dict, read_json, write_json_atomic
from .taskframe import utc_now
from src.operator_approval_pack import build_approval_pack_view


REPORT_VERSION = "operator_run_report_v1"
DEMO_REPORT_VERSION = "demo_run_report_v1"


def generate_run_report(runtime_data_dir: str | Path, frame_id: str, rebuild: bool = False) -> dict[str, Any]:
    return generate_operator_run_report(runtime_data_dir, frame_id, rebuild=rebuild)


def generate_pending_action_report(runtime_data_dir: str | Path, frame_id: str, rebuild: bool = False) -> dict[str, Any]:
    return _generate_single_report(runtime_data_dir, frame_id, report_type="pending_action_report", rebuild=rebuild)


def generate_approval_pack_report(runtime_data_dir: str | Path, frame_id: str, rebuild: bool = False) -> dict[str, Any]:
    return _generate_single_report(runtime_data_dir, frame_id, report_type="approval_pack_report", rebuild=rebuild)


def generate_operator_run_report(runtime_data_dir: str | Path, frame_id: str, rebuild: bool = False) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    frame = load_taskframe_safe(frame_id, runtime_root)
    if frame is None:
        return {"ok": False, "frame_id": frame_id, "report_type": "operator_run_report", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "generated_at": "", "rebuild": rebuild, "error": f"TaskFrame artifact not found: {frame_id}"}

    reports_dir = ensure_dir(runtime_root / "runs" / frame_id / "reports")
    bundle = build_evidence_bundle(frame_id, str(runtime_root))
    approval_pack = build_approval_pack_view(bundle)
    failure_summary = build_failure_summary(bundle)
    markdown = render_run_report_markdown(bundle, approval_pack, failure_summary, runtime_root)
    html_doc = render_run_report_html(bundle, approval_pack, failure_summary, runtime_root)

    markdown_path = reports_dir / "run_report.md"
    html_path = reports_dir / "run_report.html"
    bundle_path = reports_dir / "evidence_bundle.json"
    write_json_atomic(bundle_path, bundle)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_doc, encoding="utf-8")

    failure_report_md = reports_dir / "failure_report.md"
    failure_report_html = reports_dir / "failure_report.html"
    if str(bundle.get("state", "")).startswith("FAILED"):
        failure_report_md.write_text(render_failure_report_markdown(failure_summary), encoding="utf-8")
        failure_report_html.write_text(render_failure_report_html(failure_summary), encoding="utf-8")

    approval_pack_md = reports_dir / "approval_pack_report.md"
    approval_pack_html = reports_dir / "approval_pack_report.html"
    approval_pack_md.write_text(render_approval_pack_report_markdown(approval_pack), encoding="utf-8")
    approval_pack_html.write_text(render_approval_pack_report_html(approval_pack), encoding="utf-8")

    return {
        "ok": True,
        "frame_id": frame_id,
        "report_type": "operator_run_report",
        "markdown_path": str(markdown_path),
        "html_path": str(html_path),
        "evidence_bundle_path": str(bundle_path),
        "generated_at": utc_now(),
        "rebuild": rebuild,
        "error": "",
    }


def render_json_block(value: object, max_chars: int = 2000) -> str:
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...<truncated>..."
    return text


def render_run_report_markdown(bundle: dict[str, Any], approval_pack: dict, failure_summary: dict, runtime_root: Path) -> str:
    frame = bundle
    lines = [
        "# TaskFrame Run Report",
        "",
        "## 1. Executive Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Frame ID | {frame.get('frame_id', '')} |",
        f"| Manifest | {frame.get('manifest_id', '')} |",
        f"| State | {frame.get('state', '')} |",
        f"| Outcome | {_outcome_text(frame)} |",
        f"| Pending Actions | {len(frame.get('pending_actions', []))} |",
        f"| Executed Actions | {len(frame.get('executed_actions', []))} |",
        f"| Errors | {len(frame.get('errors', []))} |",
        "",
        "## 2. Trigger / Event",
        "",
        f"- Event ID: {frame.get('trigger', {}).get('event_id', '')}",
        f"- Event Type: {frame.get('trigger', {}).get('event_type', '')}",
        f"- Source: {frame.get('trigger', {}).get('source', '')}",
        "",
        "```json",
        render_json_block(frame.get("trigger", {})),
        "```",
        "",
        "## 3. Route and Manifest",
        "",
        f"- Manifest ID: {frame.get('manifest_id', '')}",
        f"- Manifest Name: {frame.get('summary', {}).get('manifest_name', '') or frame.get('manifest_name', '')}",
        f"- Step Count: {len(frame.get('steps', []))}",
        f"- Validation Count: {len(frame.get('validations', []))}",
        "",
        "## 4. Runtime Final State",
        "",
        f"- Final State: {frame.get('state', '')}",
        f"- Current Step ID: {frame.get('current_step_id', '')}",
        f"- Errors Count: {len(frame.get('errors', []))}",
        "",
        "```json",
        render_json_block(frame.get("completion_gate_result", {})),
        "```",
        "",
        "## 5. Step Timeline",
        "",
        _markdown_steps(frame.get("steps", [])),
        "## 6. LLM Calls",
        "",
        _markdown_llm_calls(frame.get("llm_calls", [])),
        "## 7. Tool Calls",
        "",
        _markdown_tool_calls(frame.get("tool_calls", [])),
        "## 8. Outputs",
        "",
        _markdown_outputs(frame.get("outputs", {})),
        "## 9. Evidence",
        "",
        _markdown_evidence(frame.get("evidence", [])),
        "## 10. Validations",
        "",
        _markdown_validations(frame.get("validations", [])),
        "## 11. Approval / Side-Effect Status",
        "",
        _markdown_approval_pack(approval_pack),
        "## 12. Failure Summary",
        "",
        _markdown_failure_summary(failure_summary),
        "## 13. Artifact Index",
        "",
        _markdown_artifact_index(bundle),
        "## 14. Raw References",
        "",
        f"- Frame ID: {frame.get('frame_id', '')}",
        f"- Manifest ID: {frame.get('manifest_id', '')}",
        f"- Runtime Data Dir: {runtime_root}",
        f"- Generated At: {bundle.get('generated_at', '')}",
        f"- Report Version: {REPORT_VERSION}",
    ]
    return "\n".join(lines)


def render_run_report_html(bundle: dict[str, Any], approval_pack: dict, failure_summary: dict, runtime_root: Path) -> str:
    sections = [
        ("1. Executive Summary", _table([("Frame ID", bundle.get("frame_id", "")), ("Manifest", bundle.get("manifest_id", "")), ("State", bundle.get("state", "")), ("Outcome", _outcome_text(bundle)), ("Pending Actions", len(bundle.get("pending_actions", []))), ("Executed Actions", len(bundle.get("executed_actions", []))), ("Errors", len(bundle.get("errors", [])))])),
        ("2. Trigger / Event", _pre(render_json_block(bundle.get("trigger", {})))),
        ("3. Route and Manifest", _table([("Manifest ID", bundle.get("manifest_id", "")), ("Step Count", len(bundle.get("steps", []))), ("Validation Count", len(bundle.get("validations", [])))])),
        ("4. Runtime Final State", _pre(render_json_block(bundle.get("completion_gate_result", {})))),
        ("5. Step Timeline", _pre(render_run_report_markdown(bundle, approval_pack, failure_summary, runtime_root).split("## 6. LLM Calls")[0].split("## 5. Step Timeline")[1])),
        ("6. LLM Calls", _pre(_markdown_llm_calls(bundle.get("llm_calls", [])))),
        ("7. Tool Calls", _pre(_markdown_tool_calls(bundle.get("tool_calls", [])))),
        ("8. Outputs", _pre(_markdown_outputs(bundle.get("outputs", {})))),
        ("9. Evidence", _pre(_markdown_evidence(bundle.get("evidence", [])))),
        ("10. Validations", _pre(_markdown_validations(bundle.get("validations", [])))),
        ("11. Approval / Side-Effect Status", _pre(_markdown_approval_pack(approval_pack))),
        ("12. Failure Summary", _pre(_markdown_failure_summary(failure_summary))),
        ("13. Artifact Index", _pre(_markdown_artifact_index(bundle))),
        ("14. Raw References", _pre(f"Frame ID: {bundle.get('frame_id', '')}\nManifest ID: {bundle.get('manifest_id', '')}\nRuntime Data Dir: {runtime_root}\nGenerated At: {bundle.get('generated_at', '')}\nReport Version: {REPORT_VERSION}")),
    ]
    body = "\n".join(f'<section class="section"><h2>{html.escape(title)}</h2>{content}</section>' for title, content in sections)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>TaskFrame Run Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
.section {{ margin-bottom: 24px; }}
.status-ok {{ color: #047857; }}
.status-failed {{ color: #b91c1c; }}
.status-warning {{ color: #b45309; }}
.status-pending {{ color: #6b7280; }}
.json-block {{ white-space: pre-wrap; background: #f8fafc; padding: 12px; border: 1px solid #e5e7eb; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: left; vertical-align: top; }}
.failed-row {{ background: #fef2f2; }}
</style>
</head>
<body>
<h1>TaskFrame Run Report</h1>
{body}
</body>
</html>"""


def render_failure_report_markdown(failure_summary: dict) -> str:
    lines = [
        "# Failure Report",
        "",
        f"- State: {failure_summary.get('state', '')}",
        f"- Failed Step: {failure_summary.get('failed_step_id', '')}",
        f"- Failure Type: {failure_summary.get('failure_type', '')}",
        f"- Failure Category: {failure_summary.get('failure_category', '')}",
        f"- Failure Title: {failure_summary.get('failure_title', '')}",
        f"- Failure Message: {failure_summary.get('failure_message', '')}",
        f"- Failure Reason: {failure_summary.get('failure_reason', '')}",
        f"- Recommended Action: {failure_summary.get('recommended_action', '')}",
        f"- Safe Outcome: {failure_summary.get('safe_outcome', '')}",
        f"- Pending Actions: {failure_summary.get('pending_action_count', 0)}",
        f"- Executed Actions: {failure_summary.get('executed_action_count', 0)}",
        "",
        "## Failed Validations",
    ]
    for item in failure_summary.get("failed_validations", []) or []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('validation_id', '')}: {item.get('message', '')}")
    lines.extend(["", "## Runtime Errors"])
    for error in failure_summary.get("blocking_errors", []) or []:
        lines.append(f"- {error}")
    return "\n".join(lines)


def render_failure_report_html(failure_summary: dict) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Failure Report</title></head><body><pre>{html.escape(render_failure_report_markdown(failure_summary))}</pre></body></html>"


def render_approval_pack_report_markdown(approval_pack: dict) -> str:
    lines = [
        "# Approval Pack Report",
        "",
        f"Frame ID: {approval_pack.get('frame_id', '')}",
        f"Manifest ID: {approval_pack.get('manifest_id', '')}",
        f"State: {approval_pack.get('state', '')}",
        "",
        "## Pending Actions",
    ]
    packs = approval_pack.get("approval_packs", []) or []
    if not packs:
        lines.append("No pending approval actions for this TaskFrame.")
    for pack in packs:
        if isinstance(pack, dict):
            lines.extend([f"### Action {pack.get('action_id', '')}", f"Tool: {pack.get('tool', '')}", f"Status: {pack.get('status', '')}", f"Risk: {pack.get('risk_class', '')}", f"Human Summary: {pack.get('human_summary', '')}", f"Arguments: {pack.get('args', {})}", f"Guardrails: {pack.get('guardrails', [])}", ""])
    return "\n".join(lines)


def render_approval_pack_report_html(approval_pack: dict) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Approval Pack Report</title></head><body><pre>{html.escape(render_approval_pack_report_markdown(approval_pack))}</pre></body></html>"


def _generate_single_report(runtime_data_dir: str | Path, frame_id: str, report_type: str, rebuild: bool = False) -> dict[str, Any]:
    runtime_root = Path(runtime_data_dir)
    frame = load_taskframe_safe(frame_id, runtime_root)
    if frame is None:
        raise FileNotFoundError(f"TaskFrame artifact not found: {frame_id}")
    reports_dir = ensure_dir(runtime_root / "runs" / frame_id / "reports")
    path = reports_dir / f"{report_type}.md"
    html_path = reports_dir / f"{report_type}.html"
    content = f"# {report_type}\n\nFrame ID: {frame_id}\nState: {frame.get('state', '')}\n"
    path.write_text(content, encoding="utf-8")
    html_path.write_text(f"<!doctype html><html><body><pre>{html.escape(content)}</pre></body></html>", encoding="utf-8")
    return {"ok": True, "frame_id": frame_id, "report_type": report_type, "markdown_path": str(path), "html_path": str(html_path), "generated_at": utc_now(), "rebuild": rebuild}


def _table(rows: list[tuple[object, object]]) -> str:
    body = "\n".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)
    return f"<table>{body}</table>"


def _pre(text: str) -> str:
    return f'<pre class="json-block">{html.escape(text)}</pre>'


def _markdown_steps(steps: list[dict]) -> str:
    lines = ["| # | Step | Kind | Action | Status | Attempts | Result | Error |", "|---:|---|---|---|---|---:|---|---|"]
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        status = str(step.get("status", ""))
        marker = " <<< FAILURE" if status.startswith("FAILED") else ""
        lines.append(f"| {idx} | {step.get('step_id', step.get('id', ''))} | {step.get('kind', '')} | {step.get('action', step.get('command', ''))} | {status}{marker} | {step.get('attempts', 0)} | {step.get('output_alias', step.get('result_ref', ''))} | {step.get('error', '')} |")
    return "\n".join(lines) + "\n"


def _markdown_llm_calls(llm_calls: list[dict]) -> str:
    if not llm_calls:
        return "No LLM calls were recorded."
    lines = []
    for call in llm_calls:
        if not isinstance(call, dict):
            continue
        lines.extend([f"- step_id: {call.get('step_id', '')}", f"  action: {call.get('action', '')}", f"  provider: {call.get('provider', '')}", f"  model: {call.get('model', '')}", f"  ok: {call.get('ok', '')}", f"  output_ref: {call.get('output_ref', '')}", f"  micro_tool: {call.get('metadata', {}).get('micro_tool', False)}"])
    return "\n".join(lines)


def _markdown_tool_calls(tool_calls: list[dict]) -> str:
    if not tool_calls:
        return "No tool calls were recorded."
    lines = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        live = bool(call.get("live"))
        lines.extend([f"- step_id: {call.get('step_id', '')}", f"  tool: {call.get('tool', '')}", f"  namespace: {call.get('namespace', '')}", f"  action: {call.get('action', '')}", f"  live: {live}", f"  dry_run: {call.get('dry_run', True)}", f"  side_effect: {call.get('side_effect', False)}", f"  requires_approval: {call.get('requires_approval', False)}", f"  output_alias: {call.get('output_alias', '')}", f"  ok: {call.get('ok', '')}", f"  error: {call.get('error', '')}"])
    return "\n".join(lines)


def _markdown_outputs(outputs: dict) -> str:
    if not isinstance(outputs, dict) or not outputs:
        return "No outputs were recorded."
    lines = []
    for key, value in outputs.items():
        lines.extend([f"### Output: {key}", "```json", render_json_block(value), "```", ""])
    return "\n".join(lines)


def _markdown_evidence(evidence: list[dict]) -> str:
    if not evidence:
        return "No evidence records were attached to this TaskFrame."
    lines = [f"Evidence count: {len(evidence)}"]
    for item in evidence:
        if isinstance(item, dict):
            lines.extend([f"- step_id: {item.get('step_id', '')}", f"  source: {item.get('dataset', item.get('source', ''))}", f"  record_id: {item.get('record_id', '')}", f"  data: {json.dumps(item.get('data', item), ensure_ascii=False)}"])
    return "\n".join(lines)


def _markdown_validations(validations: list[dict]) -> str:
    if not validations:
        return "No validations were recorded."
    lines = ["| Validation ID | Type | OK | Message | Step | Data |", "|---|---|---|---|---|---|"]
    failed = 0
    passed = 0
    for item in validations:
        if not isinstance(item, dict):
            continue
        ok = bool(item.get("ok"))
        if ok:
            passed += 1
        else:
            failed += 1
        marker = "FAILED <<< BLOCKING" if not ok else "ok"
        lines.append(f"| {item.get('validation_id', item.get('id', ''))} | {item.get('type', item.get('validation_type', ''))} | {marker} | {item.get('message', '')} | {item.get('step_id', '')} | {json.dumps(item.get('data', {}), ensure_ascii=False)} |")
    lines.extend(["", f"Passed validations: {passed}", f"Failed validations: {failed}"])
    return "\n".join(lines)


def _markdown_approval_pack(approval_pack: dict) -> str:
    if not isinstance(approval_pack, dict) or not approval_pack.get("approval_packs"):
        return "No side-effect actions were staged or executed."
    lines = [f"Pending Action Count: {approval_pack.get('pending_action_count', 0)}", f"Executed Action Count: {len(approval_pack.get('executed_actions', []))}"]
    for pack in approval_pack.get("approval_packs", []):
        if not isinstance(pack, dict):
            continue
        lines.extend([f"### Pending Action: {pack.get('action_id', '')}", f"| Field | Value |", f"|---|---|", f"| Tool | {pack.get('tool', '')} |", f"| Status | {pack.get('status', '')} |", f"| Risk | {pack.get('risk_class', '')} |", f"| Requires Approval | {pack.get('requires_approval', '')} |", f"| Output Alias | {pack.get('output_alias', '')} |", f"Human Summary: {pack.get('human_summary', '')}", f"Arguments: {json.dumps(pack.get('args', {}), ensure_ascii=False)}", f"Guardrails: {json.dumps(pack.get('guardrails', []), ensure_ascii=False)}", ""])
    return "\n".join(lines)


def _markdown_failure_summary(failure_summary: dict) -> str:
    if not isinstance(failure_summary, dict) or not failure_summary.get("state", "").startswith("FAILED"):
        return "No failure for this run."
    lines = [
        f"- State: {failure_summary.get('state', '')}",
        f"- failed_step_id: {failure_summary.get('failed_step_id', '')}",
        f"- Failed Step: {failure_summary.get('failed_step_id', '')}",
        f"- failure_type: {failure_summary.get('failure_type', '')}",
        f"- Failure Type: {failure_summary.get('failure_type', '')}",
        f"- failure_category: {failure_summary.get('failure_category', '')}",
        f"- Failure Category: {failure_summary.get('failure_category', '')}",
        f"- failure_title: {failure_summary.get('failure_title', '')}",
        f"- Failure Title: {failure_summary.get('failure_title', '')}",
        f"- failure_message: {failure_summary.get('failure_message', '')}",
        f"- Failure Message: {failure_summary.get('failure_message', '')}",
        f"- failure_reason: {failure_summary.get('failure_reason', '')}",
        f"- Failure Reason: {failure_summary.get('failure_reason', '')}",
        f"- Operator Explanation: {failure_summary.get('operator_explanation', '')}",
        f"- Recommended Action: {failure_summary.get('recommended_action', '')}",
        f"- Safe Outcome: {failure_summary.get('safe_outcome', '')}",
        f"- Pending Actions: {failure_summary.get('pending_action_count', 0)}",
        f"- Executed Actions: {failure_summary.get('executed_action_count', 0)}",
        f"- Safe To Retry: {failure_summary.get('safe_to_retry', False)}",
        "",
        "### Failed Validations",
    ]
    failed_validations = failure_summary.get("failed_validations", [])
    if failed_validations:
        for item in failed_validations:
            if isinstance(item, dict):
                lines.append(f"- {item.get('validation_id', '')}: {item.get('message', '')}")
    else:
        lines.append("- None")
    lines.extend(["", "### Runtime Errors"])
    errors = failure_summary.get("blocking_errors", [])
    if errors:
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("- None")
    return "\n".join(lines)


def _markdown_artifact_index(bundle: dict[str, Any]) -> str:
    artifacts = bundle.get("artifact_paths", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    lines = ["| Artifact | Path |", "|---|---|"]
    labels = {
        "taskframe_json": "TaskFrame JSON",
        "summary_json": "Summary JSON",
        "outputs_json": "Outputs JSON",
        "audit_json": "Audit JSON",
        "run_report_md": "Run Report Markdown",
        "run_report_html": "Run Report HTML",
        "approval_pack_report_md": "Approval Pack Report Markdown",
        "approval_pack_report_html": "Approval Pack Report HTML",
        "failure_report_md": "Failure Report Markdown",
        "failure_report_html": "Failure Report HTML",
        "evidence_bundle_json": "Evidence Bundle JSON",
    }
    for key, label in labels.items():
        if key in artifacts:
            lines.append(f"| {label} | {artifacts[key]} |")
    return "\n".join(lines)


def _outcome_text(bundle: dict[str, Any]) -> str:
    state = str(bundle.get("state", ""))
    pending = len(bundle.get("pending_actions", []))
    if state == "WAITING_FOR_EXECUTE" and pending > 0:
        return "Run completed to approval gate. Side effect is staged but not executed."
    if state == "COMPLETED":
        return "Run completed successfully."
    if state == "COMPLETED_NO_DATA":
        return "Run completed successfully with no data returned."
    if state.startswith("FAILED"):
        return "Run failed safely. No side effect should be executed unless explicitly recorded."
    if state in {"CANCELLED", "EXPIRED"}:
        return "Run did not complete."
    return "Run completed."


def get_demo_run_report_paths(runtime_data_dir: str | Path, frame_id: str) -> dict[str, str]:
    runtime_root = Path(runtime_data_dir)
    reports_dir = ensure_dir(runtime_root / "outputs" / "reports")
    evidence_dir = ensure_dir(runtime_root / "outputs" / "evidence")
    base_name = f"{frame_id}_run_report"
    return {
        "markdown_path": str(reports_dir / f"{base_name}.md"),
        "html_path": str(reports_dir / f"{base_name}.html"),
        "evidence_bundle_path": str(evidence_dir / f"{frame_id}_evidence_bundle.json"),
        "reports_dir": str(reports_dir),
        "evidence_dir": str(evidence_dir),
    }


def get_demo_business_report_paths(runtime_data_dir: str | Path, frame_id: str, scenario_id: str) -> dict[str, str]:
    runtime_root = Path(runtime_data_dir)
    reports_dir = ensure_dir(runtime_root / "outputs" / "reports")
    evidence_dir = ensure_dir(runtime_root / "outputs" / "evidence")
    safe_scenario_id = _slugify(scenario_id) or "business_report"
    base_name = f"{safe_scenario_id}_{frame_id}"
    return {
        "markdown_path": str(reports_dir / f"{base_name}.md"),
        "html_path": str(reports_dir / f"{base_name}.html"),
        "evidence_bundle_path": str(evidence_dir / f"{frame_id}_evidence_bundle.json"),
        "reports_dir": str(reports_dir),
        "evidence_dir": str(evidence_dir),
    }


def generate_demo_run_report(runtime_data_dir: str | Path, frame_id: str, scenario: dict | None = None) -> dict[str, Any]:
    frame_id = str(frame_id or "").strip()
    if not frame_id:
        return {"ok": False, "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": "frame_id is required"}

    runtime_root = Path(runtime_data_dir)
    taskframe_path = runtime_root / "runs" / frame_id / "taskframe.json"
    if not taskframe_path.is_file():
        return {"ok": False, "frame_id": frame_id, "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": f"TaskFrame artifact not found: {frame_id}"}

    frame = load_taskframe_dict(frame_id, runtime_root)
    outputs = _read_json_dict(runtime_root / "runs" / frame_id / "outputs.json", frame.get("outputs", {}))
    audit = _read_json_list(runtime_root / "runs" / frame_id / "audit.json", frame.get("audit", []))
    scenario_data = scenario if isinstance(scenario, dict) else {}
    story_type = _detect_demo_story_type(scenario_data, frame, outputs)
    report_model = _build_demo_run_report_model(runtime_root, frame, outputs, audit, scenario_data, story_type)
    paths = get_demo_run_report_paths(runtime_root, frame_id)
    scenario_id = _string(scenario_data.get("id"))
    business_markdown_path = Path("")
    business_html_path = Path("")
    business_evidence_path = Path("")
    if story_type == "report_generation" and not str(frame.get("state", "")).startswith("FAILED"):
        business_paths = get_demo_business_report_paths(runtime_root, frame_id, scenario_id or "report_generation")
        report_model["business_report_markdown_path"] = business_paths["markdown_path"]
        report_model["business_report_html_path"] = business_paths["html_path"]
        report_model["business_report_evidence_bundle_path"] = business_paths["evidence_bundle_path"]
        report_model["run_report_markdown_path"] = paths["markdown_path"]
        report_model["run_report_html_path"] = paths["html_path"]
        report_model["run_report_evidence_bundle_path"] = paths["evidence_bundle_path"]
        report_model["output_title"] = "Business report generated"
        report_model["output_text"] = (
            "No business report artifact was found for this run."
            if str(frame.get("state", "")).startswith("FAILED")
            else "\n".join(
                [
                    "Business report generated",
                    f"File: {business_paths['html_path']}",
                    "",
                    "Also created:",
                    "- Markdown report",
                    "- Evidence bundle",
                    "",
                    "Run report generated",
                    f"File: {paths['html_path']}",
                    "This report shows:",
                    "- manifest steps",
                    "- step results",
                    "- validations",
                    "- evidence",
                    "- pending actions",
                ]
            )
        )
        report_model["output_bullets"] = (
            ["No business report artifact was found for this run."]
            if str(frame.get("state", "")).startswith("FAILED")
            else [
                "Business report generated",
                "Markdown report created",
                "Evidence bundle created",
                "Run report generated",
                f"Report HTML: {Path(business_paths['html_path']).name}",
            ]
        )
        report_model["approval_text"] = "No approval action was created because the workflow stopped safely." if str(frame.get("state", "")).startswith("FAILED") else "No pending approval action for this run."
        business_markdown = render_demo_business_report_markdown(report_model, business_paths)
        business_html = render_demo_business_report_html(report_model, business_paths)
        business_markdown_path = Path(business_paths["markdown_path"])
        business_html_path = Path(business_paths["html_path"])
        business_evidence_path = Path(business_paths["evidence_bundle_path"])
        ensure_dir(business_markdown_path.parent)
        business_markdown_path.write_text(business_markdown, encoding="utf-8")
        business_html_path.write_text(business_html, encoding="utf-8")
    else:
        report_model["run_report_markdown_path"] = paths["markdown_path"]
        report_model["run_report_html_path"] = paths["html_path"]
        report_model["run_report_evidence_bundle_path"] = paths["evidence_bundle_path"]
        report_model["business_report_markdown_path"] = ""
        report_model["business_report_html_path"] = ""
        report_model["business_report_evidence_bundle_path"] = ""

    if story_type == "report_generation" and str(frame.get("state", "")).startswith("FAILED"):
        report_model["output_title"] = "Run report"
        report_model["output_text"] = "No business report artifact was found for this run."
        report_model["output_bullets"] = ["No business report artifact was found for this run."]
        report_model["approval_text"] = "No approval action was created because the workflow stopped safely."

    markdown = render_demo_run_report_markdown(report_model)
    html_doc = render_demo_run_report_html(report_model)
    evidence_bundle = _build_demo_evidence_bundle(runtime_root, report_model, frame, outputs, audit, paths)
    markdown_path = Path(paths["markdown_path"])
    html_path = Path(paths["html_path"])
    evidence_path = Path(paths["evidence_bundle_path"])
    ensure_dir(markdown_path.parent)
    ensure_dir(evidence_path.parent)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_doc, encoding="utf-8")
    write_json_atomic(evidence_path, evidence_bundle)

    return {
        "ok": True,
        "frame_id": frame_id,
        "report_type": "demo_run_report",
        "scenario_id": _string(scenario_data.get("id")),
        "scenario_label": _string(scenario_data.get("label")),
        "story_type": story_type,
        "markdown_path": str(markdown_path),
        "html_path": str(html_path),
        "evidence_bundle_path": str(evidence_path),
        "run_report_markdown_path": str(markdown_path),
        "run_report_html_path": str(html_path),
        "run_report_evidence_bundle_path": str(evidence_path),
        "business_report_markdown_path": str(business_markdown_path),
        "business_report_html_path": str(business_html_path),
        "business_report_evidence_bundle_path": str(business_evidence_path),
        "generated_at": report_model.get("generated_at", utc_now()),
        "report_model": report_model,
        "error": "",
    }


def build_step_report_items(frame: dict) -> list[dict]:
    frame = frame if isinstance(frame, dict) else {}
    outputs = frame.get("outputs", {}) if isinstance(frame.get("outputs", {}), dict) else {}
    story_type = _detect_demo_story_type({}, frame, outputs)
    return _build_step_report_items(frame, outputs, story_type)


def render_demo_run_report_markdown(report_model: dict) -> str:
    report_model = report_model if isinstance(report_model, dict) else {}
    lines = [
        "# Autonomous Business Worker Demo Report",
        "",
        "## Report Header",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Scenario | {report_model.get('scenario_label', '')} |",
        f"| Manifest | {report_model.get('manifest_id', '')} |",
        f"| Frame ID | {report_model.get('frame_id', '')} |",
        f"| Run status | {report_model.get('state', '')} |",
        f"| Generated at | {report_model.get('generated_at', '')} |",
        f"| Demo mode | {report_model.get('demo_mode', 'Dry run')} |",
        f"| Badge | {report_model.get('status_badge', '')} |",
        "",
        "## Plain-English Summary",
        "",
        report_model.get("plain_summary", "No summary available."),
        "",
        "## Manifest Step Timeline",
        "",
    ]
    for item in report_model.get("step_items", []):
        if not isinstance(item, dict):
            continue
        outcome = item.get("step_outcome", {}) if isinstance(item.get("step_outcome", {}), dict) else {}
        outcome_details = outcome.get("details", []) if isinstance(outcome.get("details", []), list) else []
        lines.extend(
            [
                f"### Step {item.get('index', '')}: {item.get('title', '')}",
                f"- Step ID: {item.get('step_id', '')}",
                f"- Status: {item.get('status_label', item.get('status', ''))}",
                f"- Command: {item.get('command', '')}",
                f"- Output alias: {item.get('output_alias', '')}",
                f"- Step outcome: {outcome.get('title', '')}",
                f"  {outcome.get('summary', '')}",
            ]
        )
        for detail in outcome_details:
            lines.append(f"  - {detail}")
        lines.extend(
            [
                f"- Result: {item.get('result_text', '')}",
                f"- Input values used: {item.get('inputs_text', '')}",
                f"- Tool call result: {item.get('tool_text', '') or 'Not recorded'}",
                f"- LLM call result: {item.get('llm_text', '') or 'Not recorded'}",
                f"- Validation: {item.get('validation_text', 'Not recorded')}",
                f"- Evidence: {item.get('evidence_text', 'Not recorded')}",
                f"- Errors: {item.get('error_text', '') or 'None'}",
                f"- Reason: {item.get('reason', '') or 'None'}",
                f"- Safe outcome: {item.get('safe_outcome', '') or 'None'}",
                "",
            ]
        )
    lines.extend([
        "## Outputs",
        "",
        f"### {report_model.get('output_title', 'Final Output')}",
        "",
        report_model.get("output_text", "No output available."),
    ])
    for bullet in report_model.get("output_bullets", []):
        lines.append(f"- {bullet}")
    lines.extend(
        [
            "",
            "```json",
            render_json_block(report_model.get("output_raw", {})),
            "```",
            "",
            "## Approval / Pending Actions",
            "",
            report_model.get("approval_text", "No pending approval action for this run."),
        ]
    )
    for item in report_model.get("pending_actions", []):
        if isinstance(item, dict):
            lines.extend(
                [
                    "",
                    f"- Action: {item.get('action', '')}",
                    f"  Status: {item.get('status', '')}",
                    f"  Risk: {item.get('risk', '')}",
                    f"  Dry-run mode: {item.get('dry_run', 'Yes')}",
                    f"  Prepared message: {item.get('body', '')}",
                ]
            )
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            report_model.get("evidence_text", "No evidence details available."),
        ]
    )
    for item in report_model.get("evidence_items", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            f"- Evidence bundle JSON: {report_model.get('evidence_bundle_path', '')}",
            "",
            "## Technical Appendix",
            "",
            "<details>",
            "<summary>View technical appendix</summary>",
            "",
            "### Full TaskFrame Summary",
            "```json",
            render_json_block(report_model.get("taskframe_summary", {})),
            "```",
            "",
            "### Raw TaskFrame",
            "```json",
            render_json_block(report_model.get("raw_frame", {})),
            "```",
            "",
            "### Raw Outputs",
            "```json",
            render_json_block(report_model.get("raw_outputs", {})),
            "```",
            "",
            "### Raw Audit Events",
            "```json",
            render_json_block(report_model.get("raw_audit", [])),
            "```",
            "",
            "</details>",
        ]
    )
    return "\n".join(lines)


def render_demo_run_report_html(report_model: dict) -> str:
    report_model = report_model if isinstance(report_model, dict) else {}
    step_cards = []
    for item in report_model.get("step_items", []):
        if not isinstance(item, dict):
            continue
        outcome = item.get("step_outcome", {}) if isinstance(item.get("step_outcome", {}), dict) else {}
        outcome_details = outcome.get("details", []) if isinstance(outcome.get("details", []), list) else []
        outcome_details_html = "".join(f"<li>{html.escape(str(detail))}</li>" for detail in outcome_details)
        step_cards.append(
            f"""
            <article class="step-card status-{html.escape(str(item.get('status_class', 'pending')))}">
              <div class="step-head">
                <div>
                  <div class="step-title">Step {html.escape(str(item.get('index', '')))}: {html.escape(str(item.get('title', '')))}</div>
                  <div class="step-meta">Step ID: {html.escape(str(item.get('step_id', '')))} | Command: {html.escape(str(item.get('command', '')))}</div>
                </div>
                <span class="badge badge-{html.escape(str(item.get('badge_class', 'muted')))}">{html.escape(str(item.get('status_label', item.get('status', ''))))}</span>
              </div>
              <div class="step-outcome">
                <div class="section-label">Step outcome</div>
                <div class="outcome-title">{html.escape(str(outcome.get('title', '')))}</div>
                <div class="outcome-summary">{html.escape(str(outcome.get('summary', '')))}</div>
                <ul class="outcome-details">{outcome_details_html}</ul>
              </div>
              <div class="step-grid">
                <div><strong>Output alias</strong><div class="mono">{html.escape(str(item.get('output_alias', '')))}</div></div>
                <div><strong>Result</strong><div>{html.escape(str(item.get('result_text', '')))}</div></div>
                <div><strong>Input values used</strong><div><pre>{html.escape(str(item.get('inputs_text', '')))}</pre></div></div>
                <div><strong>Tool call result</strong><div>{html.escape(str(item.get('tool_text', 'Not recorded') or 'Not recorded'))}</div></div>
                <div><strong>LLM call result</strong><div>{html.escape(str(item.get('llm_text', 'Not recorded') or 'Not recorded'))}</div></div>
                <div><strong>Validation</strong><div>{html.escape(str(item.get('validation_text', 'Not recorded')))}</div></div>
                <div><strong>Evidence</strong><div>{html.escape(str(item.get('evidence_text', 'Not recorded')))}</div></div>
                <div><strong>Errors</strong><div>{html.escape(str(item.get('error_text', 'None') or 'None'))}</div></div>
                <div><strong>Reason</strong><div>{html.escape(str(item.get('reason', 'None') or 'None'))}</div></div>
                <div><strong>Safe outcome</strong><div>{html.escape(str(item.get('safe_outcome', 'None') or 'None'))}</div></div>
              </div>
              <details>
                <summary>View raw step result</summary>
                <div class="subcard">
                  <div><strong>Step ID:</strong> {html.escape(str(item.get('step_id', '')))}</div>
                  <div><strong>Runtime status:</strong> {html.escape(str(item.get('status', '')))}</div>
                  <div><strong>Command:</strong> {html.escape(str(item.get('command', '')))}</div>
                  <div><strong>Input values used:</strong> <pre>{html.escape(str(item.get('inputs_text', '')))}</pre></div>
                  <div><strong>Output alias:</strong> {html.escape(str(item.get('output_alias', '')))}</div>
                  <div><strong>Output value:</strong> <pre>{html.escape(render_json_block(item.get('output', {})))}</pre></div>
                  <div><strong>Tool calls:</strong> <pre>{html.escape(render_json_block(item.get('tool_calls', [])))}</pre></div>
                  <div><strong>LLM calls:</strong> <pre>{html.escape(render_json_block(item.get('llm_calls', [])))}</pre></div>
                  <div><strong>Validations:</strong> <pre>{html.escape(render_json_block(item.get('validations', [])))}</pre></div>
                  <div><strong>Errors:</strong> <pre>{html.escape(render_json_block(item.get('error_text', '')))}</pre></div>
                  <div><strong>Evidence references:</strong> <pre>{html.escape(render_json_block(item.get('evidence', [])))}</pre></div>
                  <div><strong>Raw step result:</strong> <pre>{html.escape(render_json_block(item.get('raw_step', {})))}</pre></div>
                </div>
              </details>
            </article>
            """
        )

    output_raw = html.escape(render_json_block(report_model.get("output_raw", {})))
    taskframe_summary = html.escape(render_json_block(report_model.get("taskframe_summary", {})))
    raw_frame = html.escape(render_json_block(report_model.get("raw_frame", {})))
    raw_outputs = html.escape(render_json_block(report_model.get("raw_outputs", {})))
    raw_audit = html.escape(render_json_block(report_model.get("raw_audit", [])))
    pending_actions = report_model.get("pending_actions", [])
    evidence_items = report_model.get("evidence_items", [])

    pending_html = ""
    if pending_actions:
        pending_rows = []
        for item in pending_actions:
            if isinstance(item, dict):
                pending_rows.append(
                    f"""
                    <div class="subcard">
                      <div><strong>Action:</strong> {html.escape(str(item.get('action', '')))}</div>
                      <div><strong>Status:</strong> {html.escape(str(item.get('status', '')))}</div>
                      <div><strong>Risk:</strong> {html.escape(str(item.get('risk', '')))}</div>
                      <div><strong>Dry-run mode:</strong> {html.escape(str(item.get('dry_run', 'Yes')))}</div>
                      <div><strong>Prepared message:</strong> {html.escape(str(item.get('body', '')))}</div>
                    </div>
                    """
                )
        pending_html = "".join(pending_rows)
    else:
        pending_html = f"<div class=\"muted\">{html.escape(str(report_model.get('approval_text', 'No pending approval action for this run.')))}</div>"

    evidence_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in evidence_items) or "<li>No evidence details available.</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autonomous Business Worker Demo Report</title>
<style>
  :root {{
    --bg: #eef1f5;
    --card: #ffffff;
    --text: #111827;
    --muted: #5b6472;
    --border: #d8dee6;
    --success: #0f766e;
    --success-bg: #d1fae5;
    --warning: #a16207;
    --warning-bg: #fef3c7;
    --danger: #b91c1c;
    --danger-bg: #fee2e2;
    --pending: #334155;
    --pending-bg: #e2e8f0;
  }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Arial, Helvetica, sans-serif; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
  h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: -0.02em; }}
  h2 {{ margin: 0 0 14px; font-size: 22px; }}
  h3 {{ margin: 0 0 10px; font-size: 18px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 18px 18px 16px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05); margin-bottom: 16px; }}
  .grid {{ display: grid; gap: 16px; }}
  .header-grid {{ grid-template-columns: 1.5fr .9fr; align-items: start; }}
  .meta {{ color: var(--muted); font-size: 14px; line-height: 1.5; }}
  .badge {{ display: inline-block; border-radius: 999px; padding: 8px 12px; font-weight: 700; font-size: 13px; }}
  .badge-success {{ color: var(--success); background: var(--success-bg); }}
  .badge-warning {{ color: var(--warning); background: var(--warning-bg); }}
  .badge-danger {{ color: var(--danger); background: var(--danger-bg); }}
  .badge-pending {{ color: var(--pending); background: var(--pending-bg); }}
  .summary {{ font-size: 17px; line-height: 1.65; }}
  .step-card {{ border-left: 6px solid var(--border); padding-left: 16px; }}
  .status-completed {{ border-left-color: var(--success); }}
  .status-failed {{ border-left-color: var(--danger); }}
  .status-pending {{ border-left-color: var(--warning); }}
  .status-notreached {{ border-left-color: #94a3b8; }}
  .step-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
  .step-title {{ font-size: 18px; font-weight: 700; }}
  .step-meta {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
  .step-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; font-size: 14px; }}
  .step-grid strong {{ display: block; margin-bottom: 4px; }}
  .step-outcome {{ background: #f8fafc; border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; }}
  .outcome-title {{ font-size: 16px; font-weight: 700; margin-bottom: 4px; }}
  .outcome-summary {{ font-size: 14px; line-height: 1.55; margin-bottom: 8px; }}
  .outcome-details {{ margin: 0 0 0 20px; }}
  .mono, pre {{ font-family: Consolas, 'Courier New', monospace; }}
  pre {{ background: #f8fafc; border: 1px solid var(--border); border-radius: 12px; padding: 14px; overflow: auto; white-space: pre-wrap; word-break: break-word; }}
  details {{ margin-top: 12px; }}
  details > summary {{ cursor: pointer; font-weight: 700; }}
  .subcard {{ border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-top: 10px; background: #fafbfc; }}
  .muted {{ color: var(--muted); }}
  ul {{ margin: 8px 0 0 20px; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .section-label {{ text-transform: uppercase; letter-spacing: .06em; font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
  @media (max-width: 900px) {{
    .header-grid, .two-col, .step-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="grid header-grid">
      <div>
        <h1>Autonomous Business Worker Demo Report</h1>
        <div class="meta">
          <div><strong>Scenario:</strong> {html.escape(str(report_model.get('scenario_label', '')))}</div>
          <div><strong>Manifest:</strong> {html.escape(str(report_model.get('manifest_id', '')))}</div>
          <div><strong>Frame ID:</strong> {html.escape(str(report_model.get('frame_id', '')))}</div>
          <div><strong>Generated at:</strong> {html.escape(str(report_model.get('generated_at', '')))}</div>
          <div><strong>Demo mode:</strong> {html.escape(str(report_model.get('demo_mode', 'Dry run')))}</div>
          <div><strong>Evidence bundle:</strong> <span class="mono">{html.escape(str(report_model.get('evidence_bundle_path', '')))}</span></div>
        </div>
      </div>
      <div>
        <div class="section-label">Run status</div>
        <div class="badge badge-{html.escape(str(report_model.get('badge_class', 'pending')))}">{html.escape(str(report_model.get('status_badge', 'Awaiting approval')))}</div>
        <div class="meta" style="margin-top: 12px;">{html.escape(str(report_model.get('state', '')))}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="section-label">Plain-English Summary</div>
    <div class="summary">{html.escape(str(report_model.get('plain_summary', 'No summary available.')))}</div>
  </div>

  <div class="card">
    <h2>Manifest Step Timeline</h2>
    {''.join(step_cards)}
  </div>

  <div class="card">
    <h2>Outputs</h2>
    <div class="two-col">
      <div>
        <h3>{html.escape(str(report_model.get('output_title', 'Final Output')))}</h3>
        <div class="summary">{html.escape(str(report_model.get('output_text', 'No output available.')))}</div>
        <ul>{''.join(f'<li>{html.escape(str(item))}</li>' for item in report_model.get('output_bullets', []))}</ul>
      </div>
      <div>
        <h3>Raw output dictionary</h3>
        <pre>{output_raw}</pre>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Approval / Pending Actions</h2>
    {pending_html}
  </div>

  <div class="card">
    <h2>Evidence</h2>
    <div class="summary">{html.escape(str(report_model.get('evidence_text', 'No evidence details available.')))}</div>
    <ul>{evidence_html}</ul>
  </div>

  <div class="card">
    <details>
      <summary>Technical appendix</summary>
      <div class="two-col" style="margin-top: 14px;">
        <div>
          <h3>TaskFrame summary</h3>
          <pre>{taskframe_summary}</pre>
        </div>
        <div>
          <h3>Raw TaskFrame</h3>
          <pre>{raw_frame}</pre>
        </div>
        <div>
          <h3>Raw outputs</h3>
          <pre>{raw_outputs}</pre>
        </div>
        <div>
          <h3>Raw audit events</h3>
          <pre>{raw_audit}</pre>
        </div>
      </div>
    </details>
  </div>
</div>
</body>
</html>"""


def render_demo_business_report_markdown(report_model: dict, paths: dict[str, str]) -> str:
    report_model = report_model if isinstance(report_model, dict) else {}
    lines = [
        "# Business Report",
        "",
        "## Report Header",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Scenario | {report_model.get('scenario_label', '')} |",
        f"| Manifest | {report_model.get('manifest_id', '')} |",
        f"| Frame ID | {report_model.get('frame_id', '')} |",
        f"| Generated at | {report_model.get('generated_at', '')} |",
        f"| Business report HTML | {paths.get('html_path', '')} |",
        f"| Markdown report | {paths.get('markdown_path', '')} |",
        f"| Evidence bundle | {paths.get('evidence_bundle_path', '')} |",
        "",
        "## Plain-English Summary",
        "",
        _business_report_summary(report_model),
        "",
        "## Business Report Artifact",
        "",
        f"Business report generated",
        "",
        f"File: {paths.get('html_path', '')}",
        "",
        "Also created:",
        "- Markdown report",
        "- Evidence bundle",
        "",
        "## Report Details",
        "",
        f"- Final state: {report_model.get('state', '')}",
        f"- Status badge: {report_model.get('status_badge', '')}",
        f"- Output: {report_model.get('output_text', '')}",
        "",
        "## Technical Appendix",
        "",
        "<details>",
        "<summary>View business report source data</summary>",
        "",
        "### TaskFrame Summary",
        "```json",
        render_json_block(report_model.get("taskframe_summary", {})),
        "```",
        "",
        "### Outputs",
        "```json",
        render_json_block(report_model.get("raw_outputs", {})),
        "```",
        "",
        "</details>",
    ]
    return "\n".join(lines)


def render_demo_business_report_html(report_model: dict, paths: dict[str, str]) -> str:
    report_model = report_model if isinstance(report_model, dict) else {}
    summary = html.escape(_business_report_summary(report_model))
    artifact_name = html.escape(Path(paths.get("html_path", "")).name)
    markdown_name = html.escape(Path(paths.get("markdown_path", "")).name)
    evidence_name = html.escape(Path(paths.get("evidence_bundle_path", "")).name)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Business Report</title>
<style>
  body {{ margin: 0; background: #eef1f5; color: #111827; font-family: Arial, Helvetica, sans-serif; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 28px; }}
  .card {{ background: #fff; border: 1px solid #d8dee6; border-radius: 16px; padding: 20px; margin-bottom: 16px; box-shadow: 0 8px 24px rgba(15,23,42,.05); }}
  h1 {{ margin: 0 0 8px; font-size: 34px; }}
  h2 {{ margin: 0 0 12px; font-size: 22px; }}
  .meta {{ color: #5b6472; line-height: 1.6; }}
  .badge {{ display: inline-block; border-radius: 999px; padding: 8px 12px; background: #d1fae5; color: #0f766e; font-weight: 700; }}
  .mono, pre {{ font-family: Consolas, 'Courier New', monospace; }}
  pre {{ background: #f8fafc; border: 1px solid #d8dee6; border-radius: 12px; padding: 14px; overflow: auto; white-space: pre-wrap; }}
  details > summary {{ cursor: pointer; font-weight: 700; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Business Report generated</h1>
    <div class="badge">Business report generated</div>
    <div class="meta" style="margin-top: 14px;">
      <div><strong>Scenario:</strong> {html.escape(str(report_model.get('scenario_label', '')))}</div>
      <div><strong>Manifest:</strong> {html.escape(str(report_model.get('manifest_id', '')))}</div>
      <div><strong>Frame ID:</strong> {html.escape(str(report_model.get('frame_id', '')))}</div>
      <div><strong>Generated at:</strong> {html.escape(str(report_model.get('generated_at', '')))}</div>
      <div><strong>File:</strong> <span class="mono">{artifact_name}</span></div>
      <div><strong>Markdown report:</strong> <span class="mono">{markdown_name}</span></div>
      <div><strong>Evidence bundle:</strong> <span class="mono">{evidence_name}</span></div>
    </div>
  </div>
  <div class="card">
    <h2>Plain-English Summary</h2>
    <div class="meta">{html.escape(summary)}</div>
  </div>
  <div class="card">
    <h2>Artifact Details</h2>
    <div class="meta">
      <div><strong>Business report generated</strong></div>
      <div>File: <span class="mono">{html.escape(str(paths.get('html_path', '')))}</span></div>
      <div style="margin-top: 10px;">Also created:</div>
      <ul>
        <li>Markdown report</li>
        <li>Evidence bundle</li>
      </ul>
    </div>
  </div>
  <div class="card">
    <details>
      <summary>Technical appendix</summary>
      <div style="margin-top: 14px;">
        <h2>TaskFrame summary</h2>
        <pre>{html.escape(render_json_block(report_model.get('taskframe_summary', {})))}</pre>
        <h2>Raw outputs</h2>
        <pre>{html.escape(render_json_block(report_model.get('raw_outputs', {})))}</pre>
      </div>
    </details>
  </div>
</div>
</body>
</html>"""


def _build_demo_run_report_model(runtime_root: Path, frame: dict, outputs: dict, audit: list, scenario: dict, story_type: str) -> dict[str, Any]:
    state = _string(frame.get("state"))
    frame_id = _string(frame.get("frame_id"))
    scenario_label = _string(scenario.get("label") or scenario.get("name") or scenario.get("title") or frame.get("scenario_title") or frame.get("manifest_name") or frame.get("manifest_id") or "Selected demo")
    scenario_id = _string(scenario.get("id") or scenario.get("scenario_id"))
    manifest_id = _string(frame.get("manifest_id"))
    step_items = _build_step_report_items(frame, outputs, story_type)
    paths = get_demo_run_report_paths(runtime_root, frame_id)
    status_badge, badge_class = _status_badge(state)
    return {
        "report_title": "Autonomous Business Worker Demo Report",
        "scenario_id": scenario_id,
        "scenario_label": scenario_label,
        "scenario_type": story_type,
        "manifest_id": manifest_id,
        "frame_id": frame_id,
        "state": state,
        "status_badge": status_badge,
        "badge_class": badge_class,
        "generated_at": utc_now(),
        "demo_mode": "Dry run",
        "plain_summary": _plain_summary(story_type, state, frame, outputs, step_items),
        "step_items": step_items,
        "output_title": _output_title(story_type, state),
        "output_text": _output_text(story_type, state, frame, outputs, paths, step_items),
        "output_bullets": _output_bullets(story_type, state, frame, outputs, step_items, paths),
        "output_raw": outputs,
        "approval_text": _approval_text(story_type, state, frame),
        "pending_actions": _pending_actions_for_report(frame),
        "evidence_text": _evidence_text(story_type, state, frame, outputs, step_items, audit),
        "evidence_items": _evidence_items(story_type, state, frame, outputs, step_items, audit),
        "taskframe_summary": _demo_taskframe_summary(frame),
        "raw_frame": frame,
        "raw_outputs": outputs,
        "raw_audit": audit,
        "evidence_bundle_path": paths["evidence_bundle_path"],
        "run_report_markdown_path": paths["markdown_path"],
        "run_report_html_path": paths["html_path"],
        "run_report_evidence_bundle_path": paths["evidence_bundle_path"],
        "business_report_markdown_path": "",
        "business_report_html_path": "",
        "business_report_evidence_bundle_path": "",
    }


def _business_report_summary(report_model: dict) -> str:
    report_model = report_model if isinstance(report_model, dict) else {}
    if str(report_model.get("state", "")).startswith("FAILED"):
        return "No business report artifact was found for this run."
    if _string(report_model.get("scenario_type")) == "report_generation":
        return "The worker generated a business report from the selected source data and prepared audit evidence for review."
    return "The worker generated a run report for this demo run."


def _build_demo_evidence_bundle(runtime_root: Path, report_model: dict, frame: dict, outputs: dict, audit: list, paths: dict[str, str]) -> dict[str, Any]:
    frame_id = str(report_model.get("frame_id", ""))
    return {
        "bundle_version": 1,
        "report_version": DEMO_REPORT_VERSION,
        "generated_at": report_model.get("generated_at", utc_now()),
        "frame_id": frame_id,
        "scenario_id": report_model.get("scenario_id", ""),
        "scenario_label": report_model.get("scenario_label", ""),
        "scenario_type": report_model.get("scenario_type", ""),
        "manifest_id": report_model.get("manifest_id", ""),
        "state": report_model.get("state", ""),
        "taskframe_path": str(runtime_root / "runs" / frame_id / "taskframe.json"),
        "outputs_path": str(runtime_root / "runs" / frame_id / "outputs.json"),
        "audit_path": str(runtime_root / "runs" / frame_id / "audit.json"),
        "run_report_markdown_path": str(runtime_root / "outputs" / "reports" / f"{frame_id}_run_report.md"),
        "run_report_html_path": str(runtime_root / "outputs" / "reports" / f"{frame_id}_run_report.html"),
        "evidence_bundle_path": report_model.get("evidence_bundle_path", ""),
        "taskframe_summary": report_model.get("taskframe_summary", {}),
        "taskframe": frame,
        "outputs": outputs,
        "audit": audit,
        "step_items": report_model.get("step_items", []),
        "plain_summary": report_model.get("plain_summary", ""),
    }


def _build_step_report_items(frame: dict, outputs: dict, story_type: str) -> list[dict[str, Any]]:
    steps = frame.get("steps", []) if isinstance(frame.get("steps", []), list) else []
    validations = frame.get("validations", []) if isinstance(frame.get("validations", []), list) else []
    evidence = frame.get("evidence", []) if isinstance(frame.get("evidence", []), list) else []
    tool_calls = frame.get("tool_calls", []) if isinstance(frame.get("tool_calls", []), list) else []
    llm_calls = frame.get("llm_calls", []) if isinstance(frame.get("llm_calls", []), list) else []
    failed_step_id = _failed_step_id(frame)
    current_step_id = _string(frame.get("current_step_id"))
    failed_step_index = _step_index_for_id(steps, failed_step_id)
    current_step_index = _step_index_for_id(steps, current_step_id)
    step_items: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        step_id = _string(step.get("step_id") or step.get("id"))
        status = _normalize_step_status(step.get("status"), index, failed_step_index, current_step_index)
        status_label, badge_class = _status_badge_for_step(status)
        title = _step_title_for_story_type(story_type, step_id, index)
        output_alias = _string(step.get("output_alias") or step.get("result_ref"))
        output_value = outputs.get(output_alias) if output_alias and isinstance(outputs, dict) else outputs.get(step_id) if isinstance(outputs, dict) else None
        step_items.append(
            {
                "index": index,
                "step_id": step_id,
                "title": title,
                "status": status,
                "status_label": status_label,
                "status_class": _status_class(status),
                "badge_class": badge_class,
                "command": _string(step.get("command")),
                "output_alias": output_alias,
                "output": output_value,
                "result_text": _step_result_text(output_value, status, story_type),
                "inputs_text": render_json_block(frame.get("inputs", {})),
                "validation_text": _joined_records(_records_for_step(validations, step_id), "message"),
                "tool_text": _joined_records(_records_for_step(tool_calls, step_id), "tool"),
                "llm_text": _joined_records(_records_for_step(llm_calls, step_id), "action"),
                "evidence_text": _evidence_summary_text(_records_for_step(evidence, step_id)),
                "error_text": _string(step.get("error") or step.get("last_error") or ""),
                "reason": _step_reason(status, step, story_type, index, failed_step_id, current_step_id),
                "safe_outcome": _safe_outcome(status, story_type),
                "raw_step": step,
                "validations": _records_for_step(validations, step_id),
                "tool_calls": _records_for_step(tool_calls, step_id),
                "llm_calls": _records_for_step(llm_calls, step_id),
                "evidence": _records_for_step(evidence, step_id),
                "audit_events": [],
            }
        )
        step_items[-1]["step_outcome"] = build_step_outcome(step_items[-1], frame)
    return step_items


def build_step_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    step_item = step_item if isinstance(step_item, dict) else {}
    frame = frame if isinstance(frame, dict) else {}
    status = _string(step_item.get("status")).upper()
    step_id = _string(step_item.get("step_id") or step_item.get("id"))
    if status.startswith("FAILED"):
        return _failed_step_outcome(step_item, frame)
    builder = OUTCOME_BUILDERS.get(step_id)
    if builder is not None:
        return builder(step_item, frame)
    story_type = _detect_demo_story_type({}, frame, frame.get("outputs", {}) if isinstance(frame.get("outputs", {}), dict) else {})
    if story_type == "report_generation":
        return _report_step_outcome(step_item)
    return _generic_step_outcome(step_item)


def _extract_customer_id_from_frame(frame: dict) -> str:
    inputs = frame.get("inputs", {}) if isinstance(frame.get("inputs", {}), dict) else {}
    outputs = frame.get("outputs", {}) if isinstance(frame.get("outputs", {}), dict) else {}
    for value in (
        inputs.get("customer_id"),
        _nested_lookup(inputs, ("customer", "customer_id")),
        outputs.get("customer_id"),
        _nested_lookup(outputs, ("customer", "customer_id")),
    ):
        text = _string(value)
        if text:
            return text
    return ""


def _extract_tracking_reference(outputs: dict, output_value: object) -> str:
    if isinstance(output_value, dict):
        tracking = _string(output_value.get("tracking_reference") or output_value.get("tracking_number") or output_value.get("tracking"))
        if tracking:
            return tracking
    if isinstance(outputs, dict):
        shipment = outputs.get("shipment", {})
        if isinstance(shipment, dict):
            tracking = _string(shipment.get("tracking_reference") or shipment.get("tracking_number") or shipment.get("tracking"))
            if tracking:
                return tracking
    return ""


def _failed_step_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    step_id = _string(step_item.get("step_id"))
    tool_calls = step_item.get("tool_calls", []) if isinstance(step_item.get("tool_calls", []), list) else []
    raw_step = step_item.get("raw_step", {}) if isinstance(step_item.get("raw_step", {}), dict) else {}
    failure = classify_workbench_failure(
        _failure_error_for_step(step_item, frame),
        raw_step or {"step_id": step_id, "kind": step_item.get("status", ""), "output_alias": step_item.get("output_alias", "")},
    )
    details = []
    if failure.get("category") == "external_auth_failure":
        tool_args = _latest_tool_args(tool_calls)
        range_name = _string(tool_args.get("range_name"))
        spreadsheet_id = _string(tool_args.get("spreadsheet_id"))
        if range_name and spreadsheet_id:
            details.append(f"Could not read {range_name} from spreadsheet {spreadsheet_id}.")
        else:
            details.append(_string(failure.get("summary")) or "This step failed.")
        details.extend(
            [
                f"Failure type: {_failure_label(failure.get('category', 'unknown_failure'))}",
                f"Reason: {_string(failure.get('reason') or failure.get('summary'))}",
                "Safe outcome: Workflow stopped before any side effect was created.",
                f"Recommended action: {_string(failure.get('recommended_action'))}",
            ]
        )
    elif failure.get("category") == "fixture_missing":
        details.extend(
            [
                "Fixture data not available for this tool/range.",
                f"Failure type: {_failure_label(failure.get('category', 'unknown_failure'))}",
                f"Recommended action: {_string(failure.get('recommended_action'))}",
            ]
        )
    else:
        details.append("This step failed.")
        if step_id == "lookup_customer":
            customer_id = _extract_customer_id_from_frame(frame)
            if customer_id:
                details.append(f"Customer record not found for {customer_id}.")
        elif step_id == "lookup_order":
            order_ref = _extract_order_reference(frame.get("inputs", {}), frame.get("outputs", {}), step_item.get("output"))
            if order_ref:
                details.append(f"Order record not found for {order_ref}.")
        elif step_id == "lookup_shipment":
            tracking = _extract_tracking_reference(frame.get("outputs", {}), step_item.get("output"))
            if tracking:
                details.append(f"Shipment record not found for {tracking}.")
        elif step_id == "read_payment":
            details.append("Payment record not found.")
        elif step_id == "extract_order_ref":
            details.append("No order number could be found.")
        details.extend(
            [
                f"Failure type: {_failure_label(failure.get('category', 'unknown_failure'))}",
                f"Reason: {_string(failure.get('reason') or failure.get('summary') or step_item.get('error_text') or step_item.get('reason'))}",
                f"Recommended action: {_string(failure.get('recommended_action'))}",
            ]
        )
        if str(frame.get("state", "")).startswith("FAILED"):
            details.append("Safe outcome: Workflow stopped before any unsafe action was taken.")
    return {
        "title": failure.get("title", "This step failed."),
        "summary": failure.get("summary", "This step failed."),
        "details": details,
    }


def build_extract_order_ref_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    order_ref = ""
    if isinstance(output, dict):
        order_ref = _string(output.get("order_ref") or output.get("value") or output.get("reference"))
    else:
        order_ref = _string(output)
    if order_ref:
        return {"title": "Order number found", "summary": f"Order number found: {order_ref}", "details": [f"Order number found: {order_ref}"]}
    return {"title": "Order number not found", "summary": "No order number could be found.", "details": ["No order number could be found."]}


def build_classification_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    label = ""
    confidence = ""
    reason = ""
    if isinstance(output, dict):
        label = _string(output.get("label"))
        confidence = _string(output.get("confidence"))
        reason = _string(output.get("reason"))
    summary = "The customer message was classified as an order-status request."
    if label == "refund":
        summary = "The customer message was classified as a refund request."
    details = [f"Classified as: {label or 'unknown'}"]
    if confidence:
        details.append(f"Confidence: {confidence}")
    if reason:
        details.append(f"Reason: {reason}")
    return {"title": "Message classified", "summary": summary, "details": details}


def build_customer_lookup_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    inputs = frame.get("inputs", {}) if isinstance(frame.get("inputs", {}), dict) else {}
    customer_id = _string(inputs.get("customer_id") or _nested_lookup(inputs, ("customer", "customer_id")))
    if isinstance(output, dict):
        name = _string(output.get("name") or _nested_lookup(output, ("customer", "name")))
        customer_id = customer_id or _string(output.get("customer_id") or _nested_lookup(output, ("customer", "customer_id")))
        if name or customer_id:
            bits = [part for part in (name, customer_id) if part]
            summary = f"Customer record found: {' / '.join(bits)}"
            return {"title": "Customer record found", "summary": summary, "details": [summary]}
    if customer_id:
        summary = f"Customer record not found for {customer_id}."
    else:
        summary = "Customer record not found."
    return {"title": "Customer record not found", "summary": summary, "details": [summary]}


def build_order_lookup_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    inputs = frame.get("inputs", {}) if isinstance(frame.get("inputs", {}), dict) else {}
    order_ref = _extract_order_reference(
        inputs.get("order_id"),
        inputs.get("order_ref"),
        inputs.get("message"),
        step_item.get("output"),
    )
    if isinstance(output, dict):
        order_id = _string(output.get("order_id") or output.get("order_ref"))
        status = _string(output.get("status"))
        if order_id or status:
            summary = f"Order found: {order_id or order_ref or 'unknown'}"
            details = [summary]
            if status:
                details.append(f"Status: {status}")
            return {"title": "Order found", "summary": summary, "details": details}
    if order_ref:
        summary = f"Order record not found for {order_ref}."
    else:
        summary = "Order record not found."
    return {"title": "Order record not found", "summary": summary, "details": [summary]}


def build_payment_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    if isinstance(output, dict):
        status = _string(output.get("status"))
        amount = _string(output.get("amount") or output.get("paid_amount") or output.get("payment_amount"))
        details = []
        if status:
            details.append(f"Payment status: {status}")
        if amount:
            details.append(f"Amount: {amount}")
        if details:
            return {"title": "Payment record found", "summary": details[0], "details": details}
    return {"title": "Payment record not found", "summary": "Payment record not found.", "details": ["Payment record not found."]}


def build_shipment_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    if isinstance(output, dict):
        status = _string(output.get("status"))
        tracking = _string(output.get("tracking_reference") or output.get("tracking_number") or output.get("tracking"))
        details = []
        if status:
            details.append(f"Shipment status: {status}")
        if tracking:
            details.append(f"Tracking reference: {tracking}")
        if details:
            return {"title": "Shipment record found", "summary": details[0], "details": details}
    return {"title": "Shipment record not found", "summary": "Shipment record not found.", "details": ["Shipment record not found."]}


def build_context_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    outputs = frame.get("outputs", {}) if isinstance(frame.get("outputs", {}), dict) else {}
    facts: list[str] = []
    order_id = _nested_lookup(outputs, ("order", "order_id"))
    customer_name = _nested_lookup(outputs, ("customer", "name"))
    order_status = _nested_lookup(outputs, ("order", "status"))
    shipment_tracking = _nested_lookup(outputs, ("shipment", "tracking_reference"))
    if order_id:
        facts.append(f"Order: {_string(order_id)}")
    if customer_name:
        facts.append(f"Customer: {_string(customer_name)}")
    if order_status:
        facts.append(f"Order status: {_string(order_status)}")
    if shipment_tracking:
        facts.append(f"Tracking reference: {_string(shipment_tracking)}")
    details = ["Order facts were assembled for reply drafting."]
    details.extend(facts)
    return {"title": "Order context assembled", "summary": "Order facts were assembled for reply drafting.", "details": details}


def build_draft_reply_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    reply = ""
    if isinstance(output, dict):
        reply = _string(output.get("body") or output.get("reply") or output.get("message") or output.get("text"))
    else:
        reply = _string(output)
    if reply:
        return {"title": "Customer reply prepared", "summary": "Customer reply was prepared.", "details": ["Customer reply was prepared.", f"Prepared reply: {reply}"]}
    return {"title": "Customer reply not prepared", "summary": "No customer reply was prepared.", "details": ["No customer reply was prepared."]}


def build_validation_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    validations = step_item.get("validations", [])
    if isinstance(validations, list):
        failed = [item for item in validations if isinstance(item, dict) and item.get("ok") is False]
        if failed:
            reason = _string(failed[0].get("message") or failed[0].get("reason") or "Validation failed.")
            return {"title": "Reply validation failed", "summary": "Prepared reply failed validation.", "details": ["Prepared reply failed validation.", f"Reason: {reason}"]}
    return {"title": "Reply validated", "summary": "Prepared reply passed validation against business facts.", "details": ["Prepared reply passed validation against business facts."]}


def build_report_artifact_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    output = step_item.get("output")
    if isinstance(output, dict):
        html_path = _string(output.get("html_path"))
        markdown_path = _string(output.get("markdown_path"))
        evidence_path = _string(output.get("evidence_bundle_path"))
        if html_path:
            details = ["Report artifact generated.", f"HTML file: {html_path}"]
            if markdown_path:
                details.append(f"Markdown file: {markdown_path}")
            if evidence_path:
                details.append(f"Evidence bundle: {evidence_path}")
            return {"title": "Report artifact generated", "summary": "Report artifact generated.", "details": details}
    return {"title": "Report artifact not generated", "summary": "No report artifact was recorded for this step.", "details": ["No report artifact was recorded for this step."]}


def build_pending_action_outcome(step_item: dict, frame: dict) -> dict[str, Any]:
    raw_step = step_item.get("raw_step", {}) if isinstance(step_item.get("raw_step", {}), dict) else {}
    action = _string(raw_step.get("action") or raw_step.get("human_summary") or "Send customer message")
    body = ""
    output = step_item.get("output")
    if isinstance(output, dict):
        body = _string(output.get("body") or output.get("message") or output.get("reply") or output.get("summary"))
    details = ["A customer message was staged for approval.", f"Action: {action}", "Status: Pending approval"]
    if body:
        details.append(f"Prepared message: {body}")
    return {"title": "Customer message staged for approval", "summary": "A customer message was staged for approval.", "details": details}


def _report_step_outcome(step_item: dict) -> dict[str, Any]:
    output = step_item.get("output")
    if isinstance(output, dict):
        html_path = _string(output.get("html_path"))
        markdown_path = _string(output.get("markdown_path"))
        evidence_path = _string(output.get("evidence_bundle_path"))
        if html_path:
            details = ["Report artifact generated.", f"HTML file: {html_path}"]
            if markdown_path:
                details.append(f"Markdown file: {markdown_path}")
            if evidence_path:
                details.append(f"Evidence bundle: {evidence_path}")
            return {"title": "Report artifact generated", "summary": "Report artifact generated.", "details": details}
    return {"title": "Report artifact not generated", "summary": "No report artifact was recorded for this step.", "details": ["No report artifact was recorded for this step."]}


def _generic_step_outcome(step_item: dict) -> dict[str, Any]:
    output_alias = _string(step_item.get("output_alias"))
    output = step_item.get("output")
    if output in ({}, [], None, ""):
        return {"title": "No output recorded", "summary": "No output was recorded for this step.", "details": ["No output was recorded for this step."]}
    if isinstance(output, dict):
        metadata = output.get("metadata") if isinstance(output.get("metadata"), dict) else {}
        if metadata:
            details = []
            if metadata.get("source") == "workbench_fixture":
                details.append("Source: fixture data")
            elif metadata.get("source"):
                details.append(f"Source: {_string(metadata.get('source'))}")
            if "live_external_call" in metadata:
                details.append(f"Live external call: {'yes' if metadata.get('live_external_call') else 'no'}")
            if "fixture_mode" in output:
                details.append(f"Fixture mode: {'yes' if output.get('fixture_mode') else 'no'}")
            if "dry_run" in output:
                details.append(f"Dry-run: {'yes' if output.get('dry_run') else 'no'}")
            if output.get("row_count") is not None:
                details.append(f"Rows: {output.get('row_count')}")
            details.append(f"Summary: {_short_step_summary(output)}")
            return {
                "title": "Fixture output" if metadata.get("source") == "workbench_fixture" else "Output recorded",
                "summary": f"Output produced under alias: {output_alias}" if output_alias else "Output recorded.",
                "details": details,
            }
    return {
        "title": "Output recorded",
        "summary": f"Output produced under alias: {output_alias}" if output_alias else "Output recorded.",
        "details": [f"Output produced under alias: {output_alias}" if output_alias else "Output recorded.", f"Summary: {_short_step_summary(output)}"],
    }


def _failure_error_for_step(step_item: dict, frame: dict) -> dict | str:
    if isinstance(step_item.get("error_text"), str) and step_item.get("error_text"):
        return str(step_item.get("error_text"))
    if isinstance(step_item.get("reason"), str) and step_item.get("reason"):
        return str(step_item.get("reason"))
    raw_step = step_item.get("raw_step", {}) if isinstance(step_item.get("raw_step", {}), dict) else {}
    if raw_step.get("error"):
        return raw_step.get("error")
    if raw_step.get("last_error"):
        return raw_step.get("last_error")
    for error in frame.get("errors", []) if isinstance(frame.get("errors", []), list) else []:
        if isinstance(error, dict):
            if not step_item.get("step_id") or str(error.get("step_id", "")) == str(step_item.get("step_id", "")):
                return error
            if error.get("message"):
                return error
        elif error:
            return error
    return ""


def _latest_tool_args(tool_calls: list[dict]) -> dict:
    if not tool_calls:
        return {}
    item = tool_calls[-1] if isinstance(tool_calls[-1], dict) else {}
    args = item.get("args", {})
    return args if isinstance(args, dict) else {}


def _failure_label(category: str) -> str:
    return {
        "manifest_validation_failure": "Manifest/config problem",
        "missing_required_input": "Missing required input",
        "tool_execution_failure": "Tool/runtime failure",
        "external_auth_failure": "External authentication failure",
        "external_dependency_unavailable": "External dependency unavailable",
        "business_validation_failure": "Business validation failure",
        "fixture_missing": "Fixture data not available",
        "unknown_failure": "Unknown failure",
    }.get(str(category or ""), "Unknown failure")


OUTCOME_BUILDERS = {
    "extract_order_ref": build_extract_order_ref_outcome,
    "extract_order_id": build_extract_order_ref_outcome,
    "classify_message": build_classification_outcome,
    "classify_customer_message": build_classification_outcome,
    "lookup_customer": build_customer_lookup_outcome,
    "lookup_order": build_order_lookup_outcome,
    "read_payment": build_payment_outcome,
    "lookup_payment": build_payment_outcome,
    "lookup_shipment": build_shipment_outcome,
    "build_order_context": build_context_outcome,
    "draft_reply": build_draft_reply_outcome,
    "draft_customer_status_reply": build_draft_reply_outcome,
    "validate_reply": build_validation_outcome,
    "validate_draft_reply": build_validation_outcome,
    "generate_report": build_report_artifact_outcome,
    "generate_report_artifact": build_report_artifact_outcome,
    "report_artifact": build_report_artifact_outcome,
    "prepare_pending_send": build_pending_action_outcome,
}


def _detect_demo_story_type(scenario: dict, frame: dict, outputs: dict) -> str:
    scenario = scenario if isinstance(scenario, dict) else {}
    frame = frame if isinstance(frame, dict) else {}
    outputs = outputs if isinstance(outputs, dict) else {}
    for candidate in (
        scenario.get("scenario_type"),
        scenario.get("story_type"),
        scenario.get("type"),
        scenario.get("category"),
        scenario.get("id"),
        scenario.get("label"),
        scenario.get("name"),
        scenario.get("description"),
        frame.get("scenario_type"),
        frame.get("manifest_id"),
        frame.get("scenario_id"),
        outputs,
    ):
        story_type = _story_type_from_value(candidate)
        if story_type != "unknown":
            return story_type
    return "unknown"


def _story_type_from_value(value: object) -> str:
    text = _string(value).lower()
    if not text:
        return "unknown"
    if any(token in text for token in ("report_generation", "report generation", "generate report", "reporting", "run report", "evidence bundle", "html_path", "markdown_path", "report_artifact", "report artifact", "run_report", "evidence_pack", "evidence pack")):
        return "report_generation"
    if any(token in text for token in ("procurement", "supplier", "reorder", "low stock", "stock", "purchase order", "po_", "supplier_message")):
        return "procurement"
    if any(token in text for token in ("accounting", "reconciliation", "ledger", "invoice", "payments_sheet", "recon_", "sheet write")):
        return "accounting"
    if any(token in text for token in ("customer", "order", "shipment", "reply", "status", "message_status", "customer_status", "draft_reply")):
        return "customer_status"
    return "unknown"


def _build_demo_report_paths(runtime_root: Path, frame_id: str) -> dict[str, str]:
    return get_demo_run_report_paths(runtime_root, frame_id)


def _read_json_dict(path: Path, fallback: object) -> dict[str, Any]:
    if path.is_file():
        try:
            data = read_json(path)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return fallback if isinstance(fallback, dict) else {}


def _read_json_list(path: Path, fallback: object) -> list[Any]:
    if path.is_file():
        try:
            data = read_json(path)
            return data if isinstance(data, list) else []
        except Exception:
            pass
    return fallback if isinstance(fallback, list) else []


def _status_badge(state: str) -> tuple[str, str]:
    state = state.upper()
    if state == "COMPLETED":
        return "Completed", "success"
    if state == "WAITING_FOR_EXECUTE":
        return "Awaiting approval", "warning"
    if state.startswith("FAILED"):
        return "Stopped safely", "danger"
    if state == "RUNNING":
        return "In progress", "pending"
    if state == "READY":
        return "Ready", "pending"
    if state in {"WAITING_FOR_INPUT", "EXECUTING_PENDING", "VERIFYING"}:
        return "In progress", "pending"
    return "In progress", "pending"


def _status_class(status: str) -> str:
    status = status.upper()
    if status == "COMPLETED":
        return "completed"
    if status.startswith("FAILED"):
        return "failed"
    if status in {"SKIPPED", "NOT_REACHED"}:
        return "notreached"
    return "pending"


def _status_badge_for_step(status: str) -> tuple[str, str]:
    status = status.upper()
    if status == "COMPLETED":
        return "Completed", "success"
    if status.startswith("FAILED"):
        return "Failed", "danger"
    if status in {"SKIPPED", "NOT_REACHED"}:
        return "Not reached", "pending"
    return "Pending", "warning"


def _normalize_step_status(status: object, index: int, failed_step_index: int, current_step_index: int) -> str:
    value = _string(status).upper()
    if value in {"COMPLETED", "FAILED", "FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION", "SKIPPED"}:
        return value
    if failed_step_index and index > failed_step_index:
        return "NOT_REACHED"
    if current_step_index and index > current_step_index:
        return "NOT_REACHED"
    return "PENDING"


def _failed_step_id(frame: dict) -> str:
    for step in frame.get("steps", []) if isinstance(frame.get("steps", []), list) else []:
        if isinstance(step, dict) and _string(step.get("status")).upper().startswith("FAILED"):
            return _string(step.get("step_id") or step.get("id"))
    return ""


def _step_index_for_id(steps: list, step_id: str) -> int:
    if not step_id:
        return 0
    for index, step in enumerate(steps, start=1):
        if isinstance(step, dict) and _string(step.get("step_id") or step.get("id")) == step_id:
            return index
    return 0


def _step_title_for_story_type(story_type: str, step_id: str, index: int) -> str:
    if story_type == "report_generation":
        titles = [
            "Read business data",
            "Checked source records",
            "Built report summary",
            "Generated report artifact",
            "Prepared evidence pack",
        ]
        if 1 <= index <= len(titles):
            return titles[index - 1]
        return f"Report step {index}"
    mapping = {
        "customer_status": {
            "extract_order_ref": "Extract order reference",
            "classify_customer_message": "Classify the customer request",
            "validate_order_ref": "Validate the order reference",
            "lookup_customer": "Check customer record",
            "lookup_order": "Check order record",
            "read_payment": "Check payment record",
            "lookup_shipment": "Check shipment record",
            "build_order_context": "Build order context",
            "draft_reply": "Prepare customer reply",
            "draft_customer_status_reply": "Prepare customer reply",
            "validate_reply": "Validate reply against business facts",
            "validate_draft_reply": "Validate reply against business facts",
        },
        "procurement": {
            "read_inventory": "Read inventory data",
            "find_low_stock": "Find low-stock items",
            "compare_suppliers": "Compare supplier options",
            "draft_po": "Draft purchase order",
            "draft_supplier_message": "Prepare supplier message",
            "prepare_pending_send": "Stage supplier message for approval",
        },
        "accounting": {
            "read_sheets": "Read accounting sheets",
            "load_payments": "Read payment records",
            "load_orders": "Read order records",
            "load_invoices": "Read invoice records",
            "load_ledger": "Read ledger records",
            "reconcile": "Reconcile accounting records",
            "draft_reconciliation_exception_summary": "Draft exception summary",
            "build_recon_sheet_rows": "Prepare reconciliation sheet rows",
        },
    }
    if step_id in mapping.get(story_type, {}):
        return mapping[story_type][step_id]
    return _humanize_identifier(step_id or f"step_{index}")


def _humanize_identifier(value: str) -> str:
    value = _string(value).replace("_", " ").replace("-", " ")
    if not value:
        return "Step"
    return value[:1].upper() + value[1:]


def _joined_records(records: list[dict], key: str, default: str = "") -> str:
    if not records:
        return default
    values = []
    for item in records:
        if isinstance(item, dict):
            if key == "message" and item.get("message"):
                values.append(_string(item.get("message")))
            elif key == "tool" and item.get("tool"):
                values.append(_string(item.get("tool")))
            elif key == "action" and item.get("action"):
                values.append(_string(item.get("action")))
            elif key == "step_id" and item.get("dataset"):
                values.append(f"{_string(item.get('dataset'))}: {_string(item.get('found', ''))}")
            elif item.get(key) is not None:
                values.append(_string(item.get(key)))
    return "; ".join(value for value in values if value) or default


def _evidence_summary_text(records: list[dict]) -> str:
    if not records:
        return "Not recorded"
    parts: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if item.get("dataset") is not None:
            found = "found" if item.get("found") else "missing"
            parts.append(f"{_string(item.get('dataset'))}: {found}")
        elif item.get("source"):
            parts.append(_string(item.get("source")))
        elif item.get("message"):
            parts.append(_string(item.get("message")))
    return "; ".join(part for part in parts if part) or "Not recorded"


def _records_for_step(records: list[dict], step_id: str) -> list[dict]:
    if not records:
        return []
    matched = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if _string(item.get("step_id")) == step_id:
            matched.append(item)
            continue
        data_text = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if step_id and step_id in data_text:
            matched.append(item)
    return matched


def _short_step_summary(value: object) -> str:
    if value in ({}, [], None, ""):
        return ""
    if isinstance(value, dict):
        for key in ("body", "reply", "summary", "text", "message", "html_path", "markdown_path", "evidence_bundle_path", "order_ref", "order_id", "customer_id", "name", "status", "tracking_reference", "amount", "label", "confidence", "reason"):
            if value.get(key):
                text = _string(value.get(key))
                if text:
                    return text
        parts: list[str] = []
        for key, item in value.items():
            if item in (None, ""):
                continue
            if isinstance(item, (dict, list)):
                parts.append(f"{key}: {render_json_block(item)}")
            else:
                parts.append(f"{key}: {_string(item)}")
        if parts:
            return "; ".join(parts)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        parts = [_string(item) for item in value if _string(item)]
        return "; ".join(parts)
    return _string(value)


def _extract_order_reference(*values: object) -> str:
    for value in values:
        text = _string(value)
        if not text:
            continue
        match = re.search(r"\b(?:ORD|PO|INV)-[A-Z0-9]+\b", text, re.IGNORECASE)
        if match:
            return match.group(0).upper()
    return ""


def _step_result_text(output_value: object, status: str, story_type: str) -> str:
    if status.startswith("FAILED"):
        return "Stopped safely."
    if output_value in ({}, [], None, ""):
        if story_type == "report_generation":
            return "The report has not been generated yet."
        return "No output recorded."
    if isinstance(output_value, dict):
        for key in ("body", "reply", "summary", "text", "message", "artifact", "html_path", "markdown_path", "evidence_bundle_path"):
            if key in output_value and output_value.get(key):
                return _string(output_value.get(key))
        return json.dumps(output_value, ensure_ascii=False, sort_keys=True)
    if isinstance(output_value, list):
        return ", ".join(_string(item) for item in output_value)
    return _string(output_value)


def _step_reason(status: str, step: dict, story_type: str, index: int, failed_step_id: str, current_step_id: str) -> str:
    if status.startswith("FAILED"):
        return _string(step.get("error") or step.get("last_error") or "Validation failed.")
    if status == "NOT_REACHED":
        if story_type == "report_generation":
            return "Selected demo is waiting to run."
        if failed_step_id:
            return "Previous validation failed."
        return "Not reached."
    if failed_step_id and current_step_id and index > 0:
        return "Previous validation failed."
    return ""


def _safe_outcome(status: str, story_type: str) -> str:
    if status.startswith("FAILED"):
        if story_type == "report_generation":
            return "No report was generated."
        return "Workflow stopped safely before any message or side effect was sent."
    if story_type == "report_generation":
        return "Audit evidence was prepared for review."
    return "The workflow completed safely."


def _plain_summary(story_type: str, state: str, frame: dict, outputs: dict, step_items: list[dict]) -> str:
    if story_type == "report_generation":
        if state.startswith("FAILED"):
            return "Worker stopped safely. No business report artifact was prepared."
        return "The worker generated a business report from the selected source data and prepared audit evidence for review."
    if story_type == "procurement":
        if state.startswith("FAILED"):
            return "Worker stopped safely before preparing procurement outputs."
        return "The worker reviewed inventory, prepared procurement outputs, and staged the action for approval."
    if story_type == "accounting":
        if state.startswith("FAILED"):
            return "Worker stopped safely during accounting validation."
        return "The worker reconciled accounting records and prepared exception evidence for review."
    if state.startswith("FAILED"):
        return "Worker stopped safely. The worker stopped because required customer/order validation failed. No customer message was prepared or sent."
    if any(item.get("status") == "PENDING" for item in step_items):
        return "A customer asked about an order. The worker checked the customer, order, payment, and shipment records, then prepared a reply for approval."
    return "The worker completed the customer workflow safely."


def _output_title(story_type: str, state: str) -> str:
    if story_type == "report_generation":
        return "Business report generated"
    if story_type == "procurement":
        return "Prepared procurement action"
    if story_type == "accounting":
        return "Prepared reconciliation result"
    if state.startswith("FAILED"):
        return "Why the worker stopped"
    return "Prepared reply"


def _output_text(story_type: str, state: str, frame: dict, outputs: dict, paths: dict[str, str], step_items: list[dict]) -> str:
    if story_type == "report_generation":
        if state.startswith("FAILED"):
            return "No business report artifact was found for this run."
        return "\n".join(
            [
                "Business report generated",
                f"File: {Path(paths['html_path']).name}",
                "",
                "Also created:",
                "- Markdown report",
                "- Evidence bundle",
            ]
        )
    if state.startswith("FAILED"):
        return "The worker could not safely answer this customer request."
    if story_type == "procurement":
        return "The worker prepared procurement outputs and audit evidence."
    if story_type == "accounting":
        return "The worker prepared reconciliation outputs and audit evidence."
    reply = _string(_nested_lookup(outputs, ("draft_reply", "body")) or _nested_lookup(outputs, ("draft_reply", "reply")) or frame.get("final_response"))
    if reply:
        return reply
    return "No customer reply was prepared."


def _output_bullets(story_type: str, state: str, frame: dict, outputs: dict, step_items: list[dict], paths: dict[str, str]) -> list[str]:
    if story_type == "report_generation":
        return [
            "Business report generated",
            "Markdown report created",
            "Evidence bundle created",
            f"Report HTML: {Path(paths['html_path']).name}",
        ]
    if state.startswith("FAILED"):
        return [
            "Customer/order validation failed",
            "No reply was prepared",
            "No message was sent",
        ]
    facts = []
    if outputs.get("order"):
        facts.append("Order exists")
    if outputs.get("customer"):
        facts.append("Customer ownership verified")
    if _nested_lookup(outputs, ("shipment", "status")):
        facts.append(f"Shipment status: {_string(_nested_lookup(outputs, ('shipment', 'status')))}")
    if _nested_lookup(outputs, ("order", "status")):
        facts.append(f"Order status: {_string(_nested_lookup(outputs, ('order', 'status')))}")
    if _nested_lookup(outputs, ("tracking_reference",)):
        facts.append(f"Tracking reference: {_string(_nested_lookup(outputs, ('tracking_reference',)))}")
    if not facts:
        facts.append("Business facts checked")
    return facts


def _approval_text(story_type: str, state: str, frame: dict) -> str:
    if state.startswith("FAILED"):
        return "No approval action was created because the workflow stopped safely."
    if frame.get("pending_actions"):
        return "Pending approval action for this run."
    if story_type == "report_generation":
        return "No approval action was needed for the generated report."
    return "No pending approval action for this run."


def _pending_actions_for_report(frame: dict) -> list[dict[str, Any]]:
    actions = frame.get("pending_actions", []) if isinstance(frame.get("pending_actions", []), list) else []
    pending: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        pending.append(
            {
                "action": _string(action.get("action_type") or action.get("action") or action.get("human_summary")),
                "status": _string(action.get("status")),
                "risk": _string(action.get("risk_class") or action.get("risk") or ("Side effect, approval required" if action.get("status") == "PENDING_APPROVAL" else "")),
                "dry_run": "Yes" if str(action.get("dry_run", "Yes")).lower() in {"yes", "true", "1"} else _string(action.get("dry_run")),
                "body": _string(action.get("body") or action.get("message") or action.get("summary") or ""),
            }
        )
    return pending


def _evidence_text(story_type: str, state: str, frame: dict, outputs: dict, step_items: list[dict], audit: list) -> str:
    if story_type == "report_generation":
        return "The worker generated a business report artifact and evidence pack."
    if state.startswith("FAILED"):
        return "Validation checks stopped the workflow before any customer message was sent."
    return "The worker used customer, order, shipment, payment, validation, and approval evidence."


def _evidence_items(story_type: str, state: str, frame: dict, outputs: dict, step_items: list[dict], audit: list) -> list[str]:
    items: list[str] = []
    if story_type == "report_generation":
        items.append("Report artifact: present")
        items.append("Evidence pack: present")
    elif state.startswith("FAILED"):
        items.append("Customer validation: failed")
        items.append("Order validation: failed")
    else:
        for label, key in (
            ("Customer lookup", "customer"),
            ("Order lookup", "order"),
            ("Shipment lookup", "shipment"),
            ("Payment lookup", "payment"),
        ):
            items.append(f"{label}: {'found' if outputs.get(key) else 'missing'}")
    passed = sum(1 for item in frame.get("validations", []) if isinstance(item, dict) and item.get("ok"))
    failed = sum(1 for item in frame.get("validations", []) if isinstance(item, dict) and item.get("ok") is False)
    items.append(f"Validation checks: {passed} pass / {failed} fail")
    return items


def _demo_taskframe_summary(frame: dict) -> dict[str, Any]:
    frame = frame if isinstance(frame, dict) else {}
    steps = frame.get("steps", []) if isinstance(frame.get("steps", []), list) else []
    validations = frame.get("validations", []) if isinstance(frame.get("validations", []), list) else []
    outputs = frame.get("outputs", {}) if isinstance(frame.get("outputs", {}), dict) else {}
    return {
        "frame_id": _string(frame.get("frame_id")),
        "manifest_id": _string(frame.get("manifest_id")),
        "state": _string(frame.get("state")),
        "step_count": len(steps),
        "completed_steps": sum(1 for step in steps if isinstance(step, dict) and _string(step.get("status")).upper() == "COMPLETED"),
        "failed_steps": sum(1 for step in steps if isinstance(step, dict) and _string(step.get("status")).upper().startswith("FAILED")),
        "skipped_steps": sum(1 for step in steps if isinstance(step, dict) and _string(step.get("status")).upper() == "SKIPPED"),
        "validation_count": len(validations),
        "error_count": len(frame.get("errors", [])) if isinstance(frame.get("errors", []), list) else 0,
        "pending_action_count": len(frame.get("pending_actions", [])) if isinstance(frame.get("pending_actions", []), list) else 0,
        "executed_action_count": len(frame.get("executed_actions", [])) if isinstance(frame.get("executed_actions", []), list) else 0,
        "output_keys": list(outputs.keys()),
        "created_at": _string(frame.get("created_at")),
        "updated_at": _string(frame.get("updated_at")),
    }


def _nested_lookup(value: object, path: tuple[str, ...]) -> object:
    current = value
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _slugify(value: str) -> str:
    text = _string(value).lower()
    if not text:
        return ""
    slug_chars: list[str] = []
    prev_dash = False
    for char in text:
        if char.isalnum():
            slug_chars.append(char)
            prev_dash = False
        elif not prev_dash:
            slug_chars.append("-")
            prev_dash = True
    return "".join(slug_chars).strip("-")
