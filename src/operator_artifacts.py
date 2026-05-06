from __future__ import annotations

from pathlib import Path
from typing import Any


def build_artifact_state(frame_id: str | None, report_result: dict | None = None) -> dict:
    frame_id_value = _string(frame_id)
    report_result = report_result if isinstance(report_result, dict) else {}
    paths = {
        "report_markdown": _string(report_result.get("markdown_path")),
        "report_html": _string(report_result.get("html_path")),
        "evidence_bundle": _string(report_result.get("evidence_bundle_path")),
        "taskframe_json": _string(report_result.get("taskframe_json") or report_result.get("taskframe_path")),
        "output_dir": "",
    }

    if paths["report_markdown"]:
        paths["output_dir"] = str(Path(paths["report_markdown"]).resolve().parent)
    elif paths["report_html"]:
        paths["output_dir"] = str(Path(paths["report_html"]).resolve().parent)
    elif paths["evidence_bundle"]:
        paths["output_dir"] = str(Path(paths["evidence_bundle"]).resolve().parent)
    elif frame_id_value:
        try:
            paths["output_dir"] = str((Path("runtime_data") / "runs" / frame_id_value / "reports").resolve())
        except Exception:
            paths["output_dir"] = str(Path("runtime_data") / "runs" / frame_id_value / "reports")

    has_active_run = bool(frame_id_value)
    report_generated = bool(paths["report_markdown"] and paths["report_html"])
    evidence_generated = bool(paths["evidence_bundle"])
    messages: list[str] = []
    if not has_active_run:
        messages.append("No run selected. Run a demo first.")
    elif not report_generated and not evidence_generated:
        messages.append("No evidence pack has been generated for this run yet.")
    elif not artifact_paths_match_frame(frame_id_value, {"frame_id": frame_id_value, "paths": paths, "report_result": report_result}):
        messages.append("Artifacts do not belong to the current run.")

    return {
        "frame_id": frame_id_value,
        "report_frame_id": _string(report_result.get("frame_id")),
        "has_active_run": has_active_run,
        "report_generated": report_generated,
        "evidence_generated": evidence_generated,
        "paths": paths,
        "messages": messages,
        "report_result": dict(report_result),
    }


def artifact_paths_match_frame(frame_id: str, artifact_state: dict) -> bool:
    frame_id_value = _string(frame_id)
    artifact_state = artifact_state if isinstance(artifact_state, dict) else {}
    state_frame_id = _string(artifact_state.get("frame_id"))
    if not frame_id_value or not state_frame_id:
        return False
    if frame_id_value != state_frame_id:
        return False
    report_result = artifact_state.get("report_result", {})
    if isinstance(report_result, dict):
        report_frame_id = _string(report_result.get("frame_id"))
        if report_frame_id and report_frame_id != frame_id_value:
            return False
    state_report_frame_id = _string(artifact_state.get("report_frame_id"))
    if state_report_frame_id and state_report_frame_id != frame_id_value:
        return False
    return True


def get_openable_artifacts(artifact_state: dict) -> list[dict]:
    artifact_state = artifact_state if isinstance(artifact_state, dict) else {}
    frame_id = _string(artifact_state.get("frame_id"))
    paths = artifact_state.get("paths", {}) if isinstance(artifact_state.get("paths", {}), dict) else {}
    if not frame_id or not artifact_paths_match_frame(frame_id, artifact_state):
        return []

    items: list[dict] = []
    html_path = _string(paths.get("report_html"))
    if html_path and Path(html_path).is_file():
        items.append({"label": "Open HTML report", "path": html_path, "kind": "html_report"})
    evidence_path = _string(paths.get("evidence_bundle"))
    if evidence_path and Path(evidence_path).is_file():
        items.append({"label": "Open evidence bundle", "path": evidence_path, "kind": "evidence_bundle"})
    output_dir = _string(paths.get("output_dir"))
    if output_dir and Path(output_dir).is_dir():
        items.append({"label": "Open output folder", "path": output_dir, "kind": "folder"})
    return items


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
