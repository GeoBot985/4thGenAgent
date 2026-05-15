from __future__ import annotations

import copy
import json
from pathlib import Path


DEMO_TOOLPACK = Path("tool_packs/demo_echo/toolpack.json")


def _load_descriptor() -> dict:
    return json.loads(DEMO_TOOLPACK.read_text(encoding="utf-8"))


def _write_descriptor(tmp_path: Path, descriptor: dict, name: str = "toolpack.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
    return path


def test_loads_valid_descriptor() -> None:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    descriptor = load_toolpack_descriptor(DEMO_TOOLPACK)
    result = validate_toolpack_descriptor(descriptor, base_path=DEMO_TOOLPACK.parent)
    assert result["ok"] is True
    assert result["toolpack_id"] == "demo_echo"
    assert result["tool_count"] == 3


def test_rejects_missing_toolpack_id(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    descriptor.pop("toolpack_id", None)
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("toolpack_id" in message.lower() for message in result["errors"])


def test_rejects_missing_tools(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    descriptor.pop("tools", None)
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("tools" in message.lower() for message in result["errors"])


def test_rejects_malformed_tool_key(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    descriptor["tools"][0]["tool"] = "badkey"
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("malformed tool key" in message.lower() for message in result["errors"])


def test_rejects_missing_module_function(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    descriptor["tools"][0]["module"] = "tool_packs.demo_echo.missing"
    descriptor["tools"][0]["function"] = "missing"
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("module import failed" in message.lower() or "function not found" in message.lower() for message in result["errors"])


def test_rejects_duplicate_tool_keys(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    descriptor["tools"].append(copy.deepcopy(descriptor["tools"][0]))
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("duplicate tool key" in message.lower() for message in result["errors"])


def test_rejects_side_effect_tool_without_requires_approval(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    tool = descriptor["tools"][0]
    tool["side_effect"] = True
    tool["requires_approval"] = False
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("must require approval" in message.lower() for message in result["errors"])


def test_rejects_live_side_effect_tool_without_explicit_safety_fields(tmp_path: Path) -> None:
    from src.toolpack_loader import validate_toolpack_descriptor

    descriptor = _load_descriptor()
    tool = descriptor["tools"][0]
    tool["side_effect"] = True
    tool["requires_approval"] = True
    tool["allow_live"] = True
    tool["allow_live_side_effect"] = True
    tool["live_guardrail"] = "blocked"
    result = validate_toolpack_descriptor(descriptor, base_path=tmp_path)
    assert result["ok"] is False
    assert any("live side effects" in message.lower() or "live guardrail" in message.lower() for message in result["errors"])


def test_validates_demo_echo_pack() -> None:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    descriptor = load_toolpack_descriptor(DEMO_TOOLPACK)
    result = validate_toolpack_descriptor(descriptor, base_path=DEMO_TOOLPACK.parent)
    assert result["ok"] is True
    assert result["toolpack_id"] == "demo_echo"
