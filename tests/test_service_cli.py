from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_service_config(config_dir: Path, runtime_data_dir: Path) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "taskframe.service.json"
    path.write_text(
        json.dumps(
            {
                "profile": "service",
                "runtime_data_dir": str(runtime_data_dir),
                "llm": {"provider": "fake"},
                "google": {"enabled": False, "credentials_path": "", "token_path": ""},
                "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
                "live_execution": {"enabled": False},
                "worker_identity": {
                    "worker_id": "service-worker-1",
                    "worker_role": "general",
                    "environment": "service",
                    "operator_id": "system",
                    "approval_authority": "system",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _write_empty_toolpack_config(path: Path) -> Path:
    path.write_text(json.dumps({"enabled_toolpacks": [], "disabled_toolpacks": [], "allow_optional_toolpacks": False}, indent=2), encoding="utf-8")
    return path


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def test_service_cli_preflight_emits_valid_json(tmp_path) -> None:
    repo = _repo_root()
    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(config_dir, runtime_data_dir)

    proc = _run(
        "service",
        "preflight",
        "--profile",
        "service",
        "--config-dir",
        str(config_dir),
        "--runtime-data-dir",
        str(runtime_data_dir),
        "--toolpack-config-path",
        str(toolpack_config_path),
        "--json",
        cwd=repo,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "service"
    assert payload["worker_identity"]["worker_id"] == "service-worker-1"
    assert Path(payload["report_paths"]["json"]).is_file()
    assert Path(payload["report_paths"]["markdown"]).is_file()


def test_service_cli_status_emits_valid_json(tmp_path) -> None:
    repo = _repo_root()
    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(config_dir, runtime_data_dir)

    proc = _run(
        "service",
        "status",
        "--profile",
        "service",
        "--config-dir",
        str(config_dir),
        "--runtime-data-dir",
        str(runtime_data_dir),
        "--toolpack-config-path",
        str(toolpack_config_path),
        "--json",
        cwd=repo,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "service"
    assert payload["live_read_status"] == "blocked"
    assert payload["live_side_effect_status"] == "blocked"
    assert isinstance(payload["enabled_toolpacks"], list)
    assert Path(payload["report_paths"]["json"]).is_file()


def test_service_cli_run_once_emits_valid_json(tmp_path) -> None:
    repo = _repo_root()
    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(config_dir, runtime_data_dir)

    proc = _run(
        "service",
        "run-once",
        "--profile",
        "service",
        "--config-dir",
        str(config_dir),
        "--runtime-data-dir",
        str(runtime_data_dir),
        "--toolpack-config-path",
        str(toolpack_config_path),
        "--json",
        cwd=repo,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "service"
    assert payload["worker_identity"]["worker_id"] == "service-worker-1"
    assert payload["worker_cycle"]["worker_identity"]["worker_id"] == "service-worker-1"
    assert Path(payload["service_cycle_record_path"]).is_file()


def test_service_cli_run_once_refuses_unsafe_config(tmp_path) -> None:
    repo = _repo_root()
    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "taskframe.service.json").write_text(
        json.dumps(
            {
                "profile": "service",
                "runtime_data_dir": str(runtime_data_dir),
                "llm": {"provider": "fake"},
                "google": {"enabled": False, "credentials_path": "", "token_path": ""},
                "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
                "live_execution": {"enabled": False},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    proc = _run(
        "service",
        "run-once",
        "--profile",
        "service",
        "--config-dir",
        str(config_dir),
        "--runtime-data-dir",
        str(runtime_data_dir),
        "--toolpack-config-path",
        str(toolpack_config_path),
        "--json",
        cwd=repo,
    )

    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert any(blocker["id"] == "config_worker_identity_present" for blocker in payload["preflight"]["blockers"])
