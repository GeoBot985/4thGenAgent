from __future__ import annotations

from pathlib import Path

from runtime.operational_monitoring import build_operational_monitoring_report

from tests.operational_monitoring_utils import seed_operational_monitoring_runtime


def test_monitoring_report_writes_json_markdown_and_html(tmp_path) -> None:
    runtime_root, _ = seed_operational_monitoring_runtime(tmp_path)

    report = build_operational_monitoring_report(runtime_root, profile_name="demo", rebuild=False)

    json_path = Path(report["json_path"])
    markdown_path = Path(report["markdown_path"])
    html_path = Path(report["html_path"])

    assert json_path.is_file()
    assert markdown_path.is_file()
    assert html_path.is_file()
    assert "Operational Health" in markdown_path.read_text(encoding="utf-8")
    assert "<html" in html_path.read_text(encoding="utf-8").lower()
