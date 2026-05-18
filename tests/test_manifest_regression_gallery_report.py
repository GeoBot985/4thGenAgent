from __future__ import annotations

import json
from pathlib import Path

from src.manifest_regression_gallery import run_gallery, write_gallery_report


GALLERY_DIR = Path("tests/fixtures/manifest_regression_gallery")


def test_gallery_report_command_writes_files(tmp_path: Path) -> None:
    result = run_gallery(gallery_dir=GALLERY_DIR, runtime_data_dir=tmp_path, strict=True, smoke=True, repair_guidance=True, autofix=True)
    report = write_gallery_report(result, runtime_data_dir=tmp_path)
    assert report["ok"]
    json_path = Path(report["json_path"])
    md_path = Path(report["markdown_path"])
    assert json_path.is_file()
    assert md_path.is_file()


def test_gallery_report_json_shape(tmp_path: Path) -> None:
    result = run_gallery(gallery_dir=GALLERY_DIR, runtime_data_dir=tmp_path, strict=True, smoke=True, repair_guidance=True, autofix=True)
    report = write_gallery_report(result, runtime_data_dir=tmp_path)
    payload = json.loads(Path(report["json_path"]).read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["total_fixtures"] == 42
    assert payload["passed"] == 42
    assert payload["categories"]["completion"]["total"] >= 5


def test_gallery_report_markdown_contains_summary(tmp_path: Path) -> None:
    result = run_gallery(gallery_dir=GALLERY_DIR, runtime_data_dir=tmp_path, strict=True, smoke=True, repair_guidance=True, autofix=True)
    report = write_gallery_report(result, runtime_data_dir=tmp_path)
    text = Path(report["markdown_path"]).read_text(encoding="utf-8")
    assert "# Manifest Regression Gallery Report" in text
    assert "## Summary" in text
    assert "## Failed Fixtures" in text
