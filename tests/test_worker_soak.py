from __future__ import annotations

import json
from pathlib import Path

from runtime.worker.worker_failure_fixtures import write_active_lock_fixture
from runtime.worker.worker_soak import run_worker_soak


def _write_service_config(root: Path, runtime_data_dir: Path) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "taskframe.service.json"
    config_path.write_text(
        json.dumps(
            {
                "profile": "service",
                "runtime_data_dir": str(runtime_data_dir),
                "llm": {"provider": "fake", "ollama_model": "granite3.3:8b", "ollama_base_url": "http://127.0.0.1:11434"},
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
    return config_dir


def test_worker_soak_success_writes_reports(tmp_path, monkeypatch):
    runtime_data_dir = tmp_path / "runtime_data"
    config_dir = _write_service_config(tmp_path, runtime_data_dir)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))

    result = run_worker_soak(
        profile_name="service",
        cycles=5,
        sleep_seconds=0,
        max_runtime_seconds=30,
        runtime_data_dir=runtime_data_dir,
        write_report=True,
    )

    assert result["ok"] is True
    assert result["profile"] == "service"
    assert result["cycles_requested"] == 5
    assert result["cycles_completed"] == 5
    assert result["cycles_failed"] == 0
    assert result["stale_lock_detected"] is False
    assert result["live_side_effects_performed"] is False
    assert Path(result["report_paths"]["json"]).is_file()
    assert Path(result["report_paths"]["markdown"]).is_file()
    assert result["classifications"]["OK"] + result["classifications"]["NO_WORK"] == 5


def test_worker_soak_respects_max_runtime_seconds(tmp_path, monkeypatch):
    runtime_data_dir = tmp_path / "runtime_data"
    config_dir = _write_service_config(tmp_path, runtime_data_dir)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))

    result = run_worker_soak(
        profile_name="service",
        cycles=50,
        sleep_seconds=0,
        max_runtime_seconds=0,
        runtime_data_dir=runtime_data_dir,
        write_report=True,
    )

    assert result["cycles_completed"] == 0
    assert result["ok"] is False
    assert any("max_runtime_seconds" in warning for warning in result["warnings"])


def test_worker_soak_fail_fast_stops_after_first_failure(tmp_path, monkeypatch):
    runtime_data_dir = tmp_path / "runtime_data"
    config_dir = _write_service_config(tmp_path, runtime_data_dir)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))
    write_active_lock_fixture(runtime_data_dir, worker_id="locked-worker")

    result = run_worker_soak(
        profile_name="service",
        cycles=5,
        sleep_seconds=0,
        max_runtime_seconds=30,
        runtime_data_dir=runtime_data_dir,
        fail_fast=True,
        write_report=True,
    )

    assert result["ok"] is False
    assert result["cycles_completed"] == 1
    assert result["cycles_failed"] == 1
    assert any(blocker["classification"] == "FAILED_STALE_LOCK" for blocker in result["blockers"])
    assert Path(result["report_paths"]["json"]).is_file()
