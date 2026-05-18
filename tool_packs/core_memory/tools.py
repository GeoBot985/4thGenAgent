from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.memory_store import MemoryStore
from runtime.tool_result_contract import build_tool_evidence


def memory_set(key: str, value: str, runtime_root: str = "runtime_data") -> dict[str, Any]:
    store = MemoryStore(Path(runtime_root) / "memory_store.json")
    stored = store.set(key, value, metadata={"source": "toolpack", "toolpack_id": "core_memory"})
    payload = {
        "key": key,
        "value": value,
        "stored": True,
    }
    payload.update({k: v for k, v in stored.metadata.items() if k not in payload})
    return {
        "ok": True,
        "type": "memory_set_result",
        "data": payload,
        "evidence": build_tool_evidence(
            tool="memory/set",
            mode="dry_run",
            source="migrated_toolpack",
            operation="side_effect",
            input_refs=[f"key:{key}"],
            output_ref="memory_set_result",
            extra={
                "key": key,
                "runtime_root": runtime_root,
                "stored": True,
            },
        ),
        "error": "",
    }
