from __future__ import annotations

from pathlib import Path
from typing import Any

from tool_packs.core_llm_micro.tools import llm_extract_order_ref


def check_health(*, live: bool = False) -> dict[str, Any]:
    toolpack_path = Path(__file__).resolve().with_name("toolpack.json")
    result = llm_extract_order_ref("Please check order ORD-10042.")
    ok = bool(result.get("ok")) and str(result.get("data", {}).get("order_ref", "")).startswith("ORD-")
    return {
        "ok": ok,
        "toolpack_id": "core_llm_micro",
        "status": "ready" if ok else "failing",
        "severity": "info" if ok else "error",
        "message": "Deterministic LLM micro-tool is available." if ok else "Deterministic LLM micro-tool failed.",
        "tool_count": 1,
        "live_checked": bool(live),
        "health_supported": True,
        "details": {
            "toolpack_path": str(toolpack_path),
            "live": bool(live),
            "sample_result": result,
        },
        "errors": [] if ok else ["LLM micro-tool health probe failed."],
        "warnings": [],
    }
