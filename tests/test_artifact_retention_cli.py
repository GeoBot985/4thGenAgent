import subprocess
import json
import pytest
from pathlib import Path

def test_cli_artifacts_status(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    cmd = ["python", "src/taskframe_cli.py", "artifacts", "status", "--runtime-data-dir", str(root)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Runtime Artifact Status" in res.stdout
    assert "Total items: 0" in res.stdout

def test_cli_artifacts_plan_cleanup(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    cmd = ["python", "src/taskframe_cli.py", "artifacts", "plan-cleanup", "--runtime-data-dir", str(root)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Artifact Cleanup Plan (Dry Run)" in res.stdout

def test_cli_artifacts_cleanup_blocked_without_confirm(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    cmd = ["python", "src/taskframe_cli.py", "artifacts", "cleanup", "--runtime-data-dir", str(root)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    assert "FAIL" in res.stdout
    assert "Hint: You must provide --confirm" in res.stdout

def test_cli_artifacts_cleanup_with_confirm(tmp_path):
    root = tmp_path / "runtime_data"
    root.mkdir()
    
    cmd = ["python", "src/taskframe_cli.py", "artifacts", "cleanup", "--runtime-data-dir", str(root), "--confirm"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "SUCCESS" in res.stdout
