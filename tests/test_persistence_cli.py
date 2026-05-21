from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str, env: dict[str, str] | None = None):
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False, env=env)


def test_persistence_cli_commands_return_structured_output(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime_data"
    env = dict(__import__("os").environ)
    env["TASKFRAME_PERSISTENCE_BACKEND"] = "sqlite"
    env["TASKFRAME_SQLITE_DB_PATH"] = str(runtime_root / "taskframe_runtime.db")
    for command in ("status", "init", "migrate-json", "verify"):
        result = _run("persistence", command, "--runtime-data-dir", str(runtime_root), "--json", env=env)
        assert result.returncode == 0, result.stderr + result.stdout
        payload = json.loads(result.stdout)
        assert "active_backend" in payload
        assert payload["active_backend"] == "sqlite"
