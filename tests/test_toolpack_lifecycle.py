from __future__ import annotations

import json
from pathlib import Path

import pytest

DEMO_TOOLPACK = Path("tool_packs/demo_echo/toolpack.json")

def _write_pack_bundle(tmp_path: Path, pack_id: str, *, classification: str = "optional") -> Path:
    pack_dir = tmp_path / pack_id
    pack_dir.mkdir()
    (pack_dir / "__init__.py").write_text("", encoding="utf-8")
    (pack_dir / "tools.py").write_text(
        """
from __future__ import annotations


def run(message: str = "TEST") -> dict:
    return {
        "ok": True,
        "type": "temp_result",
        "data": {"message": message},
        "evidence": {
            "tool": "temp/run",
            "mode": "dry_run",
            "source": "external_toolpack",
            "operation": "read",
            "input_refs": [],
            "output_ref": "temp_result",
        },
        "error": "",
    }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (pack_dir / "health.py").write_text(
        """
from __future__ import annotations


def check_health(*, live: bool = False) -> dict:
    return {
        "ok": True,
        "status": "ready",
        "severity": "info",
        "message": "ok",
        "errors": [],
        "warnings": [],
    }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    descriptor = {
        "toolpack_id": pack_id,
        "name": pack_id.replace("_", " ").title(),
        "version": "1.0.0",
        "runtime_contract_version": 1,
        "core_or_optional": classification,
        "module_prefix": f"tmp.{pack_id}",
        "health_supported": True,
        "health": {"module": f"{pack_id}.health", "function": "check_health"},
        "tools": [
            {
                "tool": "temp/run",
                "namespace": "temp",
                "action": "run",
                "module": f"{pack_id}.tools",
                "function": "run",
                "side_effect": False,
                "requires_approval": False,
                "allow_live": False,
                "allow_live_side_effect": False,
                "live_guardrail": "blocked",
                "output_type": "temp_result",
                "required_args": ["message"],
                "optional_args": [],
                "arg_types": {"message": "str"},
                "dry_run_executes": True,
            }
        ],
    }
    (pack_dir / "toolpack.json").write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
    return pack_dir / "toolpack.json"


def _write_governance(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "entries": entries}, indent=2), encoding="utf-8")


def test_lifecycle_ready_for_valid_enabled_dev_pack() -> None:
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    result = evaluate_toolpack_lifecycle(DEMO_TOOLPACK, environment="dev")
    assert result["ok"] is True
    assert result["status"] == "READY"
    assert all(status == "PASS" for status in result["stages"].values())


def test_lifecycle_invalid_for_missing_descriptor(tmp_path: Path) -> None:
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    result = evaluate_toolpack_lifecycle(tmp_path / "missing" / "toolpack.json")
    assert result["ok"] is False
    assert result["status"] == "UNKNOWN"
    assert result["errors"]


def test_lifecycle_invalid_for_bad_descriptor_json(tmp_path: Path) -> None:
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    bad_path = tmp_path / "bad_pack" / "toolpack.json"
    bad_path.parent.mkdir()
    bad_path.write_text("{not-json", encoding="utf-8")
    result = evaluate_toolpack_lifecycle(bad_path)
    assert result["ok"] is False
    assert result["status"] == "UNKNOWN"
    assert result["errors"]


def test_lifecycle_governance_required_when_no_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src import toolpack_governance
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    toolpack_json = _write_pack_bundle(tmp_path, "no_policy_pack")
    monkeypatch.syspath_prepend(str(tmp_path))
    config_path = tmp_path / "enabled_toolpacks.json"
    config_path.write_text(json.dumps({"enabled_toolpacks": [str(toolpack_json)], "disabled_toolpacks": [], "allow_optional_toolpacks": True}, indent=2), encoding="utf-8")
    monkeypatch.setattr(toolpack_governance, "GOVERNANCE_PATH", tmp_path / "toolpack_governance.json")
    result = evaluate_toolpack_lifecycle(toolpack_json, environment="dev", config_path=config_path, runtime_data_dir=tmp_path / "runtime_data")
    assert result["ok"] is False
    assert result["status"] == "GOVERNANCE_REQUIRED"


