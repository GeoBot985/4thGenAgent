from dataclasses import asdict
import unittest

from runtime.taskframe import tool_result_error, tool_result_ok


class ToolResultTests(unittest.TestCase):
    def test_tool_result_ok_creates_ok_result(self):
        result = tool_result_ok("email_list", data=[{"id": 1}])
        self.assertTrue(result.ok)
        self.assertEqual(result.type, "email_list")
        self.assertEqual(result.data, [{"id": 1}])

    def test_tool_result_error_creates_error_result(self):
        result = tool_result_error("email_list", "failed")
        self.assertFalse(result.ok)
        self.assertEqual(result.type, "email_list")
        self.assertEqual(result.error, "failed")

    def test_tool_result_supports_evidence_and_metadata(self):
        result = tool_result_ok(
            "email_list",
            data=[],
            evidence=[{"source": "gmail"}],
            metadata={"page": 1},
        )
        self.assertEqual(result.evidence, [{"source": "gmail"}])
        self.assertEqual(result.metadata, {"page": 1})

    def test_tool_result_serializes_with_asdict(self):
        result = tool_result_ok(
            "email_list",
            data=[],
            evidence=[{"source": "gmail"}],
            metadata={"page": 1},
        )
        self.assertEqual(asdict(result)["type"], "email_list")


if __name__ == "__main__":
    unittest.main()

