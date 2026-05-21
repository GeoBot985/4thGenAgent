from __future__ import annotations

from pathlib import Path

import pytest

import tools.run_release_candidate_verification as verifier

pytestmark = pytest.mark.release


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_verifier_operational_monitoring_passes(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    _write_doc(
        docs / "operational_monitoring.md",
        "run health classifications taskframe monitor summary taskframe monitor failed taskframe monitor pending taskframe monitor stuck taskframe monitor blocked taskframe monitor tools taskframe monitor report stuck-run detection tool health does not do automatically controlled pilot readiness",
    )
    _write_doc(docs / "operator_ui.md", "Operational Health Run Health Summary Failed Runs Pending Approvals Stuck Runs Tool Health External Dependencies Runtime Store Status Recommended Actions")
    _write_doc(docs / "cli_reference.md", "taskframe monitor summary taskframe monitor failed taskframe monitor pending taskframe monitor stuck taskframe monitor blocked taskframe monitor tools taskframe monitor report")
    _write_doc(docs / "release_verification.md", "operational monitoring")

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "OPERATIONAL_MONITORING_MD", docs / "operational_monitoring.md", raising=False)
    monkeypatch.setattr(verifier, "OPERATOR_UI_MD", docs / "operator_ui.md", raising=False)
    monkeypatch.setattr(verifier, "OUTPUT_MD", docs / "release_verification.md", raising=False)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true}", "stderr": "", "stdout_tail": "{\"ok\": true}", "stderr_tail": "", "status": "PASS"})

    result = verifier._check_operational_monitoring()

    assert result["status"] == "PASS"
    assert result["missing"] == []


def test_release_verifier_operational_monitoring_fails_when_report_generation_breaks(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    _write_doc(docs / "operational_monitoring.md", "run health classifications taskframe monitor summary taskframe monitor failed taskframe monitor pending taskframe monitor stuck taskframe monitor blocked taskframe monitor tools taskframe monitor report")
    _write_doc(docs / "operator_ui.md", "Operational Health Run Health Summary Failed Runs Pending Approvals Stuck Runs Tool Health External Dependencies Runtime Store Status Recommended Actions")
    _write_doc(docs / "cli_reference.md", "taskframe monitor summary taskframe monitor failed taskframe monitor pending taskframe monitor stuck taskframe monitor blocked taskframe monitor tools taskframe monitor report")
    _write_doc(docs / "release_verification.md", "operational monitoring")

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "OPERATIONAL_MONITORING_MD", docs / "operational_monitoring.md", raising=False)
    monkeypatch.setattr(verifier, "OPERATOR_UI_MD", docs / "operator_ui.md", raising=False)
    monkeypatch.setattr(verifier, "OUTPUT_MD", docs / "release_verification.md", raising=False)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true}", "stderr": "", "stdout_tail": "{\"ok\": true}", "stderr_tail": "", "status": "PASS"})

    import runtime.operational_monitoring as monitoring

    monkeypatch.setattr(monitoring, "build_operational_monitoring_report", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = verifier._check_operational_monitoring()

    assert result["status"] == "FAIL"
    assert "monitoring_report_generation_failed" in result["missing"]
