from __future__ import annotations

from pathlib import Path

import tools.run_release_candidate_verification as verifier


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_verifier_runtime_store_passes_seeded_demo_runtime(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    _write_doc(
        docs / "runtime_store.md",
        "runtime store layout backup restore retention taskframes approval packs evidence live data pending actions runtime-store check taskframe runtime-store index taskframe runtime-store backup taskframe runtime-store restore taskframe runtime-store retention-plan taskframe runtime-store cleanup",
    )
    _write_doc(
        docs / "configuration.md",
        "runtime store runtime profiles",
    )
    _write_doc(
        docs / "cli_reference.md",
        "taskframe runtime-store check taskframe runtime-store index taskframe runtime-store backup taskframe runtime-store restore taskframe runtime-store retention-plan taskframe runtime-store cleanup",
    )
    _write_doc(
        docs / "release_verification.md",
        "runtime store validation backup restore retention",
    )

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "RUNTIME_STORE_MD", docs / "runtime_store.md", raising=False)
    monkeypatch.setattr(verifier, "CONFIGURATION_MD", docs / "configuration.md", raising=False)
    monkeypatch.setattr(verifier, "OUTPUT_MD", docs / "release_verification.md", raising=False)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true}", "stderr": "", "stdout_tail": "{\"ok\": true}", "stderr_tail": "", "status": "PASS"})

    result = verifier._check_runtime_store()

    assert result["status"] == "PASS"
    assert result["missing"] == []


def test_release_verifier_runtime_store_fails_when_validation_breaks(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    _write_doc(docs / "runtime_store.md", "runtime store layout backup restore retention taskframes approval packs evidence live data")
    _write_doc(docs / "configuration.md", "runtime store runtime profiles")
    _write_doc(docs / "cli_reference.md", "taskframe runtime-store check taskframe runtime-store index taskframe runtime-store backup taskframe runtime-store restore taskframe runtime-store retention-plan taskframe runtime-store cleanup")
    _write_doc(docs / "release_verification.md", "runtime store validation backup restore retention")

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "RUNTIME_STORE_MD", docs / "runtime_store.md", raising=False)
    monkeypatch.setattr(verifier, "CONFIGURATION_MD", docs / "configuration.md", raising=False)
    monkeypatch.setattr(verifier, "OUTPUT_MD", docs / "release_verification.md", raising=False)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true}", "stderr": "", "stdout_tail": "{\"ok\": true}", "stderr_tail": "", "status": "PASS"})

    import runtime.runtime_store as runtime_store

    monkeypatch.setattr(
        runtime_store,
        "validate_runtime_store",
        lambda *args, **kwargs: {"ok": False, "artifact_counts": {}, "issues": [{"category": "invalid_json", "message": "boom"}], "taskframes": [], "approval_packs": [], "reports": [], "evidence": [], "tool_health": [], "indexes": [], "cleanup": [], "migrations": [], "corrupted_paths": [], "orphaned_artifacts": [], "index_rebuildable": False},
    )

    result = verifier._check_runtime_store()

    assert result["status"] == "FAIL"
    assert "seeded_runtime_store_validation_failed" in result["missing"]
