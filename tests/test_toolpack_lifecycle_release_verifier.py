from __future__ import annotations

import json
from pathlib import Path


def test_release_verifier_references_toolpack_lifecycle() -> None:
    path = Path("tools/run_release_candidate_verification.py")
    text = path.read_text(encoding="utf-8")
    assert "toolpack_lifecycle" in text
    assert "_check_toolpack_lifecycle" in text


def test_release_verifier_has_toolpack_lifecycle_check() -> None:
    from tools.run_release_candidate_verification import _check_toolpack_lifecycle

    result = _check_toolpack_lifecycle()
    assert result["name"] == "toolpack_lifecycle"
    assert result["status"] == "PASS"


def test_release_verifier_blocks_lifecycle_failure(monkeypatch) -> None:
    import tools.run_release_candidate_verification as verifier

    def fake_evaluate(*args, **kwargs):
        return {
            "ok": False,
            "toolpack_id": "demo_echo",
            "environment": "dev",
            "status": "INVALID",
            "generated_at": "2026-05-18T00:00:00Z",
            "stages": {"discovered": "PASS"},
            "stage_details": {},
            "errors": ["boom"],
            "warnings": [],
            "recommended_next_action": "fix it",
        }

    def fake_write(result, *, runtime_data_dir):
        runtime_root = Path(runtime_data_dir)
        lifecycle_dir = runtime_root / "toolpacks" / "lifecycle"
        lifecycle_dir.mkdir(parents=True, exist_ok=True)
        json_path = lifecycle_dir / "demo_echo_lifecycle.json"
        md_path = lifecycle_dir / "demo_echo_lifecycle.md"
        json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        md_path.write_text("# demo echo\n", encoding="utf-8")
        return {"json_path": str(json_path), "markdown_path": str(md_path)}

    def fake_run_command(name, command, timeout_seconds=300):
        if name == "toolpack_lifecycle_cli":
            return {"name": name, "command": command, "returncode": 0, "stdout": json.dumps({"ok": False, "status": "INVALID"}), "stderr": "", "stdout_tail": "", "stderr_tail": "", "status": "PASS"}
        return {"name": name, "command": command, "returncode": 0, "stdout": "", "stderr": "", "stdout_tail": "", "stderr_tail": "", "status": "PASS"}

    monkeypatch.setattr(verifier, "run_command", fake_run_command)
    monkeypatch.setattr("src.toolpack_lifecycle.evaluate_toolpack_lifecycle", fake_evaluate)
    monkeypatch.setattr("src.toolpack_lifecycle.write_lifecycle_report", fake_write)

    result = verifier._check_toolpack_lifecycle()
    assert result["name"] == "toolpack_lifecycle"
    assert result["status"] == "FAIL"
