from __future__ import annotations

from typing import Any

from src.operator_reports import generate_report_for_frame


def report_generate(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict[str, Any]:
    result = generate_report_for_frame(frame_id, runtime_data_dir=runtime_data_dir)
    return {
        "ok": bool(result.get("ok", False)),
        "type": "report_result",
        "data": dict(result),
        "evidence": [
            {
                "kind": "report_generation",
                "frame_id": frame_id,
                "markdown_path": result.get("markdown_path", ""),
                "html_path": result.get("html_path", ""),
            }
        ] if result.get("ok") else [],
        "error": str(result.get("error", "")),
    }
