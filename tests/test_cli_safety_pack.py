"""Tests for taskframe safety-pack CLI command."""
from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_safety_pack_no_demo_exits_zero():
    result = _run("safety-pack", "--no-demo")
    assert result.returncode == 0, f"Expected 0, got {result.returncode}\n{result.stdout}\n{result.stderr}"


def test_safety_pack_no_demo_prints_pass():
    result = _run("safety-pack", "--no-demo")
    assert "PASS" in result.stdout, f"Expected PASS in output:\n{result.stdout}"


def test_safety_pack_json_flag_produces_valid_json():
    result = _run("safety-pack", "--no-demo", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, dict)
    assert "ok" in data
    assert "claims" in data


def test_safety_pack_json_ok_is_true_in_default_state():
    result = _run("safety-pack", "--no-demo", "--json")
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_safety_pack_json_has_nine_claims():
    result = _run("safety-pack", "--no-demo", "--json")
    data = json.loads(result.stdout)
    assert len(data["claims"]) == 9
