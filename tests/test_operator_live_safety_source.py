from __future__ import annotations

from pathlib import Path


SOURCE = Path("src/operator_ui.py").read_text(encoding="utf-8")


def test_live_safety_panel_label_exists():
    assert "Live Safety Panel" in SOURCE


def test_live_preflight_handler_exists():
    assert "_run_live_preflight" in SOURCE
    assert "Run live preflight" in SOURCE


def test_typed_confirmation_variable_exists():
    assert "live_execution_confirmation_var" in SOURCE
    assert "Typed confirmation:" in SOURCE


def test_live_execute_button_is_disabled_by_default():
    assert 'text="Execute live"' in SOURCE
    assert 'state="disabled"' in SOURCE


def test_blocker_rendering_exists():
    assert "Blockers:" in SOURCE
    assert "live_guardrail_failed" in SOURCE or "LIVE EXECUTION BLOCKED" in SOURCE


def test_dry_run_command_display_exists():
    assert "Copy dry-run CLI command" in SOURCE
    assert "taskframe execute-approved --frame-id" in SOURCE
