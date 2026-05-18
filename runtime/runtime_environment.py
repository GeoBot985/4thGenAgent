from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROFILE_PATH = ROOT / "config" / "runtime_profile.json"
ENVIRONMENTS = ("demo", "dev", "test", "release", "live")


def load_runtime_profile(path: str | Path = RUNTIME_PROFILE_PATH) -> dict[str, Any]:
    profile_path = Path(path)
    if not profile_path.is_file():
        return {
            "environment": "demo",
            "governance_enforced": True,
            "allow_unknown_toolpack_in_dev": False,
            "allow_high_risk_live_override": False,
        }
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "environment": str(data.get("environment", "demo") or "demo"),
        "governance_enforced": bool(data.get("governance_enforced", True)),
        "allow_unknown_toolpack_in_dev": bool(data.get("allow_unknown_toolpack_in_dev", False)),
        "allow_high_risk_live_override": bool(data.get("allow_high_risk_live_override", False)),
    }


def resolve_runtime_environment(explicit: str = "", *, profile_path: str | Path = RUNTIME_PROFILE_PATH) -> str:
    candidates = [
        explicit.strip(),
        os.getenv("TASKFRAME_ENV", "").strip(),
        str(load_runtime_profile(profile_path).get("environment", "")).strip(),
        "demo",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = candidate.lower()
        if normalized not in ENVIRONMENTS:
            raise ValueError(f"Invalid runtime environment: {candidate!r}")
        return normalized
    return "demo"

