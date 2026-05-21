import pytest
import sys
import os
from unittest.mock import patch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../tools')))
from run_release_candidate_verification import _check_artifact_stability_gate

def test_verifier_quick_mode_inventory_only(monkeypatch):
    import runtime.artifact_retention
    called = []
    
    def mock_build(*args, **kwargs):
        called.append("build")
        return {"ok": True}
        
    def mock_gate(*args, **kwargs):
        called.append("gate")
        return {"ok": True, "status": "PASS"}
        
    monkeypatch.setattr(runtime.artifact_retention, "build_retention_plan", mock_build)
    monkeypatch.setattr(runtime.artifact_retention, "run_artifact_stability_gate", mock_gate)
    
    res = _check_artifact_stability_gate("quick")
    assert res["status"] == "PASS"
    assert "build" in called
    assert "gate" not in called

def test_verifier_standard_mode_runs_gate(monkeypatch):
    import runtime.artifact_retention
    called = []
    
    def mock_gate(*args, **kwargs):
        called.append("gate")
        return {"ok": True, "status": "PASS"}
        
    monkeypatch.setattr(runtime.artifact_retention, "run_artifact_stability_gate", mock_gate)
    
    res = _check_artifact_stability_gate("standard")
    assert res["status"] == "PASS"
    assert "gate" in called

def test_verifier_fails_if_gate_fails(monkeypatch):
    import runtime.artifact_retention
    
    def mock_gate(*args, **kwargs):
        return {"ok": False, "status": "FAIL", "errors": ["Gate failed"]}
        
    monkeypatch.setattr(runtime.artifact_retention, "run_artifact_stability_gate", mock_gate)
    
    res = _check_artifact_stability_gate("release")
    assert res["status"] == "FAIL"
    assert "Gate failed" in res["failures"]
