from pathlib import Path
from runtime.artifact_retention import build_retention_plan, execute_retention_cleanup

def test_dry_run_does_not_delete(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    tmp_dir = root / "tmp"
    tmp_dir.mkdir()
    
    plan = build_retention_plan(str(root), {"delete_temp_after_days": -1})
    res = execute_retention_cleanup(plan, confirm=False)
    
    assert res["ok"] is False
    assert tmp_dir.exists()

def test_cleanup_with_confirm_deletes(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    tmp_dir = root / "tmp"
    tmp_dir.mkdir()
    
    plan = build_retention_plan(str(root), {"delete_temp_after_days": -1})
    res = execute_retention_cleanup(plan, confirm=True)
    
    assert res["ok"] is True
    assert res["deleted_count"] == 1
    assert not tmp_dir.exists()

def test_cleanup_rejects_outside_paths(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    # malicious path
    plan = {
        "ok": True,
        "runtime_data_dir": str(root),
        "items": [
            {
                "path": str(tmp_path / "malicious"),
                "group": "runs",
                "protected": False,
                "delete_candidate": True,
                "size_bytes": 0
            }
        ]
    }
    
    res = execute_retention_cleanup(plan, confirm=True)
    assert res["ok"] is True
    assert res["skipped_count"] == 1
    assert "escapes runtime_data" in res["errors"][0]
