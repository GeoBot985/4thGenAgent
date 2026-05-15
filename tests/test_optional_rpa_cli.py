from __future__ import annotations

import subprocess
import sys


def test_rpa_status_command_works_without_playwright():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Optional RPA tools" in result.stdout


def test_rpa_status_shows_disabled():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "disabled" in result.stdout.lower()


def test_rpa_health_default_does_not_run_live_probe():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "health"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "not run" in result.stdout.lower() or "disabled" in result.stdout.lower()


def test_rpa_live_probe_requires_enable_flag():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "health", "--live-probe"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "--enable-rpa" in combined


def test_rpa_docs_command_works():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "docs"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "docs/optional_rpa.md" in result.stdout


def test_rpa_health_with_enable_rpa_exits_zero_or_one():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "health", "--enable-rpa"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode in (0, 1)
    assert "Optional RPA health" in result.stdout


def test_rpa_status_shows_playwright_status():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "playwright installed" in result.stdout.lower()


def test_rpa_status_shows_live_probe_not_run():
    result = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "rpa", "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "live probe: not run" in result.stdout.lower()
