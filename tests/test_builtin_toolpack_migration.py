from __future__ import annotations

import json
from pathlib import Path


CORE_PACKS = [
    Path("tool_packs/core_business/toolpack.json"),
    Path("tool_packs/core_memory/toolpack.json"),
    Path("tool_packs/core_llm_micro/toolpack.json"),
    Path("tool_packs/core_reports/toolpack.json"),
]


def test_core_toolpack_descriptors_exist() -> None:
    for path in CORE_PACKS:
        assert path.is_file(), path


def test_core_toolpack_descriptors_validate() -> None:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    for path in CORE_PACKS:
        descriptor = load_toolpack_descriptor(path)
        result = validate_toolpack_descriptor(descriptor, base_path=path.parent)
        assert result["ok"] is True, path
        assert result["toolpack_id"] in {"core_business", "core_memory", "core_llm_micro", "core_reports"}
        assert result["tool_count"] == 1


def test_core_toolpack_wrappers_import_successfully() -> None:
    from tool_packs.core_business.tools import business_get_order_context
    from tool_packs.core_memory.tools import memory_set
    from tool_packs.core_llm_micro.tools import llm_extract_order_ref
    from tool_packs.core_reports.tools import report_generate

    assert callable(business_get_order_context)
    assert callable(memory_set)
    assert callable(llm_extract_order_ref)
    assert callable(report_generate)


def test_migrated_tools_have_required_safety_fields() -> None:
    from src.tool_registry_compat import build_compatibility_registry

    registry = build_compatibility_registry()
    for tool_key in ["business/get_order_context", "memory/set", "q/extract_order_ref", "report/generate"]:
        spec = registry[tool_key]
        assert "side_effect" in spec
        assert "requires_approval" in spec
        assert "allow_live" in spec
        assert "allow_live_side_effect" in spec
        assert "live_guardrail" in spec
        assert spec["allow_live_side_effect"] is False


def test_no_migrated_tool_allows_live_side_effects_by_default() -> None:
    from src.tool_registry_compat import build_compatibility_registry

    registry = build_compatibility_registry()
    assert all(not bool(spec.get("allow_live_side_effect", False)) for spec in registry.values())

