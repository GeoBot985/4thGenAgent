from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_service_config(root: Path, runtime_data_dir: Path) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "taskframe.service.json").write_text(
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


def test_worker_health_json_includes_hardening_payload(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    runtime_data_dir = tmp_path / "runtime_data"
    config_dir = _write_service_config(tmp_path, runtime_data_dir)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("TASKFRAME_PROFILE", "service")

    proc = subprocess.run(
        [sys.executable, "-m", "src.taskframe_cli", "worker", "health", "--runtime-data-dir", str(runtime_data_dir), "--json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "soak_ready" in payload
    assert "service_ready" in payload
    assert "hardening_checks" in payload
    assert "blockers" in payload
    assert "warnings" in payload
    assert isinstance(payload["hardening_checks"], dict)
