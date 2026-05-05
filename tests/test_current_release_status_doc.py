import json
from pathlib import Path


def test_current_release_status_doc_exists_after_verifier() -> None:
    assert Path("docs/current_release_status.md").is_file()


def test_current_release_status_matches_verifier_output() -> None:
    verifier = Path("runtime_data/audit/release_candidate_verification.json")
    status = Path("runtime_data/audit/release_status_latest.json")
    doc = Path("docs/current_release_status.md")
    assert verifier.is_file()
    assert status.is_file()
    assert doc.is_file()

    verifier_data = json.loads(verifier.read_text(encoding="utf-8"))
    status_data = json.loads(status.read_text(encoding="utf-8"))
    text = doc.read_text(encoding="utf-8")

    assert verifier_data["verdict"] == status_data["verdict"]
    assert verifier_data["generated_at"] == status_data["verification_date"]
    assert verifier_data["verdict"] in text
    assert "Golden Demo Summary" in text
    assert "Release Verifier Checks" in text
