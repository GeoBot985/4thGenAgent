from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.manifest_regression_gallery import run_gallery, write_gallery_report


GALLERY_DIR = Path("tests/fixtures/manifest_regression_gallery")
pytestmark = [pytest.mark.gallery, pytest.mark.slow]


@pytest.fixture(scope="module")
def gallery_result(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, Path]:
    runtime_dir = tmp_path_factory.mktemp("gallery_runtime")
    result = run_gallery(
        gallery_dir=GALLERY_DIR,
        runtime_data_dir=runtime_dir,
        strict=True,
        smoke=True,
        repair_guidance=True,
        autofix=True,
    )
    return result, runtime_dir


def test_gallery_report_command_writes_files(gallery_result: tuple[dict, Path]) -> None:
    result, tmp_path = gallery_result
    report = write_gallery_report(result, runtime_data_dir=tmp_path)
    assert report["ok"]
    json_path = Path(report["json_path"])
    md_path = Path(report["markdown_path"])
    assert json_path.is_file()
    assert md_path.is_file()


def test_gallery_report_json_shape(gallery_result: tuple[dict, Path]) -> None:
    result, tmp_path = gallery_result
    report = write_gallery_report(result, runtime_data_dir=tmp_path)
    payload = json.loads(Path(report["json_path"]).read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["total_fixtures"] == 42
    assert payload["passed"] == 42
    assert payload["categories"]["completion"]["total"] >= 5


def test_gallery_report_markdown_contains_summary(gallery_result: tuple[dict, Path]) -> None:
    result, tmp_path = gallery_result
    report = write_gallery_report(result, runtime_data_dir=tmp_path)
    text = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "# Manifest Regression Gallery Report" in text
    assert "## Summary" in text
    assert "## Failed Fixtures" in text
