from pathlib import Path
from runtime.artifact_retention import run_artifact_stability_gate

def test_stability_gate_passes_normal(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    res = run_artifact_stability_gate(str(root))
    assert res["ok"] is True
    assert res["status"] == "PASS"

def test_stability_gate_warns_large_size(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    (root / "big.bin").write_bytes(b"0" * 1024 * 1024 * 2) # 2MB
    
    res = run_artifact_stability_gate(str(root), {"max_total_size_mb": 1, "unknown_artifacts_default": "protect"})
    assert res["ok"] is True
    assert res["status"] == "WARN"
    assert any("total size under policy threshold" in c["check"] and c["status"] == "WARN" for c in res["checks"])

def test_stability_gate_fails_protected_deletion(tmp_path, monkeypatch):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    # We monkeypatch build_retention_plan to return a conflicting plan
    import runtime.artifact_retention
    def mock_build(*args, **kwargs):
        return {
            "ok": True,
            "runtime_data_dir": str(root),
            "summary": {"total_size_bytes": 0, "delete_candidates": 1, "delete_candidate_size_bytes": 0, "total_items": 1, "protected_items": 1, "top_groups_by_size": {}},
            "warnings": [],
            "errors": [],
            "items": [
                {"path": str(root / "conflict"), "group": "runs", "protected": True, "delete_candidate": True, "size_bytes": 0}
            ]
        }
    monkeypatch.setattr(runtime.artifact_retention, "build_retention_plan", mock_build)
    
    res = run_artifact_stability_gate(str(root))
    assert res["ok"] is False
    assert res["status"] == "FAIL"
    assert any("protected live/release artifacts not marked for deletion" in c["check"] and c["status"] == "FAIL" for c in res["checks"])

def test_stability_gate_fails_outside_root(tmp_path, monkeypatch):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    import runtime.artifact_retention
    def mock_build(*args, **kwargs):
        return {
            "ok": True,
            "runtime_data_dir": str(root),
            "summary": {"total_size_bytes": 0, "delete_candidates": 1, "delete_candidate_size_bytes": 0, "total_items": 1, "protected_items": 1, "top_groups_by_size": {}},
            "warnings": [],
            "errors": [],
            "items": [
                {"path": str(tmp_path / "outside"), "group": "runs", "protected": False, "delete_candidate": True, "size_bytes": 0}
            ]
        }
    monkeypatch.setattr(runtime.artifact_retention, "build_retention_plan", mock_build)
    
    res = run_artifact_stability_gate(str(root))
    assert res["ok"] is False
    assert res["status"] == "FAIL"
    assert any("no delete candidate outside runtime root" in c["check"] and c["status"] == "FAIL" for c in res["checks"])
