from __future__ import annotations

import inspect
import subprocess
import sys


def test_adding_a_tool_pack_does_not_add_scenario_to_default_demo() -> None:
    from src.operator_scenarios import list_scenarios

    scenario_ids = {str(item.get("id", "")) for item in list_scenarios(include_test_only=False)}
    assert "demo_echo" not in scenario_ids


def test_optional_rpa_remains_excluded_from_default_registry() -> None:
    from runtime.tool_registry import build_tool_registry

    registry = build_tool_registry(include_external=False)
    assert "messages/extract_absa_transactions" not in registry
    assert "rpa_google_messages" not in registry


def test_playwright_is_not_imported_during_default_registry_import() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, runtime.tool_registry; print('playwright' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "False"


def test_release_verifier_checks_tool_pack_contract_docs() -> None:
    import tools.run_release_candidate_verification as verifier

    source = inspect.getsource(verifier)
    assert "_check_toolpack_contract()" in source
    assert "_check_toolpack_loader()" in source
    assert "docs/toolpack_contract.md" in source
    assert "config/enabled_toolpacks.json" in source
