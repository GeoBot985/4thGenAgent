from __future__ import annotations

import json
from pathlib import Path

import tools.run_release_candidate_verification as verifier


def _write_doc(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_verifier_runtime_profiles_fails_unsafe_profile_changes(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    config_dir = repo / "config"
    docs_dir = repo / "docs"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_dir.joinpath("runtime_profile.json").write_text(
        json.dumps(
            {
                "profile": "release",
                "environment": "release",
                "fixture_mode": True,
                "dry_run_default": True,
                "governance_enforced": False,
                "allowed_toolpacks": [],
                "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
                "llm_provider": "fake",
                "requires_credentials": False,
                "evidence_required": True,
                "allow_reserved_live_profile": False,
                "release": {
                    "allow_live_reads": True,
                    "allow_live_side_effects": True,
                    "require_tool_governance": False,
                },
                "pilot": {
                    "require_tool_governance": False
                },
                "live": {
                    "allow_reserved_live_profile": False
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_doc(
        docs_dir / "runtime_profiles.md",
        "demo dev test release pilot live default profile pilot mode live side effects taskframe profile show taskframe profile list taskframe profile check",
    )
    _write_doc(
        docs_dir / "configuration.md",
        "runtime profiles default profile profile show profile list profile check",
    )
    _write_doc(
        docs_dir / "live_execution_safety.md",
        "profile separation demo pilot live side effects",
    )
    _write_doc(
        docs_dir / "cli_reference.md",
        "taskframe profile show taskframe profile list taskframe profile check",
    )

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true}", "stderr": "", "stdout_tail": "{\"ok\": true}", "stderr_tail": "", "status": "PASS"})

    import runtime.runtime_environment as runtime_env

    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", config_dir / "runtime_profile.json", raising=False)

    result = verifier._check_runtime_profiles()

    assert result["status"] == "FAIL"
    assert "default_profile_not_demo" in result["missing"]
    assert "default_profile_allows_live_side_effects" in result["missing"]
    assert "release_profile_allows_live_side_effects" in result["missing"]
    assert "pilot_profile_requires_tool_governance_false" in result["missing"]


def test_release_verifier_runtime_profiles_passes_safe_profile(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    config_dir = repo / "config"
    docs_dir = repo / "docs"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_dir.joinpath("runtime_profile.json").write_text(
        json.dumps(
            {
                "profile": "demo",
                "environment": "demo",
                "fixture_mode": True,
                "dry_run_default": True,
                "allow_live_reads": False,
                "allow_live_side_effects": False,
                "require_tool_governance": True,
                "governance_enforced": True,
                "allowed_toolpacks": [],
                "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
                "llm_provider": "fake",
                "requires_credentials": False,
                "evidence_required": True,
                "allow_reserved_live_profile": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_doc(
        docs_dir / "runtime_profiles.md",
        "demo dev test release pilot live default profile pilot mode live side effects taskframe profile show taskframe profile list taskframe profile check",
    )
    _write_doc(
        docs_dir / "configuration.md",
        "runtime profiles default profile profile show profile list profile check",
    )
    _write_doc(
        docs_dir / "live_execution_safety.md",
        "profile separation demo pilot live side effects",
    )
    _write_doc(
        docs_dir / "cli_reference.md",
        "taskframe profile show taskframe profile list taskframe profile check",
    )

    monkeypatch.setattr(verifier, "ROOT", repo)
    monkeypatch.setattr(verifier, "run_command", lambda name, command, timeout_seconds=300: {"name": name, "command": command, "returncode": 0, "duration_ms": 1, "stdout": "{\"ok\": true}", "stderr": "", "stdout_tail": "{\"ok\": true}", "stderr_tail": "", "status": "PASS"})

    import runtime.runtime_environment as runtime_env

    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", config_dir / "runtime_profile.json", raising=False)

    result = verifier._check_runtime_profiles()

    assert result["status"] == "PASS"
