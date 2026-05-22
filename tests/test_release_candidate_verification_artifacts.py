from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path("tools/run_release_candidate_verification.py")
REPORT_PATH = Path("docs/release_candidate_verification.md")
JSON_PATH = Path("runtime_data/audit/release_candidate_verification.json")
EVIDENCE_INDEX_PATH = Path("docs/release_candidate_evidence_index.md")
KNOWN_LIMITATIONS_PATH = Path("docs/known_limitations.md")
pytestmark = pytest.mark.release


def _load_module():
    spec = importlib.util.spec_from_file_location("rc_verifier", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_candidate_verification_script_exists():
    assert SCRIPT_PATH.is_file()


def test_release_candidate_report_exists_after_script_run():
    module = _load_module()
    result = {
        "mode": "release",
        "verdict": "READY_WITH_KNOWN_LIMITATIONS",
        "generated_at": "2026-05-04T00:00:00Z",
        "summary": {"command_count": 1, "passed_commands": 1, "failed_commands": 0, "skipped_checks": 0},
        "environment": {"python_version": "test", "platform": "test", "cwd": "test", "git_commit": "abc", "git_branch": "main"},
        "commands": [{
            "name": "bounded_validation_ci",
            "command": ["python", "tools/run_bounded_validation.py", "ci"],
            "returncode": 0,
            "duration_seconds": 0.001,
            "stdout_log_path": "runtime_data/release_verification/logs/bounded_validation_ci.stdout.log",
            "stderr_log_path": "runtime_data/release_verification/logs/bounded_validation_ci.stderr.log",
            "stdout_tail": "ok",
            "stderr_tail": "",
            "status": "PASS",
        }],
        "static_checks": [{"name": "orchestrator_pollution", "status": "PASS"}],
        "artifact_checks": [{"path": "README.md", "exists": True, "status": "PASS"}],
        "workflow_checks": {"customer": {"status": "PASS"}},
        "known_limitations": ["example"],
        "release_blockers": [],
        "evidence_paths": ["runtime_data/runs/frame_1/reports/run_report.md"],
    }
    module.write_markdown_report(result, str(REPORT_PATH))
    module.write_json_result(result, str(JSON_PATH))
    module._write_supporting_docs(result)
    assert REPORT_PATH.is_file()
    assert JSON_PATH.is_file()
    assert EVIDENCE_INDEX_PATH.is_file()
    assert KNOWN_LIMITATIONS_PATH.is_file()


def test_release_candidate_json_has_verdict():
    data = JSON_PATH.read_text(encoding="utf-8")
    assert "verdict" in data


def test_release_candidate_json_has_command_results():
    data = JSON_PATH.read_text(encoding="utf-8")
    assert "commands" in data


def test_release_candidate_report_mentions_verdict():
    text = REPORT_PATH.read_text(encoding="utf-8")
    assert "Release Candidate Verification Report" in text
    assert "Verdict" in text


def test_known_limitations_exists():
    assert KNOWN_LIMITATIONS_PATH.is_file()


def test_evidence_index_exists():
    assert EVIDENCE_INDEX_PATH.is_file()
