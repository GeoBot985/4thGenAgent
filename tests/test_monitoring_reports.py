from __future__ import annotations

from pathlib import Path

from runtime.monitoring_snapshot import build_monitoring_snapshot
from runtime.runtime_store import ensure_runtime_store_layout


def _seed_service_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    source = Path("config") / "examples" / "taskframe.service.example.json"
    (config_dir / "taskframe.service.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return config_dir


def test_monitoring_reports_are_written(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime_store_layout(runtime_root)
    config_dir = _seed_service_config(tmp_path)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("TASKFRAME_PROFILE", "service")

    snapshot = build_monitoring_snapshot(runtime_root, profile_name="service", write_report=True)
    report_paths = snapshot["report_paths"]

    for key in ("snapshot_json", "snapshot_markdown", "alert_candidates_json", "alert_candidates_markdown"):
        path = Path(report_paths[key])
        assert path.is_file()

    markdown = Path(report_paths["snapshot_markdown"]).read_text(encoding="utf-8")
    assert "Operational Monitoring Snapshot" in markdown
    assert "Alert Candidates" in markdown
    assert "Safety Statement" in markdown

    alert_markdown = Path(report_paths["alert_candidates_markdown"]).read_text(encoding="utf-8")
    assert "Alert Candidates" in alert_markdown
    assert "Severity" in alert_markdown
