"""Tests for taskframe tools scaffold/test/examples CLI commands."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, timeout: int = 60, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
        env=env,
    )


@pytest.fixture(scope="module")
def scaffolded_pack():
    # Scaffold inside the actual project tool_packs/ so module imports work without PYTHONPATH hacks.
    pack_id = "test_cli_scaffold_pack"
    result = _run(
        "tools", "scaffold", pack_id,
        "--namespace", "testcli",
        "--tool", "ping",
        "--safe-read",
        "--output-dir", "tool_packs",
        "--force",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    yield data
    # Cleanup: remove the generated pack directory after all tests complete
    import shutil
    pack_path = ROOT / "tool_packs" / pack_id
    if pack_path.is_dir():
        shutil.rmtree(pack_path, ignore_errors=True)


def test_scaffold_exits_zero(scaffolded_pack):
    assert scaffolded_pack["ok"] is True


def test_scaffold_generated_pack_validates(scaffolded_pack):
    toolpack_json = Path(scaffolded_pack["path"]) / "toolpack.json"
    result = _run("tools", "validate", str(toolpack_json))
    assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"


def test_scaffold_generated_pack_contract_passes(scaffolded_pack):
    toolpack_json = Path(scaffolded_pack["path"]) / "toolpack.json"
    result = _run("tools", "test", str(toolpack_json), "--json")
    assert result.returncode == 0, f"Contract test failed:\n{result.stdout}\n{result.stderr}"
    contract = json.loads(result.stdout)
    assert contract["ok"] is True


def test_scaffold_bad_name_fails():
    result = _run("tools", "scaffold", "Bad-Name", "--json")
    assert result.returncode != 0
    data = json.loads(result.stdout)
    assert data["ok"] is False


def test_tools_test_json_returns_valid_json(scaffolded_pack):
    toolpack_json = Path(scaffolded_pack["path"]) / "toolpack.json"
    result = _run("tools", "test", str(toolpack_json), "--json")
    assert result.returncode == 0
    contract = json.loads(result.stdout)
    assert "ok" in contract
    assert "checks" in contract
    assert "tool_checks" in contract
