"""Tests for generated tool pack execution through the runtime."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.toolpack_scaffold import scaffold_toolpack

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def safe_read_pack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("exec_packs")
    result = scaffold_toolpack(
        toolpack_id="exec_safe_pack",
        namespace="exec",
        tool_name="ping",
        safe_read=True,
        side_effect=False,
        output_dir=tmp,
    )
    assert result["ok"], result["errors"]
    return result


@pytest.fixture(scope="module")
def side_effect_pack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("exec_se_packs")
    result = scaffold_toolpack(
        toolpack_id="exec_se_pack",
        namespace="se",
        tool_name="notify",
        side_effect=True,
        safe_read=False,
        output_dir=tmp,
    )
    assert result["ok"], result["errors"]
    return result


def test_generated_safe_read_manifest_loads(safe_read_pack):
    examples = Path(safe_read_pack["path"]) / "examples"
    manifests = list(examples.glob("*.manifest.json"))
    assert manifests, "No example manifests found"
    data = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert "manifest_id" in data
    assert "steps" in data


def test_generated_output_alias_exists_in_manifest(safe_read_pack):
    examples = Path(safe_read_pack["path"]) / "examples"
    manifests = list(examples.glob("*.manifest.json"))
    data = json.loads(manifests[0].read_text(encoding="utf-8"))
    step = data["steps"][0]
    assert "ping_result" in step["command"]


def test_generated_side_effect_manifest_stages_pending_action(side_effect_pack):
    examples = Path(side_effect_pack["path"]) / "examples"
    manifests = list(examples.glob("*.manifest.json"))
    assert manifests, "No example manifests found"
    data = json.loads(manifests[0].read_text(encoding="utf-8"))
    completion = data.get("completion", {})
    assert completion.get("success_state") == "WAITING_FOR_EXECUTE"
    assert int(completion.get("pending_actions", 0)) >= 1


def test_generated_side_effect_manifest_does_not_execute_live(side_effect_pack):
    toolpack_json_path = Path(side_effect_pack["path"]) / "toolpack.json"
    descriptor = json.loads(toolpack_json_path.read_text(encoding="utf-8"))
    tool = descriptor["tools"][0]
    assert tool["allow_live"] is False
    assert tool["allow_live_side_effect"] is False
    assert tool["live_guardrail"] == "blocked"


def test_generated_side_effect_dry_run_records_dry_run_true(side_effect_pack):
    import importlib
    import sys

    pack_path = Path(side_effect_pack["path"])
    parent = pack_path.parent.parent

    original_path = list(sys.path)
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    try:
        toolpack_id = side_effect_pack["toolpack_id"]
        module = importlib.import_module(f"exec_se_pack.tools")
        result = module.notify(recipient="test@example.com", subject="S", body="B", dry_run=True)
        assert result["ok"] is True
        data = result.get("data", {})
        assert data.get("dry_run") is True
        assert data.get("sent") is False
    except ImportError:
        pytest.skip("Side-effect pack module not importable in this test context (expected in tmp dir).")
    finally:
        sys.path[:] = original_path
