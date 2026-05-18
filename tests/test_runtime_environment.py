from __future__ import annotations

import importlib

import pytest


def test_default_runtime_environment_is_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("runtime.runtime_environment")
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    monkeypatch.setattr(module, "load_runtime_profile", lambda path=None: {"environment": "demo"}, raising=False)
    importlib.reload(module)
    monkeypatch.setattr(module, "load_runtime_profile", lambda path=None: {"environment": "demo"}, raising=False)
    assert module.resolve_runtime_environment() == "demo"


def test_env_var_overrides_default_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("runtime.runtime_environment")
    monkeypatch.setenv("TASKFRAME_ENV", "test")
    monkeypatch.setattr(module, "load_runtime_profile", lambda path=None: {"environment": "demo"}, raising=False)
    assert module.resolve_runtime_environment() == "test"


def test_explicit_environment_overrides_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("runtime.runtime_environment")
    monkeypatch.setenv("TASKFRAME_ENV", "release")
    monkeypatch.setattr(module, "load_runtime_profile", lambda path=None: {"environment": "demo"}, raising=False)
    assert module.resolve_runtime_environment("dev") == "dev"


def test_invalid_runtime_environment_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("runtime.runtime_environment")
    monkeypatch.delenv("TASKFRAME_ENV", raising=False)
    with pytest.raises(ValueError):
        module.resolve_runtime_environment("not-a-real-env")
