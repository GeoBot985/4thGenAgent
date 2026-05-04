import unittest
from pathlib import Path

from runtime.manifest_loader import load_manifest


class ManifestContractTests(unittest.TestCase):
    def test_all_manifests_load_and_comply(self):
        manifests_dir = Path(__file__).resolve().parent.parent / "manifests"
        manifest_paths = sorted(manifests_dir.glob("*.manifest.json"))
        self.assertTrue(manifest_paths, "No manifest files found under manifests/")

        for manifest_path in manifest_paths:
            with self.subTest(manifest=str(manifest_path)):
                manifest = load_manifest(manifest_path)
                self.assertTrue(manifest.manifest_id)
                self.assertTrue(manifest.completion)

                step_ids = [step.id for step in manifest.steps]
                self.assertEqual(len(step_ids), len(set(step_ids)))

                for step in manifest.steps:
                    self.assertIsNotNone(step.parsed_command)


if __name__ == "__main__":
    unittest.main()
