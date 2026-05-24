from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.config_profiles import load_config_profile


def test_default_config_profile_is_safe(monkeypatch) -> None:
    for key in [
        "TASKFRAME_PROFILE",
        "TASKFRAME_CONFIG_DIR",
        "TASKFRAME_RUNTIME_DIR",
        "TASKFRAME_LLM_PROVIDER",
        "TASKFRAME_OLLAMA_MODEL",
        "TASKFRAME_OLLAMA_BASE_URL",
        "TASKFRAME_ACCOUNTING_SHEET_CONFIG",
        "ENABLE_OPTIONAL_RPA_TOOLS",
    ]:
        monkeypatch.delenv(key, raising=False)
    profile = load_config_profile()
    assert profile.llm_provider == "fake"
    assert profile.google_enabled is False
    assert profile.rpa_enabled is False
    assert profile.live_execution_enabled is False


def test_env_overrides_profile(monkeypatch) -> None:
    monkeypatch.setenv("TASKFRAME_PROFILE", "local-llm")
    monkeypatch.setenv("TASKFRAME_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("TASKFRAME_RUNTIME_DIR", "temp_runtime")

    profile = load_config_profile()

    assert profile.name == "local-llm"
    assert profile.llm_provider == "ollama"
    assert profile.runtime_data_dir == Path("temp_runtime")


def test_config_paths_do_not_require_repo_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(tmp_path))

    profile = load_config_profile()

    assert profile.config_dir == tmp_path
    assert profile.google_credentials_path is not None
    assert profile.google_token_path is not None


def test_config_show_sanitizes_secrets(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "taskframe.default.json").write_text(
        json.dumps(
            {
                "profile": "default",
                "runtime_data_dir": "runtime_data",
                "llm": {"provider": "fake", "ollama_model": "granite3.3:8b", "ollama_base_url": "http://127.0.0.1:11434"},
                "google": {"enabled": False, "credentials_path": "", "token_path": ""},
                "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
                "live_execution": {"enabled": False},
                "token_value": "super-secret-token",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.taskframe_cli",
            "config",
            "show",
            "--config-dir",
            str(config_dir),
            "--profile",
            "default",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "super-secret-token" not in result.stdout
    assert "Profile: default" in result.stdout
    assert "Google enabled: false" in result.stdout


def test_config_examples_exist() -> None:
    example_dir = Path("config/examples")
    expected = [
        "taskframe.default.example.json",
        "taskframe.local-llm.example.json",
        "taskframe.google-live.example.json",
        "taskframe.rpa-local.example.json",
        "taskframe.service.example.json",
        "accounting_google_sheet.example.json",
    ]
    for name in expected:
        assert (example_dir / name).is_file()
