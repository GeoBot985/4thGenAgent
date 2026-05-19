from __future__ import annotations

from pathlib import Path

from src.operator_scenarios import list_scenarios


def test_default_tool_registry_imports_without_optional_rpa():
    from runtime.tool_registry import TOOL_REGISTRY

    assert isinstance(TOOL_REGISTRY, dict)
    assert "messages/extract_absa_transactions" not in TOOL_REGISTRY


def test_default_scenario_pack_has_no_absa_or_personal_rpa():
    scenario_text = "\n".join(
        f"{scenario.get('id', '')} {scenario.get('label', '')} {scenario.get('description', '')}"
        for scenario in list_scenarios(include_test_only=False)
    ).lower()
    for marker in ("absa", "google_messages", "debit_orders", "personal_rpa"):
        assert marker not in scenario_text


def test_business_context_imports():
    import runtime.business_context

    assert runtime.business_context is not None


def test_no_runtime_mock_company_imports_remain():
    assert not Path("runtime/mock_company.py").exists()
    for path in Path(".").rglob("*.py"):
        if path.resolve() == Path(__file__).resolve():
            continue
        if any(part in {"optional_tools", "private_tools", ".git", ".venv", "venv", ".claude"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "runtime.mock_company" not in text


def test_release_verifier_script_exists():
    assert Path("scripts/run_release_verification.py").exists()


def test_golden_demo_script_exists():
    assert Path("scripts/run_golden_demo.py").exists()


def test_release_artifact_manifest_exists():
    assert Path("docs/release_artifacts.md").exists() or Path("docs/release_candidate_verification.md").exists()
