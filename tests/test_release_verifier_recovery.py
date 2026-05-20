from __future__ import annotations

from pathlib import Path

import tools.run_release_candidate_verification as verifier


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_verifier_recovery_passes(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    _write_doc(
        docs / "recovery_and_idempotency.md",
        "retryable manual review idempotency dry-run by default taskframe recover assess taskframe recover retry-step taskframe recover resume",
    )
    _write_doc(docs / "cli_reference.md", "taskframe recover assess taskframe recover retry-step taskframe recover resume")
    _write_doc(docs / "runtime_store.md", "runtime store")
    _write_doc(docs / "operational_monitoring.md", "operational monitoring")
    _write_doc(docs / "live_execution_safety.md", "live execution safety")
    _write_doc(docs / "release_verification.md", "recovery")

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "RECOVERY_AND_IDEMPOTENCY_MD", docs / "recovery_and_idempotency.md", raising=False)
    monkeypatch.setattr(verifier, "OUTPUT_MD", docs / "release_verification.md", raising=False)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true, \"dry_run\": true}", "stderr": "", "stdout_tail": "{\"ok\": true, \"dry_run\": true}", "stderr_tail": "", "status": "PASS"})

    result = verifier._check_recovery()

    assert result["status"] == "PASS"
    assert result["missing"] == []


def test_release_verifier_recovery_fails_when_duplicate_blocking_breaks(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    _write_doc(docs / "recovery_and_idempotency.md", "retryable manual review idempotency dry-run by default taskframe recover assess taskframe recover retry-step taskframe recover resume")
    _write_doc(docs / "cli_reference.md", "taskframe recover assess taskframe recover retry-step taskframe recover resume")
    _write_doc(docs / "runtime_store.md", "runtime store")
    _write_doc(docs / "operational_monitoring.md", "operational monitoring")
    _write_doc(docs / "live_execution_safety.md", "live execution safety")
    _write_doc(docs / "release_verification.md", "recovery")

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "RECOVERY_AND_IDEMPOTENCY_MD", docs / "recovery_and_idempotency.md", raising=False)
    monkeypatch.setattr(verifier, "OUTPUT_MD", docs / "release_verification.md", raising=False)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true, \"dry_run\": true}", "stderr": "", "stdout_tail": "{\"ok\": true, \"dry_run\": true}", "stderr_tail": "", "status": "PASS"})

    import runtime.recovery as recovery

    monkeypatch.setattr(recovery, "verify_pending_action_safe_to_execute", lambda *args, **kwargs: {"ok": True})

    result = verifier._check_recovery()

    assert result["status"] == "FAIL"
    assert "duplicate_pending_action_not_blocked" in result["missing"]
