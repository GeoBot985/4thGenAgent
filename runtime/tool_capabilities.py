from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolCapability:
    tool_id: str
    display_name: str
    category: str
    description: str
    core_or_optional: str
    side_effect_level: str
    auth_required: bool
    auth_type: str | None
    setup_available: bool
    setup_action: str | None
    rpa_live_probe_required: bool
    excluded_from_default_release: bool = False
    source: str = "builtin"
    path: str = ""
    enabled: bool = True
    registered: bool = True
    valid: bool = True
    toolpack_id: str = ""
    tool_count: int = 0
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ToolHealthResult:
    tool_id: str
    ok: bool
    status: str
    severity: str
    message: str
    can_auto_resolve: bool
    recommended_action: str | None
    checked_at: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolHealthResult":
        return cls(
            tool_id=str(payload.get("tool_id", "")),
            ok=bool(payload.get("ok", False)),
            status=str(payload.get("status", "unknown")),
            severity=str(payload.get("severity", "warning")),
            message=str(payload.get("message", "")),
            can_auto_resolve=bool(payload.get("can_auto_resolve", False)),
            recommended_action=payload.get("recommended_action"),
            checked_at=str(payload.get("checked_at", "")),
            details=dict(payload.get("details", {}) or {}),
        )
