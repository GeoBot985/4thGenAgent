from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def test_business_context_imports():
    module = importlib.import_module("runtime.business_context")
    assert module is not None


def test_no_legacy_business_context_module():
    for path in Path("runtime").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        assert path.name != ("mock_" "company.py")


def test_default_tool_registry_has_no_absa_rpa_tool():
    from runtime.tool_registry import TOOL_REGISTRY

    assert "messages/extract_absa_transactions" not in TOOL_REGISTRY


def test_default_tool_registry_import_does_not_require_playwright():
    sys.modules.pop("playwright", None)
    sys.modules.pop("playwright.async_api", None)
    sys.modules.pop("runtime.tool_registry", None)
    sys.modules.pop("optional_tools.rpa.google_messages_absa.messages_tools", None)
    module = importlib.import_module("runtime.tool_registry")
    assert "playwright.async_api" not in sys.modules
    assert "optional_tools.rpa.google_messages_absa.messages_tools" not in sys.modules
    assert "messages/extract_absa_transactions" not in module.TOOL_REGISTRY


def test_default_scenario_pack_excludes_absa():
    from src.operator_scenarios import list_scenarios

    scenario_ids = {item["id"] for item in list_scenarios()}
    assert not any("absa" in scenario_id.lower() for scenario_id in scenario_ids)


def test_release_verifier_wrapper_exists():
    assert Path("scripts/run_release_verification.py").is_file()


def test_optional_rpa_directory_exists_if_present():
    optional_dir = Path("optional_tools/rpa/google_messages_absa")
    assert not optional_dir.exists() or (optional_dir / "README.md").is_file()


def test_optional_rpa_documented_as_excluded():
    text = Path("README.md").read_text(encoding="utf-8").lower()
    assert "optional rpa tools" in text
    assert "excluded from the default portfolio path" in text
