from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


SCRIPT_PATH = Path("tools/run_release_candidate_verification.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("rc_verifier_packaging_cli", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_verifier_runs_packaging_cli_check() -> None:
    module = _load_module()
    source = inspect.getsource(module)
    assert "_check_packaging_cli()" in source
    assert '"packaging_cli": "PENDING"' in source
    assert '"manifest_health_cli_strict": "PENDING"' in source
    assert "docs/cli_reference.md" in source


def test_packaging_cli_failure_blocks_release(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "tomllib",
        type(
            "TomlStub",
            (),
            {
                "loads": staticmethod(
                    lambda _text: {
                        "project": {
                            "dependencies": [],
                            "optional-dependencies": {"dev": [], "google": [], "rpa": []},
                            "scripts": {"taskframe": "wrong:entry"},
                        }
                    }
                )
            },
        ),
    )
    monkeypatch.setattr(module, "run_command", lambda *args, **kwargs: {"name": args[0], "status": "PASS", "returncode": 0, "stdout": "", "stderr": "", "stdout_tail": "", "stderr_tail": "", "command": list(args[1]), "duration_ms": 1})
    check = module._check_packaging_cli()
    assert check["status"] == "FAIL"
    assert "console_script" in check["missing"]


def test_packaging_cli_report_is_evidence() -> None:
    module = _load_module()
    check = module._check_packaging_cli()
    assert check["name"] == "packaging_cli"
    assert "commands" in check
    assert any(item["name"] == "packaging_cli_help" for item in check["commands"])
    assert any(item["name"] == "packaging_cli_manifest_health_strict" for item in check["commands"])


def test_release_verifier_has_public_quickstart_check() -> None:
    module = _load_module()
    source = inspect.getsource(module)
    assert "_check_public_quickstart_docs()" in source
    assert '"public_quickstart_docs": "PENDING"' in source
    assert "docs/quickstart.md" in source
    assert "docs/index.md" in source


def test_public_quickstart_check_passes() -> None:
    module = _load_module()
    check = module._check_public_quickstart_docs()
    assert check["name"] == "public_quickstart_docs"
    assert check["status"] == "PASS", f"public_quickstart_docs check failed: {check.get('missing')}"


def test_public_quickstart_check_blocks_release_on_failure(monkeypatch, tmp_path) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    check = module._check_public_quickstart_docs()
    assert check["status"] == "FAIL"
    assert check["missing"]
