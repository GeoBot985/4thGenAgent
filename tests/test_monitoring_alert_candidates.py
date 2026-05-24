from __future__ import annotations

from runtime.monitoring_snapshot import build_alert_candidates


def _section(status: str, summary: str = "", details: dict | list | None = None, warnings: list[str] | None = None, errors: list[str] | None = None) -> dict:
    return {
        "ok": status == "OK",
        "status": status,
        "summary": summary,
        "details": details or {},
        "warnings": warnings or [],
        "errors": errors or [],
    }


def test_monitoring_alert_candidates_include_expected_severity_types() -> None:
    sections = {
        "service_preflight": _section("FAIL", "service preflight failed", details={"ok": False, "checks": [{"id": "optional_rpa_blocked", "status": "FAIL"}]}),
        "worker": _section("OK", "worker ready", details={"worker_id": "service-worker-1"}),
        "worker_hardening": _section(
            "FAIL",
            "worker hardening failed",
            details={
                "failed_cycles": [{"ok": False}, {"ok": False}],
                "stale_lock_detected": True,
                "last_heartbeat_age_seconds": 999,
                "current_lock": {"worker_id": "other-worker"},
            },
        ),
        "worker_soak": _section("SKIPPED", "no soak report", details={}),
        "scheduler": _section("FAIL", "scheduler unavailable", details={"ok": False}),
        "queue": _section("FAIL", "queue unavailable", details={"ok": False}),
        "event_sources": _section("FAIL", "event sources invalid", details={"ok": False, "errors": ["route mismatch"]}, errors=["route mismatch"]),
        "recovery": _section("WARN", "manual review needed", details={"ok": True}),
        "tool_health": _section("WARN", "tool health degraded", details={"ok": True, "status": "degraded", "results": [{"tool_id": "gmail"}]}),
        "manifest_health": _section("WARN", "manifest warnings", details={"ok": True, "status": "WARNING", "manifests": [{"path": "manifest.json"}]}),
        "live_safety": _section("WARN", "live safety blocked", details={"live_execution_env_enabled": False, "live_ready_action_count": 1}),
        "pending_actions": _section("WARN", "pending actions present", details={"pending_action_count": 1}),
        "runtime_profile": _section(
            "FAIL",
            "runtime profile unsafe",
            details={
                "runtime_profile": {"profile": "service", "allow_live_side_effects": True, "allow_live_reads": False, "blocked_tool_classes": ["write"]},
                "worker_identity": {},
            },
        ),
        "storage": _section("WARN", "storage warning", details={"ok": True, "issue_count": 1, "corrupted_path_count": 0, "runtime_data_dir": "runtime_data"}),
    }

    candidates = build_alert_candidates(
        sections=sections,
        runtime_profile={"profile": "service", "allow_live_side_effects": True, "allow_live_reads": False, "blocked_tool_classes": ["write"], "optional_rpa_enabled": True},
        service_preflight={"ok": False, "checks": [{"id": "optional_rpa_blocked", "status": "FAIL"}], "blockers": [{"message": "service preflight failed"}]},
        worker_status={"worker_id": "service-worker-1"},
        worker_hardening={"failed_cycles": [{"ok": False}, {"ok": False}], "stale_lock_detected": True, "last_heartbeat_age_seconds": 999, "current_lock": {"worker_id": "other-worker"}},
        worker_soak={},
        queue_status={"ok": False},
        scheduler_status={"ok": False},
        event_sources={"ok": False, "errors": ["route mismatch"]},
        recovery={"ok": True, "recovery_status": "skipped"},
        worker_lock={"locked": True, "lock": {"worker_id": "other-worker"}},
        tool_health={"ok": True, "status": "degraded", "results": [{"tool_id": "gmail"}]},
        manifest_health={"ok": True, "status": "WARNING", "manifests": [{"path": "manifest.json"}]},
        live_safety={"live_execution_env_enabled": False, "live_ready_action_count": 1},
        pending_actions={"pending_action_count": 1},
        storage={"ok": True, "issue_count": 1, "corrupted_path_count": 0, "runtime_data_dir": "runtime_data"},
        monitoring_summary={"latest_failed_runs": [{"frame_id": "frame_1"} for _ in range(11)]},
        heartbeat_stale_seconds=600,
        max_cycle_duration_ms=1000,
        threshold_failed_frames=10,
    )

    alert_ids = {candidate["alert_id"] for candidate in candidates}

    assert "service_preflight_failed" in alert_ids
    assert "live_side_effects_enabled" in alert_ids
    assert "optional_rpa_enabled" in alert_ids
    assert "stale_active_worker_lock" in alert_ids
    assert "queue_unavailable" in alert_ids
    assert "scheduler_unavailable" in alert_ids
    assert "event_source_contracts_invalid" in alert_ids
    assert "repeated_worker_failures" in alert_ids
    assert "failed_taskframes_manual_review" in alert_ids
    assert "tool_health_degraded" in alert_ids
    assert "manifest_health_warnings" in alert_ids
    assert "long_cycle_duration" in alert_ids or "no_recent_worker_heartbeat" in alert_ids
    assert "soak_test_not_run" in alert_ids
