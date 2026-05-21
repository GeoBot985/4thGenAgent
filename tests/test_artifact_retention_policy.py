import json
from pathlib import Path
from runtime.artifact_retention import build_retention_plan

def test_protects_failed_runs(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    run_dir = root / "runs" / "frame_fail"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"completion_status": "FAILED"}))
    
    plan = build_retention_plan(str(root), {"retain_recent_days": 0})
    item = next(i for i in plan["items"] if i["group"] == "runs")
    assert item["protected"] is True
    assert "Failed run" in item["reason"]

def test_protects_live_side_effect(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    run_dir = root / "runs" / "frame_live"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"live_side_effects_performed": True}))
    
    plan = build_retention_plan(str(root), {"retain_recent_days": 0})
    item = next(i for i in plan["items"] if i["group"] == "runs")
    assert item["protected"] is True
    assert "Live side effect" in item["reason"]

def test_deletes_old_temp(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    tmp_dir = root / "tmp"
    tmp_dir.mkdir()
    
    # We can't mock time easily without freezegun, so we set policy
    plan = build_retention_plan(str(root), {"delete_temp_after_days": -1})
    item = next(i for i in plan["items"] if i["group"] == "temporary")
    assert item["delete_candidate"] is True
    assert item["protected"] is False
