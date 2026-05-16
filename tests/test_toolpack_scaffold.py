"""Tests for src/toolpack_scaffold.py."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.toolpack_scaffold import scaffold_toolpack


@pytest.fixture
def tmp_out(tmp_path):
    return tmp_path / "tool_packs"


def _scaffold(tmp_out, toolpack_id="test_pack", **kwargs):
    return scaffold_toolpack(
        toolpack_id=toolpack_id,
        namespace=kwargs.pop("namespace", "test"),
        tool_name=kwargs.pop("tool_name", "echo"),
        output_dir=tmp_out,
        **kwargs,
    )


def test_scaffold_creates_expected_folder(tmp_out):
    result = _scaffold(tmp_out)
    assert result["ok"] is True
    assert Path(result["path"]).is_dir()


def test_scaffold_creates_toolpack_json(tmp_out):
    result = _scaffold(tmp_out)
    assert Path(result["toolpack_json"]).is_file() or (Path(tmp_out) / "test_pack" / "toolpack.json").is_file()
    pack_dir = Path(result["path"])
    assert (pack_dir / "toolpack.json").is_file()


def test_scaffold_creates_tools_py(tmp_out):
    result = _scaffold(tmp_out)
    pack_dir = Path(result["path"])
    assert (pack_dir / "tools.py").is_file()


def test_scaffold_creates_health_py(tmp_out):
    result = _scaffold(tmp_out)
    pack_dir = Path(result["path"])
    assert (pack_dir / "health.py").is_file()


def test_scaffold_creates_readme(tmp_out):
    result = _scaffold(tmp_out)
    pack_dir = Path(result["path"])
    assert (pack_dir / "README.md").is_file()


def test_scaffold_creates_tests_folder(tmp_out):
    result = _scaffold(tmp_out)
    pack_dir = Path(result["path"])
    assert (pack_dir / "tests").is_dir()
    assert (pack_dir / "tests" / "test_test_pack_contract.py").is_file()


def test_safe_read_scaffold_has_side_effect_false(tmp_out):
    result = _scaffold(tmp_out, safe_read=True, side_effect=False)
    pack_dir = Path(result["path"])
    descriptor = json.loads((pack_dir / "toolpack.json").read_text(encoding="utf-8"))
    tool = descriptor["tools"][0]
    assert tool["side_effect"] is False
    assert tool["requires_approval"] is False


def test_side_effect_scaffold_has_requires_approval_true(tmp_out):
    result = _scaffold(tmp_out, toolpack_id="test_se", namespace="se", tool_name="send", side_effect=True, safe_read=False)
    pack_dir = Path(result["path"])
    descriptor = json.loads((pack_dir / "toolpack.json").read_text(encoding="utf-8"))
    tool = descriptor["tools"][0]
    assert tool["side_effect"] is True
    assert tool["requires_approval"] is True


def test_side_effect_scaffold_has_allow_live_side_effect_false(tmp_out):
    result = _scaffold(tmp_out, toolpack_id="test_se2", namespace="se2", tool_name="send", side_effect=True, safe_read=False)
    pack_dir = Path(result["path"])
    descriptor = json.loads((pack_dir / "toolpack.json").read_text(encoding="utf-8"))
    tool = descriptor["tools"][0]
    assert tool["allow_live_side_effect"] is False


def test_invalid_pack_id_is_rejected(tmp_out):
    result = scaffold_toolpack(toolpack_id="Bad-Name", output_dir=tmp_out)
    assert result["ok"] is False
    assert result["errors"]


def test_existing_folder_not_overwritten_without_force(tmp_out):
    _scaffold(tmp_out)
    result = _scaffold(tmp_out)
    assert result["ok"] is False
    assert any("already exists" in e for e in result["errors"])


def test_existing_folder_overwritten_with_force(tmp_out):
    _scaffold(tmp_out)
    result = _scaffold(tmp_out, force=True)
    assert result["ok"] is True
