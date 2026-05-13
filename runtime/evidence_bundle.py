from __future__ import annotations

from pathlib import Path

from .failure_summary import build_failure_summary
from .persistence import get_audit_path, get_outputs_path, get_summary_path, get_taskframe_path, load_taskframe_dict, write_json_atomic
from .taskframe import utc_now
from src.operator_approval_pack import build_approval_pack_view


def build_evidence_bundle(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict:
    if not isinstance(frame_id, str) or not frame_id.strip():
        raise ValueError("frame_id is required")
    frame = load_taskframe_dict(frame_id, runtime_data_dir)
    frame_dir = Path(runtime_data_dir) / "runs" / frame_id
    reports_dir = frame_dir / "reports"
    artifact_paths = {
        "taskframe_json": str(get_taskframe_path(frame_id, runtime_data_dir)),
        "summary_json": str(get_summary_path(frame_id, runtime_data_dir)),
        "outputs_json": str(get_outputs_path(frame_id, runtime_data_dir)),
        "audit_json": str(get_audit_path(frame_id, runtime_data_dir)),
        "run_report_md": str(reports_dir / "run_report.md"),
        "run_report_html": str(reports_dir / "run_report.html"),
        "approval_pack_report_md": str(reports_dir / "approval_pack_report.md"),
        "approval_pack_report_html": str(reports_dir / "approval_pack_report.html"),
        "failure_report_md": str(reports_dir / "failure_report.md"),
        "failure_report_html": str(reports_dir / "failure_report.html"),
        "evidence_bundle_json": str(reports_dir / "evidence_bundle.json"),
    }
    return {
        "bundle_version": 1,
        "generated_at": utc_now(),
        "frame_id": frame_id,
        "manifest_id": frame.get("manifest_id", ""),
        "state": frame.get("state", ""),
        "summary": _load_json_like(get_summary_path(frame_id, runtime_data_dir)),
        "trigger": frame.get("trigger", {}),
        "inputs": frame.get("inputs", {}),
        "steps": frame.get("steps", []),
        "outputs": frame.get("outputs", {}),
        "evidence": frame.get("evidence", []),
        "validations": frame.get("validations", []),
        "errors": frame.get("errors", []),
        "pending_actions": frame.get("pending_actions", []),
        "executed_actions": frame.get("executed_actions", []),
        "tool_calls": frame.get("tool_calls", []),
        "llm_calls": frame.get("llm_calls", []),
        "completion_gate_result": frame.get("completion_gate_result", {}),
        "failure_summary": build_failure_summary(frame),
        "approval_pack": build_approval_pack_view(frame),
        "artifact_paths": artifact_paths,
    }


def write_evidence_bundle(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict:
    try:
        bundle = build_evidence_bundle(frame_id, runtime_data_dir)
        reports_dir = Path(runtime_data_dir) / "runs" / frame_id / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = reports_dir / "evidence_bundle.json"
        write_json_atomic(bundle_path, bundle)
        return {"ok": True, "frame_id": frame_id, "bundle_path": str(bundle_path), "bundle": bundle, "error": ""}
    except Exception as exc:
        return {"ok": False, "frame_id": frame_id, "bundle_path": "", "bundle": {}, "error": str(exc)}


def _load_json_like(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        from .persistence import read_json

        data = read_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
