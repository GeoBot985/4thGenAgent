from __future__ import annotations

import json
from pathlib import Path

import runtime.runtime_environment as runtime_env
from runtime.service_runtime import build_service_preflight, write_service_preflight_report


def _write_service_config(config_dir: Path, payload: dict[str, object]) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "taskframe.service.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_empty_toolpack_config(path: Path) -> Path:
    path.write_text(json.dumps({"enabled_toolpacks": [], "disabled_toolpacks": [], "allow_optional_toolpacks": False}, indent=2), encoding="utf-8")
    return path


def test_service_preflight_passes_with_example_safe_config(monkeypatch, tmp_path) -> None:
    runtime_profile_path = tmp_path / "runtime_profile.json"
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", runtime_profile_path, raising=False)

    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(
        config_dir,
        {
            "profile": "service",
            "runtime_data_dir": str(runtime_data_dir),
            "llm": {"provider": "fake"},
            "google": {"enabled": False, "credentials_path": "", "token_path": ""},
            "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
            "live_execution": {"enabled": False},
            "worker_identity": {
                "worker_id": "service-worker-1",
                "worker_role": "general",
                "environment": "service",
                "operator_id": "system",
                "approval_authority": "system",
            },
        },
    )

    result = build_service_preflight(
        profile_name="service",
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir="manifests",
        routes_path="config/event_routes.json",
        toolpack_config_path=toolpack_config_path,
    )

    assert result["ok"] is True
    assert result["profile"] == "service"
    assert result["worker_identity"]["worker_id"] == "service-worker-1"
    assert any(check["id"] == "optional_rpa_blocked" and check["status"] == "PASS" for check in result["checks"])

    report_paths = write_service_preflight_report(result, runtime_data_dir=runtime_data_dir)
    assert Path(report_paths["json"]).is_file()
    assert Path(report_paths["markdown"]).is_file()


def test_service_preflight_fails_when_worker_identity_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(
        config_dir,
        {
            "profile": "service",
            "runtime_data_dir": str(runtime_data_dir),
            "llm": {"provider": "fake"},
            "google": {"enabled": False, "credentials_path": "", "token_path": ""},
            "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
            "live_execution": {"enabled": False},
        },
    )

    result = build_service_preflight(
        profile_name="service",
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir="manifests",
        routes_path="config/event_routes.json",
        toolpack_config_path=toolpack_config_path,
    )

    blocker_ids = {blocker["id"] for blocker in result["blockers"]}
    assert result["ok"] is False
    assert "config_worker_identity_present" in blocker_ids


def test_service_preflight_fails_when_live_side_effects_are_enabled(monkeypatch, tmp_path) -> None:
    runtime_profile_path = tmp_path / "runtime_profile.json"
    runtime_profile_path.write_text(
        json.dumps(
            {
                "profile": "service",
                "environment": "service",
                "fixture_mode": False,
                "dry_run_default": True,
                "allow_live_reads": False,
                "allow_live_side_effects": True,
                "require_tool_governance": True,
                "allowed_toolpacks": [],
                "blocked_tool_classes": ["rpa", "write", "send", "delete", "mutation", "side_effect"],
                "llm_provider": "fake",
                "requires_credentials": False,
                "evidence_required": True,
                "worker_identity_required": True,
                "reserved_for_deployment": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", runtime_profile_path, raising=False)

    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(
        config_dir,
        {
            "profile": "service",
            "runtime_data_dir": str(runtime_data_dir),
            "llm": {"provider": "fake"},
            "google": {"enabled": False, "credentials_path": "", "token_path": ""},
            "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
            "live_execution": {"enabled": False},
            "worker_identity": {
                "worker_id": "service-worker-1",
                "worker_role": "general",
                "environment": "service",
                "operator_id": "system",
                "approval_authority": "system",
            },
        },
    )

    result = build_service_preflight(
        profile_name="service",
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir="manifests",
        routes_path="config/event_routes.json",
        toolpack_config_path=toolpack_config_path,
    )

    blocker_ids = {blocker["id"] for blocker in result["blockers"]}
    assert result["ok"] is False
    assert "live_side_effects_disabled" in blocker_ids


def test_service_preflight_fails_for_live_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(
        config_dir,
        {
            "profile": "service",
            "runtime_data_dir": str(runtime_data_dir),
            "llm": {"provider": "fake"},
            "google": {"enabled": False, "credentials_path": "", "token_path": ""},
            "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
            "live_execution": {"enabled": False},
            "worker_identity": {
                "worker_id": "service-worker-1",
                "worker_role": "general",
                "environment": "service",
                "operator_id": "system",
                "approval_authority": "system",
            },
        },
    )

    result = build_service_preflight(
        profile_name="live",
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir="manifests",
        routes_path="config/event_routes.json",
        toolpack_config_path=toolpack_config_path,
    )

    blocker_ids = {blocker["id"] for blocker in result["blockers"]}
    assert result["ok"] is False
    assert "service_profile_required" in blocker_ids
    assert "profile_not_live" in blocker_ids


def test_service_preflight_fails_when_optional_rpa_is_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = _write_empty_toolpack_config(tmp_path / "enabled_toolpacks.json")
    _write_service_config(
        config_dir,
        {
            "profile": "service",
            "runtime_data_dir": str(runtime_data_dir),
            "llm": {"provider": "fake"},
            "google": {"enabled": False, "credentials_path": "", "token_path": ""},
            "rpa": {"enabled": True, "browser_user_data_dir": "", "browser_profile_dir": ""},
            "live_execution": {"enabled": False},
            "worker_identity": {
                "worker_id": "service-worker-1",
                "worker_role": "general",
                "environment": "service",
                "operator_id": "system",
                "approval_authority": "system",
            },
        },
    )

    result = build_service_preflight(
        profile_name="service",
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir="manifests",
        routes_path="config/event_routes.json",
        toolpack_config_path=toolpack_config_path,
    )

    blocker_ids = {blocker["id"] for blocker in result["blockers"]}
    assert result["ok"] is False
    assert "optional_rpa_blocked" in blocker_ids


def test_service_preflight_fails_when_unknown_toolpacks_are_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_env, "RUNTIME_PROFILE_PATH", tmp_path / "runtime_profile.json", raising=False)

    config_dir = tmp_path / "config"
    runtime_data_dir = tmp_path / "runtime_data"
    toolpack_config_path = tmp_path / "enabled_toolpacks.json"
    toolpack_config_path.write_text(
        json.dumps({"enabled_toolpacks": [str(tmp_path / "missing_toolpack.json")], "disabled_toolpacks": [], "allow_optional_toolpacks": False}, indent=2),
        encoding="utf-8",
    )
    _write_service_config(
        config_dir,
        {
            "profile": "service",
            "runtime_data_dir": str(runtime_data_dir),
            "llm": {"provider": "fake"},
            "google": {"enabled": False, "credentials_path": "", "token_path": ""},
            "rpa": {"enabled": False, "browser_user_data_dir": "", "browser_profile_dir": ""},
            "live_execution": {"enabled": False},
            "worker_identity": {
                "worker_id": "service-worker-1",
                "worker_role": "general",
                "environment": "service",
                "operator_id": "system",
                "approval_authority": "system",
            },
        },
    )

    result = build_service_preflight(
        profile_name="service",
        runtime_data_dir=runtime_data_dir,
        config_dir=config_dir,
        manifest_dir="manifests",
        routes_path="config/event_routes.json",
        toolpack_config_path=toolpack_config_path,
    )

    blocker_ids = {blocker["id"] for blocker in result["blockers"]}
    assert result["ok"] is False
    assert "no_unknown_external_toolpacks" in blocker_ids
