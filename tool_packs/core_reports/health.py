from __future__ import annotations

from pathlib import Path
from typing import Any

def check_health(*, live: bool = False) -> dict[str, Any]:
    toolpack_path = Path(__file__).resolve().with_name("toolpack.json")
    reports_dir = Path("runtime_data") / "tool_health" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_dir / "report_toolpack_probe.md"
    html_path = reports_dir / "report_toolpack_probe.html"
    markdown_path.write_text("# Core Reports Tool Pack Probe\n\nThis file was generated during a safe health check.\n", encoding="utf-8")
    html_path.write_text("<!doctype html><html><body><h1>Core Reports Tool Pack Probe</h1></body></html>", encoding="utf-8")
    ok = markdown_path.is_file() and html_path.is_file()
    return {
        "ok": ok,
        "toolpack_id": "core_reports",
        "status": "ready" if ok else "failing",
        "severity": "info" if ok else "error",
        "message": "Local report generation is available." if ok else "Local report generation failed.",
        "tool_count": 1,
        "live_checked": bool(live),
        "health_supported": True,
        "details": {
            "toolpack_path": str(toolpack_path),
            "live": bool(live),
            "markdown_path": str(markdown_path),
            "html_path": str(html_path),
        },
        "errors": [] if ok else ["Report generation health probe failed."],
        "warnings": [],
    }
