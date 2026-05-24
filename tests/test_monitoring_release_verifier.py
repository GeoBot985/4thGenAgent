from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import tools.run_release_candidate_verification as verifier
from runtime.monitoring_snapshot import build_monitoring_snapshot
from runtime.runtime_store import ensure_runtime_store_layout


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_service_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    source = Path("config") / "examples" / "taskframe.service.example.json"
    (config_dir / "taskframe.service.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return config_dir


def test_release_verifier_operational_monitoring_snapshot_passes(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    config_examples = repo / "config" / "examples"
    config_examples.mkdir(parents=True, exist_ok=True)
    _write_doc(
        docs / "operational_monitoring.md",
        "monitoring snapshot alert candidates read-only not externally sent taskframe monitor snapshot taskframe monitor alerts",
    )
    _write_doc(
        docs / "alert_candidates.md",
        "alert candidates severity read-only not externally sent",
    )
    _write_doc(config_examples / "taskframe.service.example.json", Path("config/examples/taskframe.service.example.json").read_text(encoding="utf-8"))
    _write_doc(repo / "runtime" / "monitoring_snapshot.py", "pass")

    runtime_root = tmp_path / "runtime_data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime_store_layout(runtime_root)
    config_dir = _seed_service_config(tmp_path)
    monkeypatch.setenv("TASKFRAME_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("TASKFRAME_PROFILE", "service")

    snapshot_payload = build_monitoring_snapshot(runtime_root, profile_name="service", write_report=True)
    alerts_payload = {
        "ok": True,
        "profile": snapshot_payload.get("profile", "service"),
        "generated_at": snapshot_payload.get("generated_at", ""),
        "alert_candidates": list(snapshot_payload.get("alert_candidates", [])),
        "blockers": list(snapshot_payload.get("blockers", [])),
        "warnings": list(snapshot_payload.get("warnings", [])),
        "report_paths": {},
    }

    def _fake_run(command, **kwargs):
        text = " ".join(command)
        if "monitor snapshot" in text:
            return SimpleNamespace(returncode=0, stdout=json.dumps(snapshot_payload), stderr="")
        if "monitor alerts" in text:
            return SimpleNamespace(returncode=0, stdout=json.dumps(alerts_payload), stderr="")
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "ALERT_CANDIDATES_MD", repo / "docs" / "alert_candidates.md", raising=False)
    monkeypatch.setattr(verifier.subprocess, "run", _fake_run)

    result = verifier._check_operational_monitoring_snapshot()

    assert result["status"] == "PASS"
    assert result["missing"] == []


def test_release_verifier_operational_monitoring_snapshot_fails_when_module_missing(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    config_examples = repo / "config" / "examples"
    docs.mkdir(parents=True, exist_ok=True)
    config_examples.mkdir(parents=True, exist_ok=True)
    _write_doc(docs / "operational_monitoring.md", "monitoring snapshot alert candidates read-only not externally sent taskframe monitor snapshot taskframe monitor alerts")
    _write_doc(docs / "alert_candidates.md", "alert candidates severity read-only not externally sent")
    _write_doc(config_examples / "taskframe.service.example.json", Path("config/examples/taskframe.service.example.json").read_text(encoding="utf-8"))

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "ALERT_CANDIDATES_MD", repo / "docs" / "alert_candidates.md", raising=False)
    monkeypatch.setattr(verifier.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="{}", stderr=""))

    result = verifier._check_operational_monitoring_snapshot()

    assert result["status"] == "FAIL"
    assert any("runtime/monitoring_snapshot.py" in item or "monitoring_snapshot.py" in item for item in result["missing"])
