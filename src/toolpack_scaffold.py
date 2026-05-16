"""Scaffold generator for external tool packs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLPACKS_DIR = ROOT / "tool_packs"

_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SMOKE_DEFAULTS: dict[str, Any] = {
    "str": "TEST",
    "int": 1,
    "float": 1.0,
    "bool": False,
    "dict": {},
    "list": [],
}


def scaffold_toolpack(
    *,
    toolpack_id: str,
    namespace: str | None = None,
    tool_name: str | None = None,
    side_effect: bool = False,
    safe_read: bool = True,
    output_dir: str | Path = "tool_packs",
    force: bool = False,
) -> dict[str, Any]:
    errors = _validate_scaffold_args(toolpack_id, namespace, tool_name)
    if errors:
        return {"ok": False, "toolpack_id": toolpack_id, "path": "", "files_created": [], "toolpack_json": "", "warnings": [], "errors": errors}

    ns = namespace or toolpack_id
    tool = tool_name or "run"
    is_side_effect = side_effect and not safe_read

    out_base = Path(output_dir) if Path(output_dir).is_absolute() else ROOT / output_dir
    pack_dir = out_base / toolpack_id

    if pack_dir.exists() and not force:
        return {
            "ok": False,
            "toolpack_id": toolpack_id,
            "path": str(pack_dir),
            "files_created": [],
            "toolpack_json": "",
            "warnings": [],
            "errors": [f"Tool pack directory already exists: {pack_dir}. Use force=True to overwrite."],
        }

    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "tests").mkdir(exist_ok=True)
    (pack_dir / "examples").mkdir(exist_ok=True)

    files_created: list[str] = []
    warnings: list[str] = []

    def _write(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        try:
            files_created.append(str(path.relative_to(ROOT)))
        except ValueError:
            files_created.append(str(path))

    toolpack_json_path = pack_dir / "toolpack.json"
    _write(toolpack_json_path, render_toolpack_descriptor(toolpack_id=toolpack_id, namespace=ns, tool_name=tool, side_effect=is_side_effect))
    _write(pack_dir / "__init__.py", "")
    _write(pack_dir / "tools.py", render_tools_py(toolpack_id=toolpack_id, namespace=ns, tool_name=tool, side_effect=is_side_effect))
    _write(pack_dir / "health.py", render_health_py(toolpack_id=toolpack_id))
    _write(pack_dir / "README.md", render_readme(toolpack_id=toolpack_id, namespace=ns, tool_name=tool, side_effect=is_side_effect))
    _write(pack_dir / "tests" / "__init__.py", "")
    _write(pack_dir / "tests" / f"test_{toolpack_id}_contract.py", render_contract_tests(toolpack_id=toolpack_id, namespace=ns, tool_name=tool, side_effect=is_side_effect))
    _write(pack_dir / "tests" / f"test_{toolpack_id}_health.py", render_health_tests(toolpack_id=toolpack_id))
    _write(pack_dir / "tests" / f"test_{toolpack_id}_tools.py", render_tool_tests(toolpack_id=toolpack_id, namespace=ns, tool_name=tool, side_effect=is_side_effect))
    _write(pack_dir / "examples" / f"smoke_{toolpack_id}_{tool}.manifest.json", render_example_manifest(toolpack_id=toolpack_id, namespace=ns, tool_name=tool, side_effect=is_side_effect))

    try:
        toolpack_json_rel = str(toolpack_json_path.relative_to(ROOT))
    except ValueError:
        toolpack_json_rel = str(toolpack_json_path)

    return {
        "ok": True,
        "toolpack_id": toolpack_id,
        "path": str(pack_dir),
        "files_created": files_created,
        "toolpack_json": toolpack_json_rel,
        "warnings": warnings,
        "errors": [],
    }


def render_toolpack_descriptor(*, toolpack_id: str, namespace: str, tool_name: str, side_effect: bool = False) -> str:
    output_type = f"{namespace}_{tool_name}_result"
    required_args: list[str]
    optional_args: list[str]
    arg_types: dict[str, str]

    if side_effect:
        required_args = ["recipient", "subject", "body"]
        optional_args = ["dry_run"]
        arg_types = {"recipient": "str", "subject": "str", "body": "str", "dry_run": "bool"}
    else:
        required_args = ["query"]
        optional_args = ["limit"]
        arg_types = {"query": "str", "limit": "int"}

    descriptor = {
        "toolpack_id": toolpack_id,
        "name": toolpack_id.replace("_", " ").title() + " Tool Pack",
        "version": "1.0.0",
        "runtime_contract_version": 1,
        "core_or_optional": "optional",
        "description": f"Scaffolded tool pack: {toolpack_id}",
        "module_prefix": f"tool_packs.{toolpack_id}",
        "health": {
            "module": f"tool_packs.{toolpack_id}.health",
            "function": "check_health",
        },
        "tools": [
            {
                "tool": f"{namespace}/{tool_name}",
                "namespace": namespace,
                "action": tool_name,
                "module": f"tool_packs.{toolpack_id}.tools",
                "function": tool_name,
                "side_effect": side_effect,
                "requires_approval": side_effect,
                "allow_live": False,
                "allow_live_side_effect": False,
                "live_guardrail": "blocked",
                "output_type": output_type,
                "required_args": required_args,
                "optional_args": optional_args,
                "arg_types": arg_types,
                "dry_run_executes": not side_effect,
            }
        ],
    }
    return json.dumps(descriptor, indent=2, ensure_ascii=True) + "\n"


def render_tools_py(*, toolpack_id: str, namespace: str, tool_name: str, side_effect: bool = False) -> str:
    output_type = f"{namespace}_{tool_name}_result"
    tool_key = f"{namespace}/{tool_name}"

    if side_effect:
        return f'''from __future__ import annotations

from typing import Any


def {tool_name}(recipient: str, subject: str, body: str, dry_run: bool = True) -> dict[str, Any]:
    """Side-effect scaffold.

    This function must remain dry-run only until explicit live support is implemented.
    """
    if not dry_run:
        return {{
            "ok": False,
            "type": "{output_type}",
            "data": {{}},
            "evidence": {{
                "tool": "{tool_key}",
                "dry_run": False,
                "sent": False,
            }},
            "error": "LIVE_SIDE_EFFECT_NOT_IMPLEMENTED",
        }}

    return {{
        "ok": True,
        "type": "{output_type}",
        "data": {{
            "recipient": recipient,
            "subject": subject,
            "sent": False,
            "dry_run": True,
        }},
        "evidence": {{
            "tool": "{tool_key}",
            "dry_run": True,
            "sent": False,
        }},
        "error": "",
    }}
'''
    else:
        return f'''from __future__ import annotations

from typing import Any


def {tool_name}(query: str, limit: int = 10) -> dict[str, Any]:
    """Safe read-only scaffolded tool.

    Replace this implementation with real tool logic.
    """
    return {{
        "ok": True,
        "type": "{output_type}",
        "data": {{
            "query": query,
            "limit": limit,
            "results": [],
        }},
        "evidence": {{
            "tool": "{tool_key}",
            "mode": "scaffold",
        }},
        "error": "",
    }}
'''


def render_health_py(*, toolpack_id: str) -> str:
    return f'''from __future__ import annotations

from typing import Any


def check_health(*, live: bool = False) -> dict[str, Any]:
    """Health check for {toolpack_id}.

    This check must not call external systems.
    Replace with a real connectivity or config check when implementing live logic.
    """
    return {{
        "ok": True,
        "toolpack_id": "{toolpack_id}",
        "status": "healthy",
        "severity": "info",
        "message": "Scaffold health check passed.",
        "details": {{
            "live": live,
            "scaffold": True,
        }},
        "errors": [],
        "warnings": ["This is a scaffolded health check. Replace with real logic."],
    }}
'''


def render_readme(*, toolpack_id: str, namespace: str, tool_name: str, side_effect: bool = False) -> str:
    tool_key = f"{namespace}/{tool_name}"
    effect_note = "side-effect (requires approval, live execution blocked)" if side_effect else "safe read-only"
    return f"""# {toolpack_id.replace("_", " ").title()} Tool Pack

