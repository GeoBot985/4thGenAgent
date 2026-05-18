from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_runtime_profile_command_outputs_environment() -> None:
    proc = _run("runtime", "profile", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["environment"] == "demo"
    assert payload["governance_enforced"] is True


def test_runtime_governance_check_allows_core_tool() -> None:
    proc = _run("runtime", "governance-check", "customer/read", "--env", "demo", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["decision"] == "ALLOW"


def test_runtime_governance_check_blocks_high_risk_demo() -> None:
    proc = _run("runtime", "governance-check", "messages/extract_absa_transactions", "--env", "demo", "--json")
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["decision"] == "BLOCK"


def test_runtime_governance_check_json_shape() -> None:
    proc = _run("runtime", "governance-check", "customer/read", "--env", "dev", "--json")
    payload = json.loads(proc.stdout)
    assert set(payload) >= {"ok", "decision", "reason", "tool", "environment", "policy", "errors", "warnings"}
