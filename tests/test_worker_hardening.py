from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.worker.worker_engine import run_worker_once
from runtime.worker.worker_hardening import (
    build_worker_hardening_status,
    build_worker_recovery_recommendation,
    classify_worker_cycle_failure,
    detect_worker_anomalies,
    write_worker_hardening_report,
)


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


def test_worker_hardening_status_shape(tmp_path, monkeypatch):
    runtime_data_dir = tmp_path / "runtime_data"
    config_dir = _write_service_config(tmp_path, runtime_data_dir)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))

    run_worker_once(
        {
            "worker_id": "service-worker-1",
            "mode": "run_once",
            "features": {
                "recover_stale_queue": True,
                "run_scheduler_tick": True,
                "poll_event_sources": True,
                "process_queue": True,
            },
            "limits": {"max_sources_per_cycle": 10, "max_queue_items_per_cycle": 10},
            "safety": {"dry_run_only": True, "allow_live_side_effects": False},
            "frame_metadata": {"worker_identity": {"worker_id": "service-worker-1"}},
        },
        runtime_data_dir=runtime_data_dir,
    )

    status = build_worker_hardening_status(runtime_data_dir=runtime_data_dir, profile_name="service")
    assert status["profile"] == "service"
    assert "hardening_checks" in status
    assert "anomalies" in status
    assert "recommendations" in status
    assert "service_ready" in status
    assert "soak_ready" in status
    report_paths = write_worker_hardening_report(status, runtime_data_dir=runtime_data_dir)
    assert Path(report_paths["json"]).is_file()
    assert Path(report_paths["markdown"]).is_file()


@pytest.mark.parametrize(
    "cycle,expected",
    [
        ({"ok": True, "queue_items_processed": 0, "schedule_events_enqueued": 0, "event_sources_polled": 0, "source_events_enqueued": 0}, "NO_WORK"),
        ({"ok": True, "queue_items_processed": 2}, "OK"),
        ({"ok": False, "errors": ["queue_processing: transient network failure"]}, "FAILED_RECOVERABLE"),
        ({"ok": False, "errors": ["validation failed: business rule mismatch"]}, "FAILED_MANUAL_REVIEW"),
        ({"ok": False, "errors": ["policy blocked: approval required"]}, "FAILED_POLICY_BLOCKED"),
        ({"ok": False, "errors": ["worker_lock_conflict: worker lock held by another worker"]}, "FAILED_STALE_LOCK"),
        ({"ok": False, "errors": ["cycle timeout exceeded"]}, "FAILED_TIMEOUT"),
        ({"ok": False, "queue_items_processed": 1, "errors": ["event_source_poll_failed: partial"]}, "FAILED_RECOVERABLE"),
    ],
)
def test_cycle_classification_rules(cycle, expected):
    assert classify_worker_cycle_failure(cycle) == expected


def test_detect_worker_anomalies_and_recovery_recommendations():
    status = {
        "profile": "service",
        "worker_state": {},
        "current_lock": {"worker_id": "other-worker"},
        "stale_lock": {"stale": True, "lock": {"worker_id": "other-worker"}},
        "stop_request": {"reason": "manual_stop"},
        "queue_health": {"ok": False},
        "scheduler_health": {"ok": False},
        "event_source_health": {"ok": False},
        "runtime_profile_policy": {"ok": False},
        "worker_identity_present": False,
        "service_ready": False,
        "failed_cycles": [{"classification": "FAILED_RECOVERABLE"}],
        "average_cycle_duration_ms": 100,
        "longest_cycle_duration_ms": 8000,
        "last_heartbeat_age_seconds": 999,
    }

    anomalies = detect_worker_anomalies(status)
    ids = {item["id"] for item in anomalies}
    assert "stale_lock_detected" in ids
    assert "stop_request_pending" in ids
    assert "queue_unhealthy" in ids
    assert "scheduler_unhealthy" in ids
    assert "event_sources_unhealthy" in ids
    assert "runtime_profile_blocked" in ids
    assert "service_worker_identity_missing" in ids
    assert "service_preflight_failed" in ids

    status["anomalies"] = anomalies
    recommendations = build_worker_recovery_recommendation(status)
    assert any("stale lock" in item.lower() for item in recommendations)
    assert any("worker identity" in item.lower() for item in recommendations)
