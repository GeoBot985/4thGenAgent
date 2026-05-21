import os
import json
import pytest
from pathlib import Path
from runtime.artifact_retention import build_retention_plan

def test_inventory_classification(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    (root / "runs" / "frame_123" / "reports").mkdir(parents=True)
    (root / "runs" / "frame_123" / "summary.json").write_text('{"state": "COMPLETED"}')
    (root / "taskframes").mkdir()
    (root / "taskframes" / "frame_123.json").write_text('{}')
    (root / "manifest_health_reports").mkdir()
    (root / "tool_health_logs").mkdir()
    (root / "release_verification" / "logs").mkdir(parents=True)
    (root / "manifest_regression_gallery").mkdir()
    (root / "workbench").mkdir()
    (root / "tmp").mkdir()
    (root / "reports").mkdir()
    (root / "unknown_folder").mkdir()
    
    plan = build_retention_plan(str(root))
    assert plan["ok"] is True
    
    groups = {item["group"] for item in plan["items"]}
    assert "runs" in groups
    assert "taskframes" in groups
    assert "manifest_health" in groups
    assert "tool_health" in groups
    assert "release_logs" in groups
    assert "gallery_reports" in groups
    assert "workbench_preview" in groups
    assert "temporary" in groups
    assert "reports" in groups
    assert "unknown" in groups

def test_unknown_artifacts_protected(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    (root / "some_random_file.txt").write_text("hello")
    
    plan = build_retention_plan(str(root))
    assert plan["ok"] is True
    
    item = plan["items"][0]
    assert item["group"] == "unknown"
    assert item["protected"] is True