Scaffolded tool pack for `{toolpack_id}`.

This pack is **excluded from the default demo path**. It is optional and must be explicitly enabled.

## Tool

- `{tool_key}` — {effect_note}

## Safety

- Side effects: `{"true" if side_effect else "false"}`
- Requires approval: `{"true" if side_effect else "false"}`
- Live execution: blocked by default
- Live side effects: blocked

## Usage

Add to `config/enabled_toolpacks.json` to enable:

```json
{{
  "enabled_toolpacks": ["tool_packs/{toolpack_id}/toolpack.json"],
  "allow_optional_toolpacks": true
}}
```

Then run:

```bash
taskframe tools validate tool_packs/{toolpack_id}/toolpack.json
taskframe tools test tool_packs/{toolpack_id}/toolpack.json
```

## Development

Replace `tools.py` with real implementation before enabling in production.

Health checks in `health.py` must not call external systems.
"""


def render_contract_tests(*, toolpack_id: str, namespace: str, tool_name: str, side_effect: bool = False) -> str:
    return f'''"""Contract tests for {toolpack_id} tool pack."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.toolpack_contract_runner import run_toolpack_contract_tests

TOOLPACK_JSON = Path("tool_packs/{toolpack_id}/toolpack.json")


@pytest.fixture(scope="module")
def result():
    return run_toolpack_contract_tests(TOOLPACK_JSON, include_manifest_smoke=True)


def test_contract_result_ok(result):
    assert result["ok"] is True, f"Contract test failed: {{result.get('errors', [])}}"


def test_contract_status_pass(result):
    assert result["status"] == "PASS"


def test_descriptor_valid(result):
    check = next((c for c in result["checks"] if c["id"] == "descriptor_valid"), None)
    assert check is not None
    assert check["status"] == "PASS"


def test_import_ok(result):
    tool_check = next((t for t in result["tool_checks"] if t["tool"] == "{namespace}/{tool_name}"), None)
    assert tool_check is not None
    assert tool_check["import_ok"] is True


