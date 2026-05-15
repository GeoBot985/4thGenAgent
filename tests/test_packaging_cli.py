from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import tomllib


def test_pyproject_exists() -> None:
    assert Path("pyproject.toml").is_file()


def test_taskframe_cli_imports() -> None:
    module = importlib.import_module("src.taskframe_cli")
    assert module is not None


def test_console_script_is_declared() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["taskframe"] == "src.taskframe_cli:main"


def test_default_dependencies_exclude_rpa_and_google() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = [str(item).lower() for item in data["project"].get("dependencies", [])]
    forbidden = {
        "playwright",
        "google-api-python-client",
        "google-auth-oauthlib",
        "google-auth",
        "google-auth-httplib2",
    }
    assert not forbidden.intersection(dependencies)


def test_optional_extras_exist() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]
    assert {"dev", "google", "rpa"}.issubset(extras.keys())


def test_cli_help_works() -> None:
    proc = subprocess.run([sys.executable, "-m", "src.taskframe_cli", "--help"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "taskframe" in proc.stdout.lower()
    assert "demo" in proc.stdout.lower()
    assert "tools" in proc.stdout.lower()


def test_cli_version_works() -> None:
    proc = subprocess.run([sys.executable, "-m", "src.taskframe_cli", "version"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "taskframe-runtime" in proc.stdout


def test_cli_manifest_health_works() -> None:
    proc = subprocess.run([sys.executable, "-m", "src.taskframe_cli", "manifest-health", "--no-smoke"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "Manifest health:" in proc.stdout


def test_cli_manifest_health_strict_works() -> None:
    proc = subprocess.run([sys.executable, "-m", "src.taskframe_cli", "manifest-health", "--strict", "--no-smoke"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "Mode: strict" in proc.stdout


def test_verify_command_exists() -> None:
    from src.taskframe_cli import build_parser

    help_text = build_parser().format_help()
    assert "verify" in help_text
    assert "config" in help_text
