from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import tools.run_bounded_validation as bounded


def test_quick_mode_builds_marker_filtered_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):  # type: ignore[no-untyped-def]
        calls.append(list(command))
        return CompletedProcess(command, 0, stdout="passed\n", stderr="")

    monkeypatch.setattr(bounded.subprocess, "run", fake_run)
    monkeypatch.setattr(bounded, "REPORT_DIR", tmp_path / "validation")
    monkeypatch.setattr(bounded, "JSON_REPORT_PATH", bounded.REPORT_DIR / "bounded_validation_report.json")
    monkeypatch.setattr(bounded, "MD_REPORT_PATH", bounded.REPORT_DIR / "bounded_validation_report.md")

    result = bounded.run_bounded_validation("quick")

    assert result["ok"] is True
    assert result["summary"]["command_count"] == 1
    assert result["groups"][0]["name"] == "quick"
    assert result["groups"][0]["status"] == "PASS"
    assert result["failed_groups"] == []
    assert "started_at" in result
    assert "ended_at" in result
    assert isinstance(result["duration_ms"], int)
    assert calls
    assert "-m" in calls[0]
    assert "unit and not slow and not live and not full_ci" in calls[0]
    assert bounded.JSON_REPORT_PATH.is_file()
    assert bounded.MD_REPORT_PATH.is_file()
    report = bounded.JSON_REPORT_PATH.read_text(encoding="utf-8")
    assert '"groups"' in report
    assert '"failed_groups"' in report


def test_local_mode_stops_on_first_failed_group(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):  # type: ignore[no-untyped-def]
        calls.append(list(command))
        if "test_production_backend_" in " ".join(command):
            return CompletedProcess(command, 1, stdout="", stderr="boom\n")
        return CompletedProcess(command, 0, stdout="passed\n", stderr="")

    monkeypatch.setattr(bounded.subprocess, "run", fake_run)
    monkeypatch.setattr(bounded, "REPORT_DIR", tmp_path / "validation")
    monkeypatch.setattr(bounded, "JSON_REPORT_PATH", bounded.REPORT_DIR / "bounded_validation_report.json")
    monkeypatch.setattr(bounded, "MD_REPORT_PATH", bounded.REPORT_DIR / "bounded_validation_report.md")

    result = bounded.run_bounded_validation("local")

    assert result["ok"] is False
    assert result["summary"]["failed_commands"] == 1
    assert result["failed_groups"] == ["backend"]
    assert any(item["name"] == "backend" for item in result["groups"])
    assert all(item["name"] != "manifest_core" for item in result["groups"][2:])
    assert len(calls) == 2


def test_ci_mode_includes_full_ci_group(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):  # type: ignore[no-untyped-def]
        calls.append(list(command))
        return CompletedProcess(command, 0, stdout="passed\n", stderr="")

    monkeypatch.setattr(bounded.subprocess, "run", fake_run)
    monkeypatch.setattr(bounded, "REPORT_DIR", tmp_path / "validation")
    monkeypatch.setattr(bounded, "JSON_REPORT_PATH", bounded.REPORT_DIR / "bounded_validation_report.json")
    monkeypatch.setattr(bounded, "MD_REPORT_PATH", bounded.REPORT_DIR / "bounded_validation_report.md")

    result = bounded.run_bounded_validation("ci")

    assert result["ok"] is True
    assert any(item["name"] == "full_ci" for item in result["groups"])
    assert any("full_ci and not live" in " ".join(command) for command in calls)
