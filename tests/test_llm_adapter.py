import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from runtime.errors import LLMProviderError, LLMOutputParseError
from runtime.llm_adapter import FakeLLMAdapter, OllamaLLMAdapter, extract_json_from_text
from runtime.models import llm_result_error, llm_result_ok


class WorkspaceResultLike:
    def __init__(self, ok: bool, action: str, output: str = "", error: str = "", payload: dict | None = None):
        self.ok = ok
        self.action = action
        self.output = output
        self.error = error
        self.payload = payload


class LLMAdapterTests(unittest.TestCase):
    def test_fake_adapter_returns_configured_response(self):
        adapter = FakeLLMAdapter({"summarize": "configured"})
        self.assertEqual(adapter.generate("prompt", metadata={"action": "summarize"}), "configured")

    def test_fake_adapter_returns_default_response(self):
        adapter = FakeLLMAdapter()
        self.assertEqual(adapter.generate("prompt", metadata={"action": "unknown"}), adapter.default_response)

    def test_ollama_adapter_builds_request_payload(self):
        adapter = OllamaLLMAdapter(model="test-model", base_url="http://127.0.0.1:11434", timeout_seconds=5)
        response_body = json.dumps({"response": "hello", "done": True}).encode("utf-8")

        with patch("runtime.llm_adapter.urllib_request.urlopen") as mock_urlopen:
            mock_response = SimpleNamespace(read=lambda: response_body)
            mock_urlopen.return_value.__enter__.return_value = mock_response
            mock_urlopen.return_value.__exit__.return_value = False

            result = adapter.generate("prompt text", system="system text")

            self.assertEqual(result, "hello")
            request = mock_urlopen.call_args[0][0]
            payload = json.loads(request.data.decode("utf-8"))
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(payload["prompt"], "prompt text")
            self.assertEqual(payload["system"], "system text")
            self.assertFalse(payload["stream"])

    def test_ollama_adapter_uses_granite_model_by_default(self):
        adapter = OllamaLLMAdapter()
        response_body = json.dumps({"response": "hello", "done": True}).encode("utf-8")

        with patch("runtime.llm_adapter.urllib_request.urlopen") as mock_urlopen:
            mock_response = SimpleNamespace(read=lambda: response_body)
            mock_urlopen.return_value.__enter__.return_value = mock_response
            mock_urlopen.return_value.__exit__.return_value = False

            adapter.generate("prompt text")

            request = mock_urlopen.call_args[0][0]
            payload = json.loads(request.data.decode("utf-8"))
            self.assertEqual(payload["model"], "granite3.3:8b")
            self.assertFalse(payload["stream"])

    def test_ollama_adapter_handles_provider_error(self):
        adapter = OllamaLLMAdapter()
        response_body = json.dumps({"error": "provider unavailable"}).encode("utf-8")

        with patch("runtime.llm_adapter.urllib_request.urlopen") as mock_urlopen:
            mock_response = SimpleNamespace(read=lambda: response_body)
            mock_urlopen.return_value.__enter__.return_value = mock_response
            mock_urlopen.return_value.__exit__.return_value = False

            with self.assertRaises(LLMProviderError):
                adapter.generate("prompt")

    def test_extract_json_from_text_parses_pure_object(self):
        parsed = extract_json_from_text('{"a": 1, "b": "x"}')
        self.assertEqual(parsed, {"a": 1, "b": "x"})

    def test_extract_json_from_text_parses_embedded_object(self):
        parsed = extract_json_from_text('Answer:\n{"a": 1, "b": "x"}\nThanks')
        self.assertEqual(parsed, {"a": 1, "b": "x"})

    def test_extract_json_from_text_parses_array(self):
        parsed = extract_json_from_text('[{"a": 1}, {"b": 2}]')
        self.assertEqual(parsed, [{"a": 1}, {"b": 2}])

    def test_extract_json_from_text_fails_invalid_json(self):
        with self.assertRaises(LLMOutputParseError):
            extract_json_from_text("not json at all")

    def test_llm_result_ok_creates_ok_result(self):
        result = llm_result_ok("summarize", "hello")
        self.assertTrue(result.ok)
        self.assertEqual(result.action, "summarize")
        self.assertEqual(result.output, "hello")

    def test_llm_result_error_creates_failed_result(self):
        result = llm_result_error("summarize", "boom")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "boom")


if __name__ == "__main__":
    unittest.main()
