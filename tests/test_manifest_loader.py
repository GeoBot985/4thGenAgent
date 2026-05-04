import json
import tempfile
import unittest
from pathlib import Path

from runtime.errors import ManifestValidationError
from runtime.manifest_loader import load_manifest, load_manifest_by_id, load_manifest_catalog


def write_manifest(tmpdir: Path, data: dict, filename: str = "manifest.manifest.json") -> Path:
    path = tmpdir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class ManifestLoaderTests(unittest.TestCase):
    def test_valid_manifest_loads_and_parses_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.gmail_check",
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}
                    ],
                    "validations": [
                        {"id": "unread_mail_output_exists", "type": "output_exists", "output": "unread_mail"}
                    ],
                    "completion": {
                        "success_outputs": ["unread_mail"],
                        "acceptable_empty_outputs": ["unread_mail"],
                    },
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.manifest_id, "smoke.gmail_check")
            self.assertEqual(manifest.steps[0].parsed_command.namespace, "g")
            self.assertEqual(manifest.steps[0].parsed_command.action, "check")
            self.assertEqual(manifest.steps[0].parsed_command.output_alias, "unread_mail")

    def test_missing_manifest_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [],
                    "validations": [],
                    "completion": {"success_outputs": []},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_missing_steps_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.gmail_check",
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "validations": [],
                    "completion": {"success_outputs": []},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_step_without_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.gmail_check",
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": []},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_step_without_command_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.gmail_check",
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail"}],
                    "validations": [],
                    "completion": {"success_outputs": []},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_invalid_command_inside_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.gmail_check",
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": []},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_valid_step_retry_policy_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.retry_valid",
                    "name": "Smoke Test - Retry Valid",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_flaky",
                            "retry": {"max_attempts": 2},
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].retry["max_attempts"], 2)
            self.assertEqual(manifest.steps[0].retry["delay_seconds"], 0)
            self.assertEqual(manifest.steps[0].retry["retry_on"], ["any"])

    def test_missing_retry_policy_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.retry_default",
                    "name": "Smoke Test - Retry Default",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertIsNone(manifest.steps[0].retry)

    def test_invalid_retry_max_attempts_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.retry_bad_attempts",
                    "name": "Smoke Test - Retry Bad Attempts",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_flaky",
                            "retry": {"max_attempts": 6, "retry_on": ["any"]},
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_invalid_retry_delay_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.retry_bad_delay",
                    "name": "Smoke Test - Retry Bad Delay",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_flaky",
                            "retry": {"max_attempts": 2, "delay_seconds": 31, "retry_on": ["any"]},
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_invalid_retry_retry_on_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.retry_bad_retry_on",
                    "name": "Smoke Test - Retry Bad Retry On",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_flaky",
                            "retry": {"max_attempts": 2, "retry_on": []},
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_retry_on_non_dict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.retry_bad_type",
                    "name": "Smoke Test - Retry Bad Type",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_flaky",
                            "retry": "not-a-dict",
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_valid_step_with_when_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_equals",
                    "name": "Smoke Test - Condition Equals",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["channel"],
                    "steps": [
                        {
                            "id": "set_whatsapp_memory",
                            "when": {"input": "channel", "equals": "whatsapp"},
                            "command": "[m:set -> saved_channel] key=\"test.channel\"; value=$inputs.channel",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_channel"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when, {"input": "channel", "equals": "whatsapp"})

    def test_step_with_invalid_when_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_bad",
                    "name": "Smoke Test - Condition Bad",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["channel"],
                    "steps": [
                        {
                            "id": "set_whatsapp_memory",
                            "when": {"output": "category"},
                            "command": "[m:set -> saved_channel] key=\"test.channel\"; value=$inputs.channel",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_channel"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_step_with_when_as_non_dict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_bad_type",
                    "name": "Smoke Test - Condition Bad Type",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["channel"],
                    "steps": [
                        {
                            "id": "set_whatsapp_memory",
                            "when": "not-a-dict",
                            "command": "[m:set -> saved_channel] key=\"test.channel\"; value=$inputs.channel",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_channel"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_with_compound_all_condition_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_all",
                    "name": "Smoke Test - Compound Condition All",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["channel", "priority"],
                    "steps": [
                        {
                            "id": "set_priority_channel",
                            "when": {
                                "all": [
                                    {"input": "channel", "equals": "whatsapp"},
                                    {"input": "priority", "equals": "urgent"},
                                ]
                            },
                            "command": "[m:set -> saved_branch] key=\"test.branch\"; value=\"urgent_whatsapp\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_branch"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when["all"][0]["input"], "channel")

    def test_manifest_with_compound_any_condition_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_any",
                    "name": "Smoke Test - Compound Condition Any",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["priority", "category"],
                    "steps": [
                        {
                            "id": "set_escalation_flag",
                            "when": {
                                "any": [
                                    {"input": "priority", "equals": "urgent"},
                                    {"input": "category", "equals": "complaint"},
                                ]
                            },
                            "command": "[m:set -> escalation_flag] key=\"test.escalation\"; value=\"true\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["escalation_flag"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when["any"][1]["equals"], "complaint")

    def test_manifest_with_compound_not_condition_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_not",
                    "name": "Smoke Test - Compound Condition Not",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["channel"],
                    "steps": [
                        {
                            "id": "set_non_whatsapp_channel",
                            "when": {"not": {"input": "channel", "equals": "whatsapp"}},
                            "command": "[m:set -> saved_branch] key=\"test.non_whatsapp\"; value=$inputs.channel",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_branch"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when["not"]["input"], "channel")

    def test_manifest_with_invalid_compound_condition_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_bad",
                    "name": "Smoke Test - Condition Bad",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["channel"],
                    "steps": [
                        {
                            "id": "bad_branch",
                            "when": {
                                "all": [{"input": "channel", "equals": "whatsapp"}],
                                "output": "category",
                            },
                            "command": "[m:set -> saved_channel] key=\"test.channel\"; value=$inputs.channel",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["saved_channel"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_with_numeric_condition_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_numeric_comparison",
                    "name": "Smoke Test - Numeric Comparison Condition",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["amount"],
                    "steps": [
                        {
                            "id": "set_high_value_flag",
                            "when": {"input": "amount", "greater_than": 1000},
                            "command": "[m:set -> high_value_flag] key=\"test.high_value\"; value=\"true\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["high_value_flag"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when["greater_than"], 1000)

    def test_manifest_with_date_condition_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_date_window",
                    "name": "Smoke Test - Date Window Condition",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["requested_date"],
                    "steps": [
                        {
                            "id": "set_may_window",
                            "when": {"input": "requested_date", "between_dates": ["2026-05-01", "2026-05-31"]},
                            "command": "[m:set -> date_window] key=\"test.date_window\"; value=\"may_2026\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["date_window"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when["between_dates"][0], "2026-05-01")

    def test_manifest_with_time_condition_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_time_window",
                    "name": "Smoke Test - Time Window Condition",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["requested_time"],
                    "steps": [
                        {
                            "id": "set_evening_window",
                            "when": {"input": "requested_time", "between_time": ["17:00", "20:00"]},
                            "command": "[m:set -> evening_window] key=\"test.time_window\"; value=\"evening\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["evening_window"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].when["between_time"], ["17:00", "20:00"])

    def test_manifest_with_invalid_date_condition_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_bad_date",
                    "name": "Smoke Test - Bad Date Condition",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["requested_date"],
                    "steps": [
                        {
                            "id": "bad_date",
                            "when": {"input": "requested_date", "between_dates": ["2026-05-31", "2026-05-01"]},
                            "command": "[m:set -> date_window] key=\"test.date_window\"; value=\"may_2026\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["date_window"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_with_invalid_time_condition_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_bad_time",
                    "name": "Smoke Test - Bad Time Condition",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["requested_time"],
                    "steps": [
                        {
                            "id": "bad_time",
                            "when": {"input": "requested_time", "between_time": ["17:00", "20:00:00"]},
                            "command": "[m:set -> evening_window] key=\"test.time_window\"; value=\"evening\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["evening_window"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_with_invalid_numeric_condition_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.condition_bad_numeric",
                    "name": "Smoke Test - Bad Numeric Condition",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": ["amount"],
                    "steps": [
                        {
                            "id": "bad_amount",
                            "when": {"input": "amount", "greater_than": "R1000"},
                            "command": "[m:set -> high_value_flag] key=\"test.high_value\"; value=\"true\"",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["high_value_flag"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_valid_timeout_seconds_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.timeout_valid",
                    "name": "Smoke Test - Timeout Valid",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_fast",
                            "timeout_seconds": 1,
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.steps[0].timeout_seconds, 1.0)

    def test_missing_timeout_seconds_loads_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.timeout_missing",
                    "name": "Smoke Test - Timeout Missing",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_fast",
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertIsNone(manifest.steps[0].timeout_seconds)

    def test_invalid_timeout_seconds_string_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.timeout_bad_string",
                    "name": "Smoke Test - Timeout Bad String",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_fast",
                            "timeout_seconds": "fast",
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_invalid_timeout_seconds_zero_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.timeout_bad_zero",
                    "name": "Smoke Test - Timeout Bad Zero",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_fast",
                            "timeout_seconds": 0,
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_invalid_timeout_seconds_too_large_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.timeout_bad_large",
                    "name": "Smoke Test - Timeout Bad Large",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [
                        {
                            "id": "run_fast",
                            "timeout_seconds": 999999,
                            "command": "[t:g/check -> unread_mail] max_results=5",
                        }
                    ],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_live_execution_missing_defaults_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.live_default",
                    "name": "Smoke Test - Live Default",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertFalse(manifest.live_execution["enabled"])
            self.assertEqual(manifest.live_execution["allowed_tools"], [])
            self.assertTrue(manifest.live_execution["requires_approval"])

    def test_manifest_live_execution_enabled_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.live_enabled",
                    "name": "Smoke Test - Live Enabled",
                    "version": 1,
                    "live_execution": {"enabled": True, "allowed_tools": ["sheet/write"], "requires_approval": True},
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            manifest = load_manifest(manifest_path)
            self.assertTrue(manifest.live_execution["enabled"])
            self.assertEqual(manifest.live_execution["allowed_tools"], ["sheet/write"])

    def test_manifest_live_execution_invalid_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.live_invalid_type",
                    "name": "Smoke Test - Live Invalid Type",
                    "version": 1,
                    "live_execution": "not-an-object",
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_live_execution_requires_approval_false_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.live_requires_approval_false",
                    "name": "Smoke Test - Live Requires Approval False",
                    "version": 1,
                    "live_execution": {"enabled": True, "allowed_tools": ["sheet/write"], "requires_approval": False},
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_manifest_live_execution_allowed_tools_non_list_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.live_allowed_tools_bad",
                    "name": "Smoke Test - Live Allowed Tools Bad",
                    "version": 1,
                    "live_execution": {"enabled": True, "allowed_tools": "sheet/write", "requires_approval": True},
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_load_manifest_catalog_and_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            manifest_path = write_manifest(
                tmpdir,
                {
                    "manifest_id": "smoke.gmail_check",
                    "name": "Smoke Test - Gmail Check",
                    "version": 1,
                    "trigger": {"type": "manual"},
                    "inputs": [],
                    "steps": [{"id": "check_mail", "command": "[t:g/check -> unread_mail] max_results=5"}],
                    "validations": [],
                    "completion": {"success_outputs": ["unread_mail"]},
                },
            )

            catalog = load_manifest_catalog(tmpdir)
            self.assertEqual(catalog["smoke.gmail_check"], manifest_path)

            manifest = load_manifest_by_id("smoke.gmail_check", tmpdir)
            self.assertEqual(manifest.manifest_id, "smoke.gmail_check")


if __name__ == "__main__":
    unittest.main()
