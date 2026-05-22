"""Spec 139 — Event source adapter base protocol."""
from __future__ import annotations

from typing import Any, Protocol


class EventSourceAdapter(Protocol):
    adapter_id: str

    def health(
        self,
        config: dict[str, Any],
        runtime_data_dir: str = "runtime_data",
    ) -> dict[str, Any]: ...

    def poll(
        self,
        config: dict[str, Any],
        state: dict[str, Any],
        runtime_data_dir: str = "runtime_data",
    ) -> dict[str, Any]: ...

    def normalize(
        self,
        raw_record: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]: ...


def build_poll_result(
    source_id: str,
    adapter: str,
    mode: str,
    *,
    ok: bool = True,
    raw_count: int = 0,
    event_count: int = 0,
    events: list[dict[str, Any]] | None = None,
    cursor_update: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    error: str = "",
    error_category: str = "",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "source_id": str(source_id),
        "adapter": str(adapter),
        "mode": str(mode),
        "raw_count": int(raw_count),
        "event_count": int(event_count),
        "events": list(events or []),
        "cursor_update": dict(cursor_update or {}),
        "evidence": dict(evidence or {}),
        "error": str(error),
        "error_category": str(error_category),
        "warnings": list(warnings or []),
    }
