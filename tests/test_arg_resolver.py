import unittest

from runtime.command_parser import parse_command
from runtime.arg_resolver import resolve_command_args, resolve_ref, resolve_value
from runtime.errors import ArgumentResolutionError
from runtime.models import TaskFrame


def make_frame() -> TaskFrame:
    return TaskFrame(
        frame_id="frame_test",
        manifest_id="manifest_test",
        state="READY",
        trigger={"date": "2026-05-01"},
        raw_input="",
        inputs={"date": "2026-05-02", "start": "17:00"},
        steps=[],
        current_step_id=None,
        attempts=[],
        outputs={
            "events": [
                {"id": "evt1", "title": "Squash"},
                {"id": "evt2", "title": "Dinner"},
            ],
            "chat": {"name": "Cornelia"},
        },
        evidence=[],
        pending_actions=[],
        executed_actions=[],
        tool_calls=[],
        llm_calls=[],
        validations=[],
        errors=[],
        completion_gate_result=None,
        final_response="",
        audit=[],
        created_at="2026-05-01T00:00:00Z",
        updated_at="2026-05-01T00:00:00Z",
    )


class ArgResolverTests(unittest.TestCase):
    def test_literal_string_remains_literal(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "hello"), "hello")

    def test_quoted_parser_result_remains_resolved_string(self):
        frame = make_frame()
        parsed = parse_command('[t:wa/send -> sent] chat="Cornelia"; message="Running late"')
        self.assertEqual(resolve_value(frame, parsed.args["message"]), "Running late")

    def test_event_ref_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$event.date"), "2026-05-01")

    def test_inputs_ref_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$inputs.date"), "2026-05-02")

    def test_output_alias_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$chat"), {"name": "Cornelia"})

    def test_output_alias_field_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$chat.name"), "Cornelia")

    def test_output_alias_first_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$events.first"), {"id": "evt1", "title": "Squash"})

    def test_output_alias_first_field_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$events.first.id"), "evt1")

    def test_output_alias_last_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$events.last"), {"id": "evt2", "title": "Dinner"})

    def test_output_alias_last_field_resolves(self):
        frame = make_frame()
        self.assertEqual(resolve_value(frame, "$events.last.id"), "evt2")

    def test_missing_event_field_fails(self):
        frame = make_frame()
        with self.assertRaises(ArgumentResolutionError):
            resolve_value(frame, "$event.missing")

    def test_missing_input_field_fails(self):
        frame = make_frame()
        with self.assertRaises(ArgumentResolutionError):
            resolve_value(frame, "$inputs.missing")

    def test_missing_output_alias_fails(self):
        frame = make_frame()
        with self.assertRaises(ArgumentResolutionError):
            resolve_value(frame, "$missing")

    def test_first_on_non_list_fails(self):
        frame = make_frame()
        with self.assertRaises(ArgumentResolutionError):
            resolve_value(frame, "$chat.first")

    def test_field_on_non_dict_fails(self):
        frame = make_frame()
        with self.assertRaises(ArgumentResolutionError):
            resolve_value(frame, "$events.first.id.name")

    def test_resolve_command_args(self):
        frame = make_frame()
        resolved = resolve_command_args(
            frame,
            {
                "date": "$event.date",
                "start": "$inputs.start",
                "title": "$chat.name",
            },
        )
        self.assertEqual(resolved["date"], "2026-05-01")
        self.assertEqual(resolved["start"], "17:00")
        self.assertEqual(resolved["title"], "Cornelia")


if __name__ == "__main__":
    unittest.main()
