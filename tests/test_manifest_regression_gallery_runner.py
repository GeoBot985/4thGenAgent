from __future__ import annotations

from pathlib import Path

from src.manifest_regression_gallery import run_gallery, run_gallery_fixture


GALLERY_DIR = Path("tests/fixtures/manifest_regression_gallery")


def test_run_single_valid_fixture_passes_expectations() -> None:
    result = run_gallery_fixture("valid_read_only_basic", gallery_dir=GALLERY_DIR, runtime_data_dir="runtime_data")
    assert result["matched_expectations"]
    assert result["actual"]["strict_status"] == "PASS"
    assert result["actual"]["autofix"] == "NONE"


def test_run_single_bad_fixture_matches_expected_findings() -> None:
    result = run_gallery_fixture("completion_output_missing", gallery_dir=GALLERY_DIR, runtime_data_dir="runtime_data")
    assert result["matched_expectations"]
    assert "completion_output_missing" in result["actual"]["findings"]


def test_unknown_tool_fixture_matches_expected_finding() -> None:
    result = run_gallery_fixture("unknown_tool", gallery_dir=GALLERY_DIR, runtime_data_dir="runtime_data")
    assert result["matched_expectations"]
    assert "unknown_tool" in result["actual"]["findings"]


def test_completion_output_missing_fixture_matches_expected_finding() -> None:
    result = run_gallery_fixture("completion_output_missing", gallery_dir=GALLERY_DIR, runtime_data_dir="runtime_data")
    assert result["matched_expectations"]


def test_live_execution_fixture_matches_critical_finding() -> None:
    result = run_gallery_fixture("live_execution_enabled", gallery_dir=GALLERY_DIR, runtime_data_dir="runtime_data")
    assert result["matched_expectations"]
    assert result["actual"]["strict_status"] == "FAIL"
    assert result["actual"]["top_severity"] == "critical"


def test_malformed_json_fixture_returns_parse_error() -> None:
    result = run_gallery_fixture("malformed_json", gallery_dir=GALLERY_DIR, runtime_data_dir="runtime_data")
    assert result["matched_expectations"]
    assert "json_parse_error" in result["actual"]["findings"]


def test_gallery_runner_fails_on_expectation_mismatch() -> None:
    result = run_gallery(
        gallery_dir=GALLERY_DIR,
        runtime_data_dir="runtime_data",
        strict=True,
        smoke=True,
        repair_guidance=True,
        autofix=True,
    )
    assert result["ok"]
    assert result["status"] == "PASS"
    assert result["failed"] == 0


def test_gallery_runner_passes_full_gallery() -> None:
    result = run_gallery(
        gallery_dir=GALLERY_DIR,
        runtime_data_dir="runtime_data",
        strict=True,
        smoke=True,
        repair_guidance=True,
        autofix=True,
    )
    assert result["ok"]
    assert result["total_fixtures"] == 42
    assert result["passed"] == 42
