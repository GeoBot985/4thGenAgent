from __future__ import annotations

import json
from pathlib import Path


def test_inventory_report_builds(tmp_path: Path) -> None:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=tmp_path / "runtime_data")
    assert report["report_type"] == "tool_inventory"
    assert report["ok"] is True
    assert report["summary"]["total_tools"] >= 1


def test_inventory_includes_migrated_tool_pack_tools(tmp_path: Path) -> None:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=tmp_path / "runtime_data")
    migrated = [item for item in report["tools"] if item["source"] == "migrated_toolpack"]
    assert {item["tool"] for item in migrated} >= {"business/get_order_context", "memory/set", "q/extract_order_ref", "report/generate"}


def test_inventory_includes_legacy_and_external_counts(tmp_path: Path) -> None:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=tmp_path / "runtime_data")
    summary = report["summary"]
    assert summary["legacy_fallback_tools"] > 0
    assert summary["external_enabled_tools"] >= 0


def test_inventory_reports_zero_live_side_effect_allowed_by_default(tmp_path: Path) -> None:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=tmp_path / "runtime_data")
    assert report["summary"]["live_side_effect_allowed"] == 0


def test_inventory_json_and_markdown_are_written(tmp_path: Path) -> None:
    from src.tool_inventory import build_tool_inventory_report

    report = build_tool_inventory_report(runtime_data_dir=tmp_path / "runtime_data")
    json_path = Path(report["json_path"])
    markdown_path = Path(report["markdown_path"])
    docs_path = Path(report["docs_path"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert docs_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report_type"] == "tool_inventory"

