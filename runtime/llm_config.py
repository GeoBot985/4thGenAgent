from __future__ import annotations

import os

from .errors import LLMProviderError
from .llm_adapter import FakeLLMAdapter, OllamaLLMAdapter, BaseLLMAdapter


DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "granite3.3:8b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120


def build_llm_adapter(
    provider: str = "",
    model: str = "",
    base_url: str = "",
    timeout_seconds: int | None = None,
) -> BaseLLMAdapter:
    resolved_provider = provider or os.getenv("TASKFRAME_LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
    resolved_model = model or os.getenv("TASKFRAME_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    resolved_base_url = base_url or os.getenv("TASKFRAME_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    timeout_value = timeout_seconds if timeout_seconds is not None else _env_int("TASKFRAME_OLLAMA_TIMEOUT_SECONDS", DEFAULT_OLLAMA_TIMEOUT_SECONDS)

    if resolved_provider == "fake":
        return FakeLLMAdapter()
    if resolved_provider == "ollama":
        return OllamaLLMAdapter(model=resolved_model, base_url=resolved_base_url, timeout_seconds=timeout_value)
    raise LLMProviderError(f"Unknown LLM provider: {resolved_provider}")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
