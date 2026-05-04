from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.llm_config import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    build_llm_adapter,
)


class LLMConfigTests(unittest.TestCase):
    def test_build_llm_adapter_defaults_to_granite_ollama(self):
        adapter = build_llm_adapter(provider="ollama")
        self.assertEqual(adapter.provider, "ollama")
        self.assertEqual(adapter.model, DEFAULT_OLLAMA_MODEL)
        self.assertEqual(adapter.base_url, DEFAULT_OLLAMA_BASE_URL)

    def test_build_llm_adapter_fake(self):
        adapter = build_llm_adapter(provider="fake")
        self.assertEqual(adapter.provider, "fake")
        self.assertEqual(adapter.model, "fake")

    def test_build_llm_adapter_env_override(self):
        with patch.dict(
            os.environ,
            {
                "TASKFRAME_LLM_PROVIDER": "ollama",
                "TASKFRAME_OLLAMA_MODEL": "granite3.3:8b",
                "TASKFRAME_OLLAMA_BASE_URL": "http://localhost:11434",
                "TASKFRAME_OLLAMA_TIMEOUT_SECONDS": "45",
            },
            clear=False,
        ):
            adapter = build_llm_adapter()
            self.assertEqual(adapter.provider, "ollama")
            self.assertEqual(adapter.model, "granite3.3:8b")
            self.assertEqual(adapter.base_url, "http://localhost:11434")
            self.assertEqual(adapter.timeout_seconds, 45)


if __name__ == "__main__":
    unittest.main()
