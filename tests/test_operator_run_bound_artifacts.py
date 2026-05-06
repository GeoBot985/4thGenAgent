from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.operator_artifacts import artifact_paths_match_frame, build_artifact_state, get_openable_artifacts


class OperatorRunBoundArtifactTests(unittest.TestCase):
    def test_no_active_frame_has_no_openable_artifacts(self):
        state = build_artifact_state(None, None)

        self.assertFalse(state["has_active_run"])
        self.assertEqual(get_openable_artifacts(state), [])

    def test_artifact_state_uses_active_frame_id(self):
        state = build_artifact_state("frame-123", {"frame_id": "frame-123", "markdown_path": "", "html_path": "", "evidence_bundle_path": ""})

        self.assertEqual(state["frame_id"], "frame-123")
        self.assertTrue(state["has_active_run"])

    def test_open_evidence_disabled_when_report_missing(self):
        state = build_artifact_state("frame-123", None)

        self.assertFalse(state["report_generated"])
        self.assertFalse(state["evidence_generated"])
        self.assertEqual(get_openable_artifacts(state), [])

    def test_stale_artifact_paths_do_not_match_current_frame(self):
        state = build_artifact_state("frame-123", {"frame_id": "frame-123", "markdown_path": "", "html_path": "", "evidence_bundle_path": ""})
        state["frame_id"] = "frame-999"

        self.assertFalse(artifact_paths_match_frame("frame-123", state))

    def test_generated_report_exposes_html_bundle_and_output_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_markdown = root / "run_report.md"
            report_html = root / "run_report.html"
            evidence_bundle = root / "evidence_bundle.json"
            report_markdown.write_text("# report", encoding="utf-8")
            report_html.write_text("<html></html>", encoding="utf-8")
            evidence_bundle.write_text("{}", encoding="utf-8")

            state = build_artifact_state(
                "frame-123",
                {
                    "frame_id": "frame-123",
                    "markdown_path": str(report_markdown),
                    "html_path": str(report_html),
                    "evidence_bundle_path": str(evidence_bundle),
                },
            )
            items = get_openable_artifacts(state)

            kinds = {item["kind"] for item in items}
            self.assertIn("html_report", kinds)
            self.assertIn("evidence_bundle", kinds)
            self.assertIn("folder", kinds)


if __name__ == "__main__":
    unittest.main()
