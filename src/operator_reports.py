from __future__ import annotations

import os
import webbrowser
from pathlib import Path

from runtime.evidence_bundle import write_evidence_bundle
from runtime.run_report import generate_operator_run_report


def generate_report_for_frame(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict:
    if not isinstance(frame_id, str) or not frame_id.strip():
        return {"ok": False, "error": "frame_id is required", "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": ""}
    try:
        report = generate_operator_run_report(runtime_data_dir, frame_id, rebuild=True)
        bundle = write_evidence_bundle(frame_id, runtime_data_dir)
        report["evidence_bundle_path"] = bundle.get("bundle_path", "")
        report["bundle"] = bundle.get("bundle", {})
        return report
    except Exception as exc:
        return {"ok": False, "error": str(exc), "frame_id": frame_id, "markdown_path": "", "html_path": "", "evidence_bundle_path": ""}


def get_latest_report_paths(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict:
    reports_dir = Path(runtime_data_dir) / "runs" / frame_id / "reports"
    return {
        "markdown_path": str(reports_dir / "run_report.md"),
        "html_path": str(reports_dir / "run_report.html"),
        "evidence_bundle_path": str(reports_dir / "evidence_bundle.json"),
    }


def open_report_html(path: str) -> dict:
    try:
        webbrowser.open(Path(path).resolve().as_uri())
        return {"ok": True, "path": path, "error": ""}
    except Exception as exc:
        return {"ok": False, "path": path, "error": str(exc)}


def open_report_folder(path: str) -> dict:
    try:
        folder = Path(path).resolve().parent
        if hasattr(os, "startfile"):
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            webbrowser.open(folder.as_uri())
        return {"ok": True, "path": str(folder), "error": ""}
    except Exception as exc:
        return {"ok": False, "path": path, "error": str(exc)}
