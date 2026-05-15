from __future__ import annotations

from pathlib import Path
from typing import Any


def check_health(*, live: bool = False) -> dict[str, Any]:
    toolpack_path = Path(__file__).resolve().with_name("toolpack.json")
    return {
        "ok": True,
        "toolpack_id": "demo_echo",
        "status": "ready",
        "severity": "info",
        "message": "Demo Echo tool pack is available and safe.",
        "tool_count": 3,
        "live_checked": bool(live),
        "health_supported": True,
        "details": {
            "toolpack_path": str(toolpack_path),
            "live": bool(live),
        },
        "errors": [],
        "warnings": [],
    }
