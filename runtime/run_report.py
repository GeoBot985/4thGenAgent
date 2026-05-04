from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .artifact_cleanup import load_taskframe_safe
from .evidence_bundle import build_evidence_bundle, write_evidence_bundle
from .failure_summary import build_failure_summary
from .persistence import ensure_dir, load_taskframe_dict, write_json_atomic
from .taskframe import utc_now
from src.operator_approval_pack import build_approval_pack_view


REPORT_VERSION = "operator_run_report_v1"


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
        f"- Failure Message: {failure_summary.get('failure_message', '')}",
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
        f"- failure_message: {failure_summary.get('failure_message', '')}",
        f"- Failure Message: {failure_summary.get('failure_message', '')}",
        f"- Operator Explanation: {failure_summary.get('operator_explanation', '')}",
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
