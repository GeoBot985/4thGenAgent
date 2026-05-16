"""Tests for src/toolpack_contract_runner.py."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.toolpack_contract_runner import (
    build_tool_invocation_smoke_args,
    run_toolpack_contract_tests,
    validate_tool_result_shape,
)
from src.toolpack_scaffold import scaffold_toolpack


@pytest.fixture(scope="module")
def scaffolded_pack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("toolpacks")
    result = scaffold_toolpack(
        toolpack_id="contract_test_pack",
        namespace="ct",
        tool_name="check",
        safe_read=True,
        side_effect=False,
        output_dir=tmp,
    )
    assert result["ok"], result["errors"]
    return result


def test_valid_scaffolded_pack_passes_contract_runner(scaffolded_pack):
    toolpack_json = Path(scaffolded_pack["path"]) / "toolpack.json"
    result = run_toolpack_contract_tests(toolpack_json, include_manifest_smoke=True)
    assert result["ok"] is True, f"Errors: {result['errors']}"
    assert result["status"] == "PASS"


def test_missing_descriptor_fails():
    result = run_toolpack_contract_tests("/nonexistent/path/toolpack.json")
    assert result["ok"] is False
    assert result["errors"]


def test_invalid_function_import_fails(tmp_path):
    bad_descriptor = {
        "toolpack_id": "bad_import_pack",
        "name": "Bad Import",
        "version": "1.0.0",
        "runtime_contract_version": 1,
        "core_or_optional": "optional",
        "module_prefix": "does_not_exist",
        "health_supported": False,
        "health": {},
        "tools": [
            {
                "tool": "bad/run",
                "namespace": "bad",
                "action": "run",
                "module": "does_not_exist.tools",
                "function": "run",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": False,
                "allow_live_side_effect": False,
                "live_guardrail": "blocked",
                "output_type": "bad_run_result",
                "required_args": ["query"],
                "optional_args": [],
                "arg_types": {"query": "str"},
            }
        ],
    }
    toolpack_json = tmp_path / "toolpack.json"
    toolpack_json.write_text(json.dumps(bad_descriptor), encoding="utf-8")
    result = run_toolpack_contract_tests(toolpack_json)
    assert result["ok"] is False


def test_invalid_tool_result_shape_fails():
    shape = validate_tool_result_shape({"ok": True}, "some_type")
    assert shape["ok"] is False
    assert shape["errors"]


def test_valid_tool_result_shape_passes():
    result = {
        "ok": True,
        "type": "test_result",
        "data": {},
        "evidence": {},
        "error": "",
    }
    shape = validate_tool_result_shape(result, "test_result")
    assert shape["ok"] is True


def test_side_effect_tool_without_approval_fails(tmp_path):
    bad_descriptor = {
        "toolpack_id": "bad_safety_pack",
        "name": "Bad Safety",
        "version": "1.0.0",
        "runtime_contract_version": 1,
        "core_or_optional": "optional",
        "module_prefix": "tool_packs.demo_echo",
        "health_supported": False,
        "health": {},
        "tools": [
            {
                "tool": "echo/echo",
                "namespace": "echo",
                "action": "echo",
                "module": "tool_packs.demo_echo.tools",
                "function": "echo",
                "side_effect": True,
                "requires_approval": False,
                "allow_live": False,
                "allow_live_side_effect": False,
                "live_guardrail": "blocked",
                "output_type": "echo_result",
                "required_args": ["message"],
                "optional_args": [],
                "arg_types": {"message": "str"},
            }
        ],
    }
    toolpack_json = tmp_path / "toolpack.json"
    toolpack_json.write_text(json.dumps(bad_descriptor), encoding="utf-8")
    result = run_toolpack_contract_tests(toolpack_json)
    assert result["ok"] is False
    # Descriptor-level safety check: side_effect=True without requires_approval fails validation
    descriptor_check = next((c for c in result["checks"] if c["id"] == "descriptor_valid"), None)
    assert descriptor_check is not None
    assert descriptor_check["status"] == "FAIL"


def test_unknown_arg_type_fails():
    tool_spec = {
        "tool": "x/y",
        "required_args": ["data"],
        "optional_args": [],
        "arg_types": {"data": "SomeCustomType"},
    }
    smoke_args = build_tool_invocation_smoke_args(tool_spec)
    assert smoke_args["ok"] is False
    assert any("UNKNOWN_ARG_TYPE" in e for e in smoke_args["errors"])


def test_generated_smoke_args_match_arg_types():
    tool_spec = {
        "tool": "t/f",
        "required_args": ["name", "count"],
        "optional_args": [],
        "arg_types": {"name": "str", "count": "int"},
    }
    smoke_args = build_tool_invocation_smoke_args(tool_spec)
    assert smoke_args["ok"] is True
    assert smoke_args["kwargs"]["name"] == "TEST"
    assert smoke_args["kwargs"]["count"] == 1