def test_smoke_ok(result):
    tool_check = next((t for t in result["tool_checks"] if t["tool"] == "{namespace}/{tool_name}"), None)
    assert tool_check is not None
    assert tool_check["smoke_ok"] is True


def test_result_shape_ok(result):
    tool_check = next((t for t in result["tool_checks"] if t["tool"] == "{namespace}/{tool_name}"), None)
    assert tool_check is not None
    assert tool_check["result_shape_ok"] is True


def test_safety_ok(result):
    tool_check = next((t for t in result["tool_checks"] if t["tool"] == "{namespace}/{tool_name}"), None)
    assert tool_check is not None
    assert tool_check["safety_ok"] is True
'''


def render_health_tests(*, toolpack_id: str) -> str:
    return f'''"""Health tests for {toolpack_id} tool pack."""
from __future__ import annotations

import importlib

import pytest


def test_health_module_importable():
    module = importlib.import_module("tool_packs.{toolpack_id}.health")
    assert hasattr(module, "check_health")


def test_health_check_passes():
    from tool_packs.{toolpack_id}.health import check_health

    result = check_health(live=False)
    assert isinstance(result, dict)
    assert result.get("ok") is True


def test_health_check_returns_required_fields():
    from tool_packs.{toolpack_id}.health import check_health

    result = check_health(live=False)
    for key in ("ok", "toolpack_id", "status", "message"):
        assert key in result, f"Missing key: {{key}}"


def test_health_check_does_not_call_external_systems():
    from tool_packs.{toolpack_id}.health import check_health

    result = check_health(live=False)
    assert result.get("ok") is True
'''


def render_tool_tests(*, toolpack_id: str, namespace: str, tool_name: str, side_effect: bool = False) -> str:
    if side_effect:
        call_args = 'recipient="test@example.com", subject="Test", body="Test body", dry_run=True'
        dry_run_check = '''
def test_side_effect_live_not_implemented():
    from tool_packs.{toolpack_id}.tools import {tool_name}

    result = {tool_name}(recipient="x@example.com", subject="S", body="B", dry_run=False)
    assert result.get("ok") is False
    assert "LIVE_SIDE_EFFECT_NOT_IMPLEMENTED" in result.get("error", "")
'''.format(toolpack_id=toolpack_id, tool_name=tool_name)
    else:
        call_args = 'query="TEST", limit=1'
        dry_run_check = ""

    return f'''"""Tool tests for {toolpack_id} tool pack."""
from __future__ import annotations

import importlib

import pytest


def test_tools_module_importable():
    module = importlib.import_module("tool_packs.{toolpack_id}.tools")
    assert hasattr(module, "{tool_name}")


def test_tool_returns_ok():
    from tool_packs.{toolpack_id}.tools import {tool_name}

    result = {tool_name}({call_args})
    assert isinstance(result, dict)
    assert result.get("ok") is True


def test_tool_returns_correct_type():
    from tool_packs.{toolpack_id}.tools import {tool_name}

    result = {tool_name}({call_args})
    assert result.get("type") == "{namespace}_{tool_name}_result"


def test_tool_result_shape():
    from tool_packs.{toolpack_id}.tools import {tool_name}

    result = {tool_name}({call_args})
    for key in ("ok", "type", "data", "evidence", "error"):
        assert key in result, f"Missing key: {{key}}"
{dry_run_check}'''


def render_example_manifest(*, toolpack_id: str, namespace: str, tool_name: str, side_effect: bool = False) -> str:
    manifest_id = f"toolpack.{toolpack_id}.smoke_{tool_name}"
    if side_effect:
        step_command = f'[t:{namespace}/{tool_name} -> {tool_name}_result] recipient="test@example.com"; subject="Smoke test"; body="Smoke test body"'
        completion = {
            "success_state": "WAITING_FOR_EXECUTE",
            "pending_actions": 1,
        }
        validations: list[dict[str, Any]] = []
    else:
        step_command = f'[t:{namespace}/{tool_name} -> {tool_name}_result] query="TEST"; limit=1'
        completion = {
            "success_outputs": [f"{tool_name}_result"],
        }
        validations = [
            {
                "id": f"{tool_name}_output_exists",
                "type": "output_exists",
                "output": f"{tool_name}_result",
            }
        ]

    manifest: dict[str, Any] = {
        "manifest_id": manifest_id,
        "name": f"Smoke Test {toolpack_id} {tool_name}",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {
                "id": tool_name,
                "command": step_command,
            }
        ],
        "validations": validations,
        "completion": completion,
    }
    return json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"


def _validate_scaffold_args(toolpack_id: str, namespace: str | None, tool_name: str | None) -> list[str]:
    errors: list[str] = []
    if not _SNAKE_RE.match(toolpack_id):
        errors.append(f"toolpack_id must be snake_case (lowercase letters, digits, underscores, must start with a letter): {toolpack_id!r}")
    if namespace and not _SNAKE_RE.match(namespace):
        errors.append(f"namespace must be snake_case: {namespace!r}")
    if tool_name and not _SNAKE_RE.match(tool_name):
        errors.append(f"tool_name must be snake_case: {tool_name!r}")
    return errors