def test_lifecycle_blocked_when_pack_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src import toolpack_governance
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    toolpack_json = _write_pack_bundle(tmp_path, "disabled_pack")
    monkeypatch.syspath_prepend(str(tmp_path))
    config_path = tmp_path / "enabled_toolpacks.json"
    config_path.write_text(json.dumps({"enabled_toolpacks": [], "disabled_toolpacks": [str(toolpack_json)], "allow_optional_toolpacks": True}, indent=2), encoding="utf-8")
    _write_governance(
        tmp_path / "toolpack_governance.json",
        [
            {
                "toolpack_id": "disabled_pack",
                "classification": "optional",
                "enabled_environments": ["dev"],
                "enabled_by": "test",
                "enabled_at": "2026-05-18T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(toolpack_governance, "GOVERNANCE_PATH", tmp_path / "toolpack_governance.json")
    result = evaluate_toolpack_lifecycle(toolpack_json, environment="dev", config_path=config_path, runtime_data_dir=tmp_path / "runtime_data")
    assert result["ok"] is False
    assert result["status"] == "DISABLED"


def test_lifecycle_blocks_high_risk_pack_in_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src import toolpack_governance
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    toolpack_json = _write_pack_bundle(tmp_path, "high_risk_pack")
    monkeypatch.syspath_prepend(str(tmp_path))
    config_path = tmp_path / "enabled_toolpacks.json"
    config_path.write_text(json.dumps({"enabled_toolpacks": [str(toolpack_json)], "disabled_toolpacks": [], "allow_optional_toolpacks": True}, indent=2), encoding="utf-8")
    _write_governance(
        tmp_path / "toolpack_governance.json",
        [
            {
                "toolpack_id": "high_risk_pack",
                "classification": "high_risk",
                "enabled_environments": ["demo", "dev", "test"],
                "enabled_by": "test",
                "enabled_at": "2026-05-18T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(toolpack_governance, "GOVERNANCE_PATH", tmp_path / "toolpack_governance.json")
    result = evaluate_toolpack_lifecycle(toolpack_json, environment="demo", config_path=config_path, runtime_data_dir=tmp_path / "runtime_data")
    assert result["ok"] is False
    assert result["status"] == "BLOCKED"


def test_lifecycle_runs_contract_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.toolpack_lifecycle as lifecycle
    from src import toolpack_governance

    toolpack_json = _write_pack_bundle(tmp_path, "contract_pack")
    monkeypatch.syspath_prepend(str(tmp_path))
    config_path = tmp_path / "enabled_toolpacks.json"
    config_path.write_text(json.dumps({"enabled_toolpacks": [str(toolpack_json)], "disabled_toolpacks": [], "allow_optional_toolpacks": True}, indent=2), encoding="utf-8")
    _write_governance(
        tmp_path / "toolpack_governance.json",
        [
            {
                "toolpack_id": "contract_pack",
                "classification": "optional",
                "enabled_environments": ["dev"],
                "enabled_by": "test",
                "enabled_at": "2026-05-18T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(toolpack_governance, "GOVERNANCE_PATH", tmp_path / "toolpack_governance.json")
    called = {"value": False}

    def fake_contract(*args, **kwargs):
        called["value"] = True
        return {
            "ok": True,
            "status": "PASS",
            "toolpack_id": "contract_pack",
            "checks": [],
            "tool_checks": [],
            "manifest_smoke": {"ok": True, "message": "skipped"},
            "errors": [],
            "warnings": [],
        }

    monkeypatch.setattr(lifecycle, "run_toolpack_contract_tests", fake_contract)
    result = lifecycle.evaluate_toolpack_lifecycle(toolpack_json, environment="dev", config_path=config_path, runtime_data_dir=tmp_path / "runtime_data")
    assert called["value"] is True
    assert result["stages"]["contract_test"] == "PASS"


def test_lifecycle_runs_health_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.toolpack_lifecycle as lifecycle
    from src import toolpack_governance
    import src.toolpack_loader as toolpack_loader

    toolpack_json = _write_pack_bundle(tmp_path, "health_pack")
    monkeypatch.syspath_prepend(str(tmp_path))
    config_path = tmp_path / "enabled_toolpacks.json"
    config_path.write_text(json.dumps({"enabled_toolpacks": [str(toolpack_json)], "disabled_toolpacks": [], "allow_optional_toolpacks": True}, indent=2), encoding="utf-8")
    _write_governance(
        tmp_path / "toolpack_governance.json",
        [
            {
                "toolpack_id": "health_pack",
                "classification": "optional",
                "enabled_environments": ["dev"],
                "enabled_by": "test",
                "enabled_at": "2026-05-18T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(toolpack_governance, "GOVERNANCE_PATH", tmp_path / "toolpack_governance.json")
    called = {"value": False}

    def fake_health(*args, **kwargs):
        called["value"] = True
        return {
            "ok": True,
            "toolpack_id": "health_pack",
            "status": "ready",
            "severity": "info",
            "message": "ok",
            "errors": [],
            "warnings": [],
            "source": "external_toolpack",
            "path": str(toolpack_json),
            "enabled": True,
            "registered": True,
        }

    monkeypatch.setattr(toolpack_loader, "check_toolpack_health", fake_health)
    result = lifecycle.evaluate_toolpack_lifecycle(toolpack_json, environment="dev", config_path=config_path, runtime_data_dir=tmp_path / "runtime_data")
    assert called["value"] is True
    assert result["stages"]["health_check"] == "PASS"


def test_lifecycle_checks_registry_integration() -> None:
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle

    result = evaluate_toolpack_lifecycle(DEMO_TOOLPACK, environment="dev")
    assert result["stages"]["registry_integration"] == "PASS"
    assert result["stage_details"]["registry_integration"]["status"] == "PASS"


def test_lifecycle_writes_json_and_markdown_report(tmp_path: Path) -> None:
    from src.toolpack_lifecycle import evaluate_toolpack_lifecycle, write_lifecycle_report

    result = evaluate_toolpack_lifecycle(DEMO_TOOLPACK, environment="dev", runtime_data_dir=tmp_path / "runtime_data")
    paths = write_lifecycle_report(result, runtime_data_dir=tmp_path / "runtime_data")
    json_path = Path(paths["json_path"])
    markdown_path = Path(paths["markdown_path"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["toolpack_id"] == "demo_echo"
    assert "Stages" in markdown_path.read_text(encoding="utf-8")
