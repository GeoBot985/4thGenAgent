from __future__ import annotations

import json
from pathlib import Path

from src.manifest_health import (
    check_manifest_health,
    run_manifest_health_check,
    summarize_manifest_health,
    write_manifest_health_report,
)
from src.manifest_template_generator import build_manifest_from_template


def _write_manifest(path: Path, manifest: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _healthy_manifest(manifest_id: str = "health.healthy") -> dict:
    return build_manifest_from_template("manual_read_tool", manifest_id, "Healthy")


def _warning_manifest(manifest_id: str = "health.warning") -> dict:
    manifest = _healthy_manifest(manifest_id)
    manifest["inputs"] = ["unused_param"]
    manifest["sample_inputs"] = {"unused_param": "x"}
    return manifest


def _completion_mismatch_manifest(manifest_id: str = "health.repairable") -> dict:
    manifest = _healthy_manifest(manifest_id)
    manifest["completion"]["success_outputs"] = ["wrong_alias"]
    return manifest


def _unknown_tool_manifest(manifest_id: str = "health.unknown_tool") -> dict:
    manifest = _healthy_manifest(manifest_id)
    manifest["steps"] = [{"id": "bad_tool", "command": "[t:unknown/tool -> result]"}]
    return manifest


def test_check_manifest_health_valid_manifest_is_healthy(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "healthy.manifest.json", _healthy_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["health"] == "HEALTHY"
    assert result["validation"]["ok"] is True
    assert result["smoke"]["status"] == "PASS"


def test_check_manifest_health_warning_manifest_is_warning(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "warning.manifest.json", _warning_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["health"] == "WARNING"
    assert result["repair_guidance"]["top_findings"] == ["input_declared_but_not_used"]


def test_check_manifest_health_invalid_json_is_failed(tmp_path: Path) -> None:
    path = tmp_path / "broken.manifest.json"
    path.write_text("{broken", encoding="utf-8")
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["health"] == "FAILED"
    assert result["validation"]["ok"] is False


def test_check_manifest_health_unknown_tool_is_failed_or_manual_fix_required(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "unknown.manifest.json", _unknown_tool_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["health"] == "FAILED"
    assert result["manual_fix_required"] is True
    assert "unknown_tool" in result["repair_guidance"]["top_findings"]


def test_check_manifest_health_live_execution_is_critical(tmp_path: Path) -> None:
    manifest = _healthy_manifest("health.critical")
    manifest["live_execution"] = {"enabled": True, "requires_approval": True}
    path = _write_manifest(tmp_path / "critical.manifest.json", manifest)
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["health"] == "CRITICAL"
    assert result["next_action"] == "Disable live execution."


def test_check_manifest_health_completion_mismatch_is_repairable(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "repairable.manifest.json", _completion_mismatch_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["health"] == "FAILED"
    assert result["repairable"] is True
    assert result["autofix"]["low_risk_applyable"] >= 1


def test_run_manifest_health_check_summarizes_catalog(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    _write_manifest(manifest_dir / "healthy.manifest.json", _healthy_manifest("health.catalog.healthy"))
    _write_manifest(manifest_dir / "warning.manifest.json", _warning_manifest("health.catalog.warning"))
    (manifest_dir / "broken.manifest.json").write_text("{broken", encoding="utf-8")
    result = run_manifest_health_check(manifest_dir=manifest_dir, runtime_data_dir=tmp_path / "runtime")
    assert result["summary"]["total"] == 3
    assert result["summary"]["healthy"] == 1
    assert result["summary"]["warnings"] == 1
    assert result["summary"]["failed"] == 1
    assert result["status"] == "HAS_FAILURES"


def test_run_manifest_health_check_excludes_archive_by_default(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    _write_manifest(manifest_dir / "healthy.manifest.json", _healthy_manifest("health.active"))
    _write_manifest(manifest_dir / "archive" / "archived.manifest.json", _healthy_manifest("health.archived"))
    result = run_manifest_health_check(manifest_dir=manifest_dir, runtime_data_dir=tmp_path / "runtime")
    assert [item["manifest_id"] for item in result["manifests"]] == ["health.active"]


def test_run_manifest_health_check_does_not_include_broken_gallery(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    gallery_dir = tmp_path / "tests" / "fixtures" / "broken_manifests"
    _write_manifest(manifest_dir / "healthy.manifest.json", _healthy_manifest("health.active"))
    _write_manifest(gallery_dir / "gallery_bad.manifest.json", _unknown_tool_manifest("health.gallery"))
    result = run_manifest_health_check(manifest_dir=manifest_dir, runtime_data_dir=tmp_path / "runtime")
    assert [item["manifest_id"] for item in result["manifests"]] == ["health.active"]


def test_run_manifest_health_check_handles_empty_manifest_dir(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    result = run_manifest_health_check(manifest_dir=manifest_dir, runtime_data_dir=tmp_path / "runtime")
    assert result["summary"]["total"] == 0
    assert result["status"] == "HEALTHY"


def test_smoke_skipped_when_manifest_cannot_load(tmp_path: Path) -> None:
    path = tmp_path / "broken.manifest.json"
    path.write_text("{broken", encoding="utf-8")
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["smoke"]["status"] == "SKIPPED"
    assert "failed to load" in result["smoke"]["reason"]


def test_smoke_skipped_when_required_inputs_missing(tmp_path: Path) -> None:
    manifest = build_manifest_from_template("manual_llm_helper", "health.inputs", "Inputs", inputs=["message"])
    path = _write_manifest(tmp_path / "inputs.manifest.json", manifest)
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["smoke"]["status"] == "SKIPPED"
    assert result["health"] == "SMOKE_SKIPPED"
    assert "required sample inputs missing" in result["smoke"]["reason"]


def test_auto_fix_summary_counts_low_risk_applyable(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "repairable.manifest.json", _completion_mismatch_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["autofix"]["proposal_count"] >= 1
    assert result["autofix"]["supported_count"] >= 1
    assert result["autofix"]["low_risk_applyable"] >= 1


def test_manual_fix_required_when_no_supported_fix(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "unknown.manifest.json", _unknown_tool_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    assert result["manual_fix_required"] is True
    assert result["autofix"]["low_risk_applyable"] == 0


def test_write_manifest_health_report_creates_json_and_markdown(tmp_path: Path) -> None:
    item = check_manifest_health(
        _write_manifest(tmp_path / "healthy.manifest.json", _healthy_manifest()),
        runtime_data_dir=tmp_path / "runtime",
    )
    result = {
        "ok": True,
        "status": "HEALTHY",
        "generated_at": "2026-05-15T00:00:00Z",
        "manifest_dir": "manifests",
        "summary": summarize_manifest_health([item]),
        "manifests": [item],
    }
    report = write_manifest_health_report(result, runtime_data_dir=tmp_path / "runtime")
    assert report["ok"] is True
    assert Path(report["json_path"]).is_file()
    assert Path(report["markdown_path"]).is_file()


def test_markdown_report_contains_summary_table(tmp_path: Path) -> None:
    result = run_manifest_health_check(manifest_dir=tmp_path / "empty", runtime_data_dir=tmp_path / "runtime")
    report = write_manifest_health_report(result, runtime_data_dir=tmp_path / "runtime")
    text = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "# Manifest Health Report" in text
    assert "| Metric | Count |" in text
    assert "| Total manifests | 0 |" in text


def test_health_result_is_json_serializable(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "healthy.manifest.json", _healthy_manifest())
    result = check_manifest_health(path, runtime_data_dir=tmp_path / "runtime")
    json.dumps(result)
