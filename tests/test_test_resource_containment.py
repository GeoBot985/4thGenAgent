from __future__ import annotations

import inspect
from pathlib import Path

import tools.run_release_candidate_verification as verifier


def test_pytest_configuration_constrains_default_collection() -> None:
    text = Path("pytest.ini").read_text(encoding="utf-8")
    assert "testpaths = tests" in text
    assert "addopts = --strict-markers" in text
    for term in (
        ".git",
        ".claude",
        "worktrees",
        "runtime_data",
        "docs",
        "dist",
        "build",
    ):
        assert term in text
    for marker in ("unit:", "backend:", "manifest:", "toolpack:", "runtime:", "reports:", "smoke:", "integration:", "slow:", "live:", "full_ci:"):
        assert marker in text


def test_claude_code_policy_blocks_full_verifier_by_default() -> None:
    text = Path("CLAUDE.md").read_text(encoding="utf-8")
    assert "Do not run the full test suite locally." in text
    assert "python tools/run_bounded_validation.py quick" in text
    assert "python tools/run_bounded_validation.py local" in text
    assert "python -m pytest" in text
    assert "Full pytest is reserved for overnight/full CI only." in text


def test_release_verifier_modes_and_log_streaming_exist() -> None:
    text = inspect.getsource(verifier)
    signature = inspect.signature(verifier.build_verification_result)
    assert signature.parameters["mode"].default == "release"
    assert "add_argument(\"--mode\"" in text
    assert "def _build_mode_verification_result" in text
    assert "manifest_regression_gallery_validate" in text
    assert "stdout_log_path" in text
    assert "stderr_log_path" in text
    assert "duration_seconds" in text
    assert "tools/run_bounded_validation.py" in text


def test_run_command_streams_output_to_logs_without_retaining_full_stdout(tmp_path) -> None:
    result = verifier.run_command(
        "containment_probe",
        ["python", "-c", "print('containment-probe')"],
        timeout_seconds=30,
    )
    assert set(result) == {
        "returncode",
        "duration_seconds",
        "stdout_log_path",
        "stderr_log_path",
        "stdout_tail",
        "stderr_tail",
        "status",
    }
    assert result["status"] == "PASS"
    assert result["returncode"] == 0
    assert "containment-probe" in result["stdout_tail"]
    assert "stdout" not in result
    assert "stderr" not in result
    stdout_log = Path(result["stdout_log_path"])
    stderr_log = Path(result["stderr_log_path"])
    assert stdout_log.is_file()
    assert stderr_log.is_file()
    assert "containment-probe" in stdout_log.read_text(encoding="utf-8")
    assert stderr_log.read_text(encoding="utf-8") == ""
