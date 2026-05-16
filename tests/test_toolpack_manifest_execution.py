from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path


DEMO_TOOLPACK = Path("tool_packs/demo_echo/toolpack.json")


@contextmanager
def _temporary_external_tools(config_path: Path):
    import runtime.tool_registry as tool_registry
    import runtime.tool_runner as tool_runner

    saved = tool_registry.build_tool_registry(include_external=True)
    external = tool_registry.build_tool_registry(include_external=True, config_path=config_path)
    tool_registry.TOOL_REGISTRY.clear()
    tool_registry.TOOL_REGISTRY.update(external)
    saved_get_tool_spec = tool_runner.get_tool_spec
    tool_runner.get_tool_spec = lambda namespace, action: external[f"{namespace}/{action}"]
    try:
        yield
    finally:
        tool_registry.TOOL_REGISTRY.clear()
        tool_registry.TOOL_REGISTRY.update(saved)
        tool_runner.get_tool_spec = saved_get_tool_spec


def _write_config(tmp_path: Path, *, allow_optional: bool = True) -> Path:
    payload = {
        "enabled_toolpacks": [str(DEMO_TOOLPACK)],
        "disabled_toolpacks": [],
        "allow_optional_toolpacks": allow_optional,
    }
    path = tmp_path / "enabled_toolpacks.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_manifest(tmp_path: Path, tool: str, output_alias: str | None = None) -> Path:
    alias = output_alias or "result"
    command = f"[t:{tool} -> {alias}] message=\"Hello\""
    manifest = {
        "manifest_id": f"test.{tool.replace('/', '_')}",
        "name": "Tool Pack Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [{"id": "step_1", "command": command}],
        "validations": [{"id": "output_exists", "type": "output_exists", "output": alias}] if output_alias else [],
        "completion": {"success_outputs": [alias] if output_alias else []},
    }
    path = tmp_path / "manifest.manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def test_manifest_can_call_external_echo_tool(tmp_path: Path) -> None:
    from runtime.manifest_loader import load_manifest
    from runtime.orchestrator import Orchestrator
    from runtime.tool_runner import ToolRunner

    config_path = _write_config(tmp_path)
    manifest_path = _write_manifest(tmp_path, "echo/echo", "echoed")
    with _temporary_external_tools(config_path):
        manifest = load_manifest(manifest_path)
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        runner = ToolRunner(dry_run=False)
        result = runner.run_step(frame, frame.steps[0])

    assert result.ok is True
    assert frame.outputs["echoed"]["data"]["echo"] == "Hello"
    assert frame.outputs["echoed"]["data"]["message"] == "Hello"


def test_validation_can_check_external_tool_output_exists(tmp_path: Path) -> None:
    from runtime.validation import run_validation
    from runtime.manifest_loader import load_manifest
    from runtime.orchestrator import Orchestrator
    from runtime.tool_runner import ToolRunner

    config_path = _write_config(tmp_path)
    manifest_path = _write_manifest(tmp_path, "echo/echo", "echoed")
    with _temporary_external_tools(config_path):
        manifest = load_manifest(manifest_path)
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        runner = ToolRunner(dry_run=False)
        runner.run_step(frame, frame.steps[0])
        result = run_validation(frame, {"id": "v1", "type": "output_exists", "output": "echoed"})

    assert result.ok is True


def test_failed_external_tool_returns_failed_execution(tmp_path: Path) -> None:
    from runtime.manifest_loader import load_manifest
    from runtime.orchestrator import Orchestrator
    from runtime.tool_runner import ToolRunner

    config_path = _write_config(tmp_path)
    manifest_path = _write_manifest(tmp_path, "echo/fail")
    with _temporary_external_tools(config_path):
        manifest = load_manifest(manifest_path)
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        runner = ToolRunner(dry_run=False)
        runner.run_step(frame, frame.steps[0])

    assert frame.state == "FAILED_EXECUTION"
    assert frame.steps[0].status == "FAILED"


def test_demo_echo_pack_has_no_side_effect_tools() -> None:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    descriptor = load_toolpack_descriptor(DEMO_TOOLPACK)
    result = validate_toolpack_descriptor(descriptor, base_path=DEMO_TOOLPACK.parent)
    assert result["ok"] is True
    assert all(not tool["side_effect"] for tool in result["descriptor"]["tools"])
