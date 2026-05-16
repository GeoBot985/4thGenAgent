from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.memory_store import MemoryStore


def check_health(*, live: bool = False) -> dict[str, Any]:
    toolpack_path = Path(__file__).resolve().with_name("toolpack.json")
    store = MemoryStore("runtime_data/memory_store.json")
    loaded = store.load()
    ok = isinstance(loaded, dict)
    return {
        "ok": ok,
        "toolpack_id": "core_memory",
        "status": "ready" if ok else "failing",
        "severity": "info" if ok else "error",
        "message": "Core memory store is available." if ok else "Core memory store is unavailable.",
        "tool_count": 1,
        "live_checked": bool(live),
        "health_supported": True,
        "details": {
            "toolpack_path": str(toolpack_path),
            "live": bool(live),
            "memory_store_path": str(store.path),
        },
        "errors": [] if ok else ["Memory store load failed."],
        "warnings": [],
    }
