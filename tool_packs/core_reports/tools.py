from __future__ import annotations

from typing import Any

from src.operator_reports import generate_report_for_frame
from runtime.tool_result_contract import build_tool_evidence


def report_generate(frame_id: str, runtime_data_dir: str = "runtime_data") -> dict[str, Any]:
    result = generate_report_for_frame(frame_id, runtime_data_dir=runtime_data_dir)
    return {
        "ok": bool(result.get("ok", False)),
        "type": "report_result",
        "data": dict(result),
        "evidence": build_tool_evidence(
            tool="report/generate",
            mode="dry_run",
            source="migrated_toolpack",
            operation="prepare",
            input_refs=[f"frame_id:{frame_id}"],
            output_ref="report_result",
            extra={
                "frame_id": frame_id,
                "markdown_path": result.get("markdown_path", ""),
                "html_path": result.get("html_path", ""),
                "generated": bool(result.get("ok", False)),
            },
        ),
        "error": str(result.get("error", "")),
    }
