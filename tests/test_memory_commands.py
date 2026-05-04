import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.command_parser import parse_command
from runtime.errors import CommandParseError, MemoryCommandError
from runtime.memory_commands import MemoryCommandRunner
from runtime.memory_store import MemoryStore
from runtime.models import Manifest, ManifestStep
from runtime.taskframe import create_taskframe


def build_manifest(command: str, manifest_id: str = "memory.test", inputs: list | None = None) -> Manifest:
    parsed = parse_command(command)
    return Manifest(
        manifest_id=manifest_id,
        name=manifest_id,
        version=1,
        trigger={"type": "manual"},
        inputs=inputs or [],
        steps=[ManifestStep(id="step_1", command=command, parsed_command=parsed)],
        validations=[],
        completion={"success_outputs": ["output"]},
        raw={},
    )


class MemoryCommandTests(unittest.TestCase):
    def test_parser_parses_m_get(self):
        parsed = parse_command('[m:get -> supplier_pref] key="supplier.ABC.preferred_channel"')
        self.assertEqual(parsed.kind, "memory")
        self.assertEqual(parsed.action, "get")

    def test_parser_parses_m_set(self):
        parsed = parse_command('[m:set -> saved_fact] key="supplier.ABC.lead_time_days"; value="5"')
        self.assertEqual(parsed.kind, "memory")
        self.assertEqual(parsed.action, "set")

    def test_parser_parses_m_list(self):
        parsed = parse_command('[m:list -> supplier_facts] prefix="supplier.ABC."')
        self.assertEqual(parsed.kind, "memory")
        self.assertEqual(parsed.action, "list")

    def test_parser_rejects_m_get_without_output_alias(self):
        with self.assertRaises(CommandParseError):
            parse_command('[m:get] key="x"')

    def test_m_get_writes_output_to_taskframe(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.preferred_channel", "email")
            frame = create_taskframe(build_manifest('[m:get -> memory_value] key=$inputs.key', inputs=["key"]), inputs={"key": "supplier.ABC.preferred_channel"})
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["memory_value"]["found"], True)
            self.assertTrue(any(item.event_type == "MEMORY_GET" for item in frame.audit))
            self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_m_get_missing_key_writes_found_false_output(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(build_manifest('[m:get -> memory_value] key=$inputs.key', inputs=["key"]), inputs={"key": "supplier.ABC.preferred_channel"})
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            runner.run_step(frame, frame.steps[0])

            self.assertFalse(frame.outputs["memory_value"]["found"])
            self.assertIsNone(frame.outputs["memory_value"]["value"])

    def test_m_set_writes_output_to_taskframe_and_persists_value(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(
                build_manifest('[m:set -> saved_pref] key=$inputs.key; value=$inputs.value', inputs=["key", "value"]),
                inputs={"key": "supplier.ABC.preferred_channel", "value": "email"},
            )
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["saved_pref"]["stored"], True)
            self.assertEqual(store.get("supplier.ABC.preferred_channel").value, "email")

    def test_m_list_writes_matching_items_to_taskframe(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            store.set("supplier.ABC.lead_time_days", "5")
            store.set("supplier.ABC.preferred_channel", "email")
            store.set("family.calendar.default", "Family")
            frame = create_taskframe(build_manifest('[m:list -> supplier_facts] prefix=$inputs.prefix', inputs=["prefix"]), inputs={"prefix": "supplier.ABC."})
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            result = runner.run_step(frame, frame.steps[0])

            self.assertTrue(result.ok)
            self.assertEqual(frame.outputs["supplier_facts"]["count"], 2)
            self.assertEqual(len(frame.outputs["supplier_facts"]["items"]), 2)

    def test_m_delete_fails_closed(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(build_manifest('[m:delete -> deleted] key="supplier.ABC.lead_time_days"'))
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            with self.assertRaises(MemoryCommandError):
                runner.run_step(frame, frame.steps[0])
            self.assertEqual(frame.steps[0].status, "FAILED")

    def test_memory_command_marks_step_completed_on_success(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(build_manifest('[m:set -> saved_pref] key="a.b"; value="c"'))
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            runner.run_step(frame, frame.steps[0])

            self.assertEqual(frame.steps[0].status, "COMPLETED")

    def test_memory_command_marks_step_failed_on_error(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(build_manifest('[m:set -> saved_pref] key="a b"; value="c"'))
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            with self.assertRaises(MemoryCommandError):
                runner.run_step(frame, frame.steps[0])
            self.assertEqual(frame.steps[0].status, "FAILED")

    def test_memory_command_resolves_inputs_refs(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(
                build_manifest('[m:set -> saved_pref] key=$inputs.key; value=$inputs.value', inputs=["key", "value"]),
                inputs={"key": "supplier.ABC.preferred_channel", "value": "email"},
            )
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            runner.run_step(frame, frame.steps[0])

            self.assertEqual(store.get("supplier.ABC.preferred_channel").value, "email")

    def test_memory_command_resolves_event_refs(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(
                build_manifest('[m:set -> saved_pref] key=$event.key; value=$event.value'),
                trigger={"key": "supplier.ABC.preferred_channel", "value": "email"},
            )
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            runner.run_step(frame, frame.steps[0])

            self.assertEqual(store.get("supplier.ABC.preferred_channel").value, "email")

    def test_memory_command_records_audit_event(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory_store.json")
            frame = create_taskframe(build_manifest('[m:set -> saved_pref] key="a.b"; value="c"'))
            frame.state = "RUNNING"
            runner = MemoryCommandRunner(store)

            runner.run_step(frame, frame.steps[0])

            self.assertTrue(any(item.event_type == "MEMORY_SET" for item in frame.audit))


if __name__ == "__main__":
    unittest.main()
