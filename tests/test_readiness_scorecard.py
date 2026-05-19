from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import src.readiness_scorecard as readiness_scorecard
from tools.run_release_candidate_verification import _check_readiness_scorecard_gate


def test_readiness_scorecard_module_imports():
    assert hasattr(readiness_scorecard, "build_readiness_scorecard")


def test_scorecard_has_all_seven_areas(tmp_path: Path):
    result = readiness_scorecard.build_readiness_scorecard(runtime_data_dir=tmp_path, strict=True)
    assert len(result["areas"]) == 7
    assert set(result["areas"].keys()) == {
        "core_architecture",
        "manifest_runtime",
        "event_routing",
        "business_workflows",
        "tooling",
        "release_verification",
        "production_readiness",
    }


def test_area_scores_have_required_shape(tmp_path: Path):
    result = readiness_scorecard.build_readiness_scorecard(runtime_data_dir=tmp_path, strict=True)
    for area in result["areas"].values():
        assert {"area_id", "label", "score", "status", "threshold", "checks", "evidence", "gaps", "recommended_next_specs"} <= set(area)
        for check in area["checks"]:
            assert {"check_id", "label", "status", "score_weight", "earned", "message", "evidence", "source"} <= set(check)


def test_scorecard_fails_if_any_area_below_threshold(tmp_path: Path, monkeypatch):
    real_collect = readiness_scorecard._collect_area_results

    def fake_collect(runtime_root, *, threshold):
        areas = real_collect(runtime_root, threshold=threshold)
        areas["tooling"] = dict(areas["tooling"], score=80.0, status="WARN")
        return areas

    monkeypatch.setattr(readiness_scorecard, "_collect_area_results", fake_collect)
    result = readiness_scorecard.build_readiness_scorecard(runtime_data_dir=tmp_path, strict=True)
    assert result["ok"] is False
    assert "tooling" in result["blocking_areas"]


def test_scorecard_passes_when_all_areas_at_or_above_threshold(tmp_path: Path):
    result = readiness_scorecard.build_readiness_scorecard(runtime_data_dir=tmp_path, strict=True)
    assert result["ok"] is True
    assert result["status"] == "PASS"
    assert result["overall_score"] >= 90


def test_scorecard_writes_json_markdown_and_html(tmp_path: Path):
    result = readiness_scorecard.build_readiness_scorecard(runtime_data_dir=tmp_path, strict=True)
    report_paths = result["report_paths"]
    assert Path(report_paths["json_path"]).is_file()
    assert Path(report_paths["markdown_path"]).is_file()
    assert Path(report_paths["html_path"]).is_file()
    payload = json.loads(Path(report_paths["json_path"]).read_text(encoding="utf-8"))
    assert payload["status"] == result["status"]


def test_cli_readiness_command_exists(tmp_path: Path):
    command = [
        sys.executable,
        "-m",
        "src.taskframe_cli",
        "readiness",
        "--strict",
        "--json",
        "--runtime-data-dir",
        str(tmp_path),
    ]
    completed = subprocess.run(command, cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PASS"
    assert Path(payload["report_paths"]["json_path"]).is_file()


def test_release_verifier_includes_readiness_gate(tmp_path: Path):
    result = _check_readiness_scorecard_gate()
    assert result["status"] == "PASS", result
    assert result["name"] == "readiness_scorecard_gate"
    assert Path(result["json_path"]).is_file()
    assert Path(result["markdown_path"]).is_file()
    assert Path(result["html_path"]).is_file()


def test_operator_ui_mentions_readiness_scorecard():
    ui_source = Path("src/operator_ui.py").read_text(encoding="utf-8")
    assert "Generate 90% Readiness Scorecard" in ui_source
    assert "Open Readiness Report" in ui_source
    assert "Readiness Scorecard" in ui_source

