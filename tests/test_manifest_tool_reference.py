"""Drift tests: ensure manifest_tool_reference.md stays in sync with the registry."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOL_REFERENCE_PATH = PROJECT_ROOT / "docs" / "manifest_tool_reference.md"
COMMAND_REFERENCE_PATH = PROJECT_ROOT / "docs" / "manifest_command_reference.md"
MANUAL_PATH = PROJECT_ROOT / "docs" / "manifest_building_manual.md"
GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_manifest_tool_reference.py"

sys.path.insert(0, str(PROJECT_ROOT))
from runtime.tool_registry import TOOL_REGISTRY


def test_manifest_tool_reference_generator_runs():
    result = subprocess.run(
        [sys.executable, str(GENERATOR_PATH)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Generator failed:\n{result.stderr}"


def test_manifest_tool_reference_file_exists():
    assert TOOL_REFERENCE_PATH.exists(), (
        f"{TOOL_REFERENCE_PATH} does not exist. "
        "Run: python tools/generate_manifest_tool_reference.py"
    )


def test_manifest_tool_reference_mentions_registered_tools():
    assert TOOL_REFERENCE_PATH.exists(), "Run the generator first."
    content = TOOL_REFERENCE_PATH.read_text(encoding="utf-8")
    missing = [key for key in TOOL_REGISTRY if f"## {key}" not in content]
    assert not missing, f"These tools are missing from the reference: {missing}"


def test_manifest_tool_reference_marks_side_effect_tools():
    assert TOOL_REFERENCE_PATH.exists(), "Run the generator first."
    content = TOOL_REFERENCE_PATH.read_text(encoding="utf-8")
    side_effect_tools = [k for k, v in TOOL_REGISTRY.items() if v.get("side_effect")]
    for key in side_effect_tools:
        # Each side-effect tool's section must contain the safety note
        tool_section_start = content.find(f"## {key}")
        assert tool_section_start != -1, f"Tool {key} not found in reference."
        next_section = content.find("\n## ", tool_section_start + 1)
        section = content[tool_section_start:next_section] if next_section != -1 else content[tool_section_start:]
        assert "Safety note" in section, f"Side-effect tool {key} is missing safety note."


def test_manifest_command_reference_links_generated_tool_reference():
    assert COMMAND_REFERENCE_PATH.exists(), f"{COMMAND_REFERENCE_PATH} not found."
    content = COMMAND_REFERENCE_PATH.read_text(encoding="utf-8")
    assert "manifest_tool_reference" in content, (
        "manifest_command_reference.md must link to manifest_tool_reference.md"
    )


def test_manifest_manual_links_command_and_tool_reference():
    assert MANUAL_PATH.exists(), f"{MANUAL_PATH} not found."
    content = MANUAL_PATH.read_text(encoding="utf-8")
    assert "manifest_command_reference" in content, (
        "manifest_building_manual.md must link to manifest_command_reference.md"
    )
    assert "manifest_tool_reference" in content, (
        "manifest_building_manual.md must link to manifest_tool_reference.md"
    )
