from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


DEMO_TOOLPACK = Path("tool_packs/demo_echo/toolpack.json")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_tools_lifecycle_command_exists() -> None:
    result = _run("tools", "lifecycle", str(DEMO_TOOLPACK), "--env", "dev", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "READY"


def test_tools_lifecycle_json_output_valid() -> None:
    result = _run("tools", "lifecycle", str(DEMO_TOOLPACK), "--env", "dev", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["toolpack_id"] == "demo_echo"
    assert payload["stages"]["discovered"] == "PASS"


def test_tools_lifecycle_text_output_mentions_status() -> None:
    result = _run("tools", "lifecycle", str(DEMO_TOOLPACK), "--env", "dev")
    assert result.returncode == 0
    assert "Tool pack lifecycle: demo_echo" in result.stdout
    assert "Status: READY" in result.stdout


def test_tools_lifecycle_invalid_pack_returns_nonzero(tmp_path: Path) -> None:
    bad_path = tmp_path / "missing" / "toolpack.json"
    result = _run("tools", "lifecycle", str(bad_path), "--env", "dev", "--json")
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "UNKNOWN"


def test_tools_lifecycle_write_report_creates_files(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime_data"
    result = _run("tools", "lifecycle", str(DEMO_TOOLPACK), "--env", "dev", "--runtime-data-dir", str(runtime_data_dir), "--write-report", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    json_path = Path(payload["json_path"])
    markdown_path = Path(payload["markdown_path"])
    assert json_path.is_file()
    assert markdown_path.is_file()
