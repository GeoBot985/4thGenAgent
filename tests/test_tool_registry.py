import unittest

from runtime.errors import ToolArgumentError, ToolNotRegisteredError
from runtime.tool_registry import (
    coerce_tool_args,
    get_tool_spec,
    is_registered_tool,
    tool_key,
    validate_tool_args,
)


class ToolRegistryTests(unittest.TestCase):
    def test_registered_tools_exist(self):
        self.assertTrue(is_registered_tool("g", "check"))
        self.assertTrue(is_registered_tool("wa", "send"))
        self.assertTrue(is_registered_tool("gb", "open_courts"))

    def test_unknown_tool_fails(self):
        with self.assertRaises(ToolNotRegisteredError):
            get_tool_spec("unknown", "tool")

    def test_required_args_pass(self):
        spec = get_tool_spec("g", "send")
        validate_tool_args(spec, {"to": "a@b.com", "subject": "Hello", "body": "World"})

    def test_missing_required_arg_fails(self):
        spec = get_tool_spec("g", "send")
        with self.assertRaises(ToolArgumentError):
            validate_tool_args(spec, {"to": "a@b.com", "subject": "Hello"})

    def test_int_coercion_works(self):
        spec = get_tool_spec("g", "check")
        coerced = coerce_tool_args(spec, {"max_results": "5"})
        self.assertEqual(coerced["max_results"], 5)

    def test_bool_coercion_works(self):
        spec = get_tool_spec("gb", "book")
        coerced = coerce_tool_args(
            spec,
            {"confirm": "false", "slowmo": "100", "date": "2026-05-01", "time_value": "18:00", "court": "Court 1"},
        )
        self.assertFalse(coerced["confirm"])
        self.assertEqual(coerced["slowmo"], 100)

    def test_invalid_int_coercion_fails(self):
        spec = get_tool_spec("g", "check")
        with self.assertRaises(ToolArgumentError):
            coerce_tool_args(spec, {"max_results": "not-an-int"})

    def test_tool_key_returns_namespace_action_string(self):
        self.assertEqual(tool_key("g", "check"), "g/check")

    def test_specific_registry_values(self):
        spec = get_tool_spec("g", "check")
        self.assertEqual(spec["function"], "gmail_check")
        self.assertFalse(spec["side_effect"])
        self.assertTrue(spec["allow_live"])

        spec = get_tool_spec("wa", "send")
        self.assertTrue(spec["requires_approval"])
        self.assertFalse(spec["allow_live"])


if __name__ == "__main__":
    unittest.main()
