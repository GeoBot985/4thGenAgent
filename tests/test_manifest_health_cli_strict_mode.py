from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_manifest_health_cli_strict_no_smoke_passes_for_active_catalog() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "manifest-health", "--strict", "--no-smoke"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Mode: strict" in result.stdout


def test_manifest_health_report_mode_exits_zero_on_failure_fixture(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "broken.manifest.json").write_text("{not valid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.taskframe_cli",
            "manifest-health",
            "--manifest-dir",
            str(manifest_dir),
            "--no-smoke",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Mode: report" in result.stdout
    assert "HAS_FAILURES" in result.stdout or "FAILED" in result.stdout


def test_manifest_health_strict_mode_exits_nonzero_on_failure_fixture(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "broken.manifest.json").write_text("{not valid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.taskframe_cli",
            "manifest-health",
            "--manifest-dir",
            str(manifest_dir),
            "--strict",
            "--no-smoke",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Mode: strict" in result.stdout


def test_manifest_health_json_output_is_valid_json() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "manifest-health", "--json", "--no-smoke"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "status" in payload
    assert "summary" in payload
    assert "json_path" in payload
    assert "markdown_path" in payload


def test_manifest_health_help_mentions_strict() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "manifest-health", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--strict" in result.stdout
    assert "--json" in result.stdout
    assert "--manifest-dir" in result.stdout
