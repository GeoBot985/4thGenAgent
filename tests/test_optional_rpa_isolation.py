from __future__ import annotations

import importlib
import subprocess
import sys


def test_default_tool_registry_does_not_import_playwright():
    sys.modules.pop("playwright", None)
    sys.modules.pop("playwright.async_api", None)

    importlib.import_module("runtime.tool_registry")

    assert "playwright" not in sys.modules
    assert "playwright.async_api" not in sys.modules


def test_cli_help_does_not_import_optional_rpa_modules():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "optional_tools.rpa.google_messages_absa.messages_tools" not in result.stdout
    assert "optional_tools.rpa.google_messages_absa.messages_tools" not in result.stderr


def test_default_demo_does_not_require_playwright():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "demo"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0
    assert "playwright" not in result.stderr.lower() or "not found" not in result.stderr.lower()


def test_optional_rpa_disabled_by_default():
    from runtime.tool_health import check_all_tool_health

    results = check_all_tool_health(include_optional=True, live_rpa=False)
    rpa_result = next((r for r in results if r.tool_id == "rpa_google_messages"), None)
    assert rpa_result is not None
    assert rpa_result.status in ("disabled_optional", "not_run", "skipped")


def test_rpa_capability_is_marked_excluded_from_default_release():
    from runtime.tool_capability_registry import get_tool_capability

    cap = get_tool_capability("rpa_google_messages")
    assert cap.excluded_from_default_release is True


def test_rpa_capability_is_optional_and_high_risk():
    from runtime.tool_capability_registry import get_tool_capability

    cap = get_tool_capability("rpa_google_messages")
    assert cap.core_or_optional == "optional"
    assert cap.side_effect_level == "high_risk"
    assert cap.rpa_live_probe_required is True


def test_playwright_not_imported_by_tool_registry_subprocess():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.modules.pop('playwright', None); "
                "sys.modules.pop('playwright.async_api', None); "
                "import runtime.tool_registry; "
                "assert 'playwright' not in sys.modules, 'playwright leaked'"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"playwright leaked: {result.stderr}"
