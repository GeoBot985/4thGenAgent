from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import unittest

from src.manifest_manual import manifest_manual_path, open_manifest_manual


ROOT = Path(__file__).resolve().parents[1]
MANUAL_PATH = ROOT / "docs" / "manifest_building_manual.md"
UI_SOURCE = ROOT / "src" / "operator_ui.py"


class ManifestManualTests(unittest.TestCase):
    def test_manifest_building_manual_exists(self):
        self.assertTrue(MANUAL_PATH.is_file())
        self.assertEqual(manifest_manual_path(), MANUAL_PATH)

    def test_manifest_manual_contains_plain_english_overview(self):
        text = MANUAL_PATH.read_text(encoding="utf-8")
        self.assertIn("A manifest is the instruction file for an autonomous business worker.", text)
        self.assertIn("In simple terms: the manifest is the worker's SOP.", text)

    def test_manifest_manual_contains_command_reference(self):
        text = MANUAL_PATH.read_text(encoding="utf-8")
        self.assertIn("Command Reference", text)
        self.assertIn("[q:extract_order_ref -> order_ref]", text)
        self.assertIn("[t:sheet/read_range -> payments_sheet]", text)

    def test_manifest_manual_contains_frontier_llm_authoring_guide(self):
        text = MANUAL_PATH.read_text(encoding="utf-8")
        self.assertIn("Frontier LLM Authoring Guide", text)
        self.assertIn("Do not invent tools.", text)
        self.assertIn("LLM self-check checklist", text)

    def test_manifest_manual_contains_workbench_testing_steps(self):
        text = MANUAL_PATH.read_text(encoding="utf-8")
        self.assertIn("How to Test a Manifest in the Workbench", text)
        self.assertIn("Open Manifest Workbench", text)
        self.assertIn("Create/open run report", text)

    def test_manifest_manual_contains_saving_section(self):
        text = MANUAL_PATH.read_text(encoding="utf-8")
        self.assertIn("Saving New Manifests", text)
        self.assertIn("Do not save manifests that require live external credentials", text)

    def test_manifest_manual_open_helper_returns_path(self):
        with patch("src.manifest_manual.os.startfile", create=True) as startfile:
            result = open_manifest_manual()
        self.assertTrue(result["ok"])
        self.assertEqual(Path(result["path"]), MANUAL_PATH)
        startfile.assert_called_once()

    def test_operator_ui_exposes_manifest_manual_button(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        self.assertIn("Open manifest manual", source)
