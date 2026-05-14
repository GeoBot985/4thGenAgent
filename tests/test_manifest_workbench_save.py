from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.manifest_workbench import (
    list_manifest_catalog,
    load_manifest_for_workbench,
    manifest_filename_for_id,
    new_manifest_template,
    save_manifest_json_text,
    validate_manifest_json_text,
)


def _valid_manifest() -> dict:
    return {
        "manifest_id": "workbench.save_test",
        "name": "Workbench Save Test",
        "version": 1,
        "trigger": {"type": "manual"},
        "inputs": [],
        "steps": [
            {"id": "extract_order_ref", "command": "[q:extract_order_ref -> order_ref] text=$inputs.message"},
        ],
        "validations": [],
        "completion": {"success_outputs": ["order_ref"]},
        "live_execution": {"enabled": False, "allowed_tools": [], "requires_approval": True},
    }


class ManifestWorkbenchSaveTests(unittest.TestCase):
    def test_new_manifest_template_is_valid_shape(self):
        template = new_manifest_template()
        self.assertEqual(template["manifest_id"], "example.new_manifest")
        self.assertEqual(template["name"], "New Manifest")
        self.assertEqual(template["version"], 1)
        self.assertIn("trigger", template)
        self.assertIn("steps", template)
        self.assertIn("completion", template)
        self.assertIn("live_execution", template)

    def test_manifest_filename_for_id_sanitizes_manifest_id(self):
        self.assertEqual(manifest_filename_for_id("customer.message_status_check"), "customer_message_status_check.manifest.json")

    def test_validate_manifest_json_text_accepts_valid_manifest(self):
        result = validate_manifest_json_text(json.dumps(_valid_manifest()))
        self.assertTrue(result["ok"])
        self.assertEqual(result["manifest_id"], "workbench.save_test")
        self.assertTrue(result["validated"])

    def test_validate_manifest_json_text_rejects_invalid_json(self):
        result = validate_manifest_json_text("{not json")
        self.assertFalse(result["ok"])
        self.assertFalse(result["validated"])
        self.assertIn("Invalid JSON", result["error"])

    def test_validate_manifest_json_text_rejects_missing_required_fields(self):
        bad = {"manifest_id": "workbench.save_test", "name": "Broken"}
        result = validate_manifest_json_text(json.dumps(bad))
        self.assertFalse(result["ok"])
        self.assertFalse(result["validated"])
        self.assertIn("Missing required manifest fields", result["error"])

    def test_save_manifest_json_text_writes_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_dir = Path(tmp) / "manifests"
            result = save_manifest_json_text(json.dumps(_valid_manifest()), manifest_dir=str(manifest_dir))
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["path"]).is_file())
            self.assertIn("workbench_save_test.manifest.json", result["path"])

    def test_save_manifest_json_text_blocks_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_dir = Path(tmp) / "manifests"
            result = save_manifest_json_text(json.dumps({"manifest_id": "workbench.save_test", "name": "Broken"}), manifest_dir=str(manifest_dir))
            self.assertFalse(result["ok"])
            self.assertIn("Missing required manifest fields", result["error"])

    def test_save_manifest_json_text_blocks_unexpected_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_dir = Path(tmp) / "manifests"
            manifest_text = json.dumps(_valid_manifest())
            first = save_manifest_json_text(manifest_text, manifest_dir=str(manifest_dir))
            self.assertTrue(first["ok"])
            second = save_manifest_json_text(manifest_text, manifest_dir=str(manifest_dir))
            self.assertFalse(second["ok"])
            self.assertIn("already exists", second["error"])

    def test_saved_manifest_can_be_loaded_from_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_dir = Path(tmp) / "manifests"
            saved = save_manifest_json_text(json.dumps(_valid_manifest()), manifest_dir=str(manifest_dir))
            self.assertTrue(saved["ok"])
            catalog = list_manifest_catalog(str(manifest_dir))
            self.assertTrue(any(item.get("manifest_id") == "workbench.save_test" for item in catalog))
            loaded = load_manifest_for_workbench(saved["path"])
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["manifest_id"], "workbench.save_test")

