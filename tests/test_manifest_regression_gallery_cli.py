from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


GALLERY_DIR = Path("tests/fixtures/manifest_regression_gallery")
pytestmark = [pytest.mark.gallery, pytest.mark.slow]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_gallery_list_command_outputs_fixture_ids() -> None:
    result = _run_cli("manifests", "gallery", "list", "--gallery-dir", str(GALLERY_DIR))
    assert result.returncode == 0
    assert "completion_output_missing" in result.stdout
    assert "valid_read_only_basic" in result.stdout


def test_gallery_validate_command_passes() -> None:
    result = _run_cli(
        "manifests",
        "gallery",
        "validate",
        "--gallery-dir",
        str(GALLERY_DIR),
        "--no-smoke",
        "--no-autofix",
        "--no-repair-guidance",
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_gallery_run_command_json_shape() -> None:
    result = _run_cli(
        "manifests",
        "gallery",
        "run",
        "--fixture",
        "completion_output_missing",
        "--gallery-dir",
        str(GALLERY_DIR),
        "--json",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["fixture_id"] == "completion_output_missing"
    assert payload["matched_expectations"] is True


def test_gallery_report_command_writes_files() -> None:
    result = _run_cli("manifests", "gallery", "report", "--gallery-dir", str(GALLERY_DIR))
    assert result.returncode == 0
    assert "gallery_report.json" in result.stdout
    assert "gallery_report.md" in result.stdout


def test_gallery_invalid_fixture_id_returns_nonzero() -> None:
    result = _run_cli("manifests", "gallery", "run", "--fixture", "does_not_exist", "--gallery-dir", str(GALLERY_DIR))
    assert result.returncode != 0
    assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()
