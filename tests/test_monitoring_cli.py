from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from runtime.runtime_store import ensure_runtime_store_layout


def _seed_service_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    source = Path("config") / "examples" / "taskframe.service.example.json"
    (config_dir / "taskframe.service.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return config_dir


def _run_cli(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False, env=env)


def test_monitor_cli_commands_exist() -> None:
    from src.taskframe_cli import build_parser

    parser = build_parser()
    for command in ("snapshot", "alerts", "summary", "failed", "pending", "stuck", "blocked", "tools", "report"):
        args = parser.parse_args(["monitor", command, "--json"])
        assert args.command == "monitor"
        assert args.monitor_command == command


def test_monitor_snapshot_and_alerts_cli_are_valid_json_and_read_only(tmp_path) -> None:
    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime_store_layout(runtime_root)
    config_dir = _seed_service_config(tmp_path)

    env = os.environ.copy()
    env["TASKFRAME_CONFIG_DIR"] = str(config_dir)
    env["TASKFRAME_PROFILE"] = "service"

    snapshot_proc = _run_cli(
        [
            "monitor",
            "snapshot",
            "--profile",
            "service",
            "--runtime-data-dir",
            str(runtime_root),
            "--write-report",
            "--json",
        ],
        env=env,
    )
    assert snapshot_proc.returncode == 0
    snapshot = json.loads(snapshot_proc.stdout)
    assert snapshot["ok"] is True
    assert snapshot["sections"]["service_preflight"]["status"] in {"OK", "WARN", "FAIL", "SKIPPED"}
    assert Path(snapshot["report_paths"]["snapshot_json"]).is_file()
    assert Path(snapshot["report_paths"]["alert_candidates_json"]).is_file()

    alerts_proc = _run_cli(
        [
            "monitor",
            "alerts",
            "--profile",
            "service",
            "--runtime-data-dir",
            str(runtime_root),
            "--json",
        ],
        env=env,
    )
    assert alerts_proc.returncode == 0
    alerts = json.loads(alerts_proc.stdout)
    assert alerts["ok"] is True
    assert isinstance(alerts["alert_candidates"], list)

    assert not (runtime_root / "worker" / "cycles.jsonl").exists()
