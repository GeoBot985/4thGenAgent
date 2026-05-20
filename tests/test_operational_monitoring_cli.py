from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.taskframe_cli import build_parser

from tests.operational_monitoring_utils import seed_operational_monitoring_runtime


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_monitor_cli_commands_exist() -> None:
    parser = build_parser()
    for command in ("summary", "failed", "pending", "stuck", "blocked", "tools", "report"):
        args = parser.parse_args(["monitor", command, "--json"])
        assert args.command == "monitor"
        assert args.monitor_command == command


def test_monitor_summary_cli_returns_valid_json(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)
    completed = _run_cli(["monitor", "summary", "--runtime-data-dir", str(runtime_root), "--json"])

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["summary"]["total_indexed_runs"] >= 1
    assert "tool_health_status" in payload


def test_monitor_report_cli_writes_json_markdown_and_html(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)
    completed = _run_cli(["monitor", "report", "--runtime-data-dir", str(runtime_root), "--json"])

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["json_path"]
    assert payload["markdown_path"]
    assert payload["html_path"]
    assert Path(payload["json_path"]).is_file()
    assert Path(payload["markdown_path"]).is_file()
    assert Path(payload["html_path"]).is_file()
