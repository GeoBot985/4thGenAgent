from __future__ import annotations

from pathlib import Path

from runtime.monitoring_snapshot import build_monitoring_snapshot, classify_monitoring_status
from runtime.runtime_store import ensure_runtime_store_layout


def _seed_service_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    source = Path("config") / "examples" / "taskframe.service.example.json"
    (config_dir / "taskframe.service.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return config_dir


def test_monitoring_snapshot_includes_required_sections(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime_store_layout(runtime_root)
    config_dir = _seed_service_config(tmp_path)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("TASKFRAME_PROFILE", "service")

    snapshot = build_monitoring_snapshot(runtime_root, profile_name="service")

    assert snapshot["ok"] is True
    assert snapshot["profile"] == "service"
    assert snapshot["generated_at"]
    assert snapshot["worker_identity"]["worker_id"] == "service-worker-1"
    assert snapshot["status"] in {"HEALTHY", "DEGRADED", "ATTENTION_REQUIRED", "BLOCKED"}
    assert snapshot["report_paths"] == {}

    required_sections = {
        "service_preflight",
        "worker",
        "worker_hardening",
        "worker_soak",
        "scheduler",
        "queue",
        "event_sources",
        "recovery",
        "tool_health",
        "manifest_health",
        "live_safety",
        "pending_actions",
        "runtime_profile",
        "storage",
    }
    assert required_sections.issubset(snapshot["sections"].keys())
    for section in snapshot["sections"].values():
        assert set(section.keys()) == {"ok", "status", "summary", "details", "warnings", "errors"}
        assert section["status"] in {"OK", "WARN", "FAIL", "SKIPPED"}


def test_monitoring_status_classification_rules() -> None:
    sections = {"worker": {"status": "OK", "summary": "", "details": {}, "warnings": [], "errors": []}}

    assert classify_monitoring_status(sections=sections, alert_candidates=[], blockers=[], warnings=[]) == "HEALTHY"
    assert classify_monitoring_status(
        sections=sections,
        alert_candidates=[{"severity": "warning"}],
        blockers=[],
        warnings=["tool degraded"],
    ) == "DEGRADED"
    assert classify_monitoring_status(
        sections=sections,
        alert_candidates=[{"severity": "error"}],
        blockers=[],
        warnings=[],
    ) == "ATTENTION_REQUIRED"
    assert classify_monitoring_status(
        sections=sections,
        alert_candidates=[{"severity": "critical"}],
        blockers=["service preflight failed"],
        warnings=[],
    ) == "BLOCKED"
