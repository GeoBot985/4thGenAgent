from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.persistence import save_taskframe
from runtime.runtime_store import ensure_runtime_store_layout

from tests.recovery_test_utils import seed_recovery_runtime, write_recovery_manifest


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.taskframe_cli", *args], capture_output=True, text=True, check=False)


def test_recover_cli_defaults_to_dry_run(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(
        manifest_dir,
        retry={"max_attempts": 3, "retry_on": ["external_dependency_unavailable", "timeout"], "do_not_retry_on": []},
    )
    frame = seed_recovery_runtime(runtime_root, manifest_path)
    frame.state = "FAILED_EXECUTION"
    frame.steps[0].status = "FAILED"
    frame.steps[0].last_error = "Connection timeout"
    frame.errors.append({"type": "tool", "message": "Connection timeout", "data": {}, "timestamp": frame.updated_at})
    save_taskframe(frame, runtime_root)

    completed = _run(
        "recover",
        "assess",
        frame.frame_id,
        "--runtime-data-dir",
        str(runtime_root),
        "--manifest-dir",
        str(manifest_dir),
        "--json",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["dry_run"] is True
    assert payload["recovery_status"] == "retryable"


def test_recover_retry_and_resume_commands_emit_json(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    manifest_dir = tmp_path / "manifests"
    manifest_path = write_recovery_manifest(
        manifest_dir,
        retry={"max_attempts": 3, "retry_on": ["external_dependency_unavailable", "timeout"], "do_not_retry_on": []},
    )
    retryable = seed_recovery_runtime(runtime_root, manifest_path)
    retryable.state = "FAILED_EXECUTION"
    retryable.steps[0].status = "FAILED"
    retryable.steps[0].last_error = "Connection timeout"
    retryable.errors.append({"type": "tool", "message": "Connection timeout", "data": {}, "timestamp": retryable.updated_at})
    save_taskframe(retryable, runtime_root)

    stale = seed_recovery_runtime(runtime_root, manifest_path)
    stale.state = "RUNNING"
    stale.updated_at = "2026-05-01T10:00:00Z"
    save_taskframe(stale, runtime_root)

    retry = _run(
        "recover",
        "retry-step",
        retryable.frame_id,
        "--step",
        retryable.steps[0].step_id,
        "--runtime-data-dir",
        str(runtime_root),
        "--manifest-dir",
        str(manifest_dir),
        "--json",
    )
    resume = _run(
        "recover",
        "resume",
        stale.frame_id,
        "--runtime-data-dir",
        str(runtime_root),
        "--manifest-dir",
        str(manifest_dir),
        "--json",
    )

    assert retry.returncode == 0
    assert resume.returncode == 0
    retry_payload = json.loads(retry.stdout)
    resume_payload = json.loads(resume.stdout)
    assert retry_payload["dry_run"] is True
    assert resume_payload["dry_run"] is True
    assert "taskframe recover retry-step" in retry_payload["command_suggestion"]
    assert "taskframe recover resume" in resume_payload["command_suggestion"]
