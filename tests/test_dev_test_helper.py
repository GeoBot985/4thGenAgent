import os
import pytest

def test_dev_test_helper_exists():
    assert os.path.exists("tools/run_dev_tests.py")

def test_dev_test_helper_content():
    with open("tools/run_dev_tests.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "run_bounded_validation.py" in content
    assert "local" in content
    assert "run_release_candidate_verification.py" not in content
    assert "python -m pytest" not in content
    assert 'subprocess.run' in content
    assert 'bounded local validation' in content

def test_docs_mention_dev_tests():
    doc_files = ["README.md", "docs/cli_reference.md", "docs/quickstart.md", "CLAUDE.md"]
    found = False
    for doc in doc_files:
        if os.path.exists(doc):
            with open(doc, "r", encoding="utf-8") as f:
                content = f.read()
                if "python tools/run_bounded_validation.py local" in content or "python tools/run_bounded_validation.py quick" in content:
                    found = True
                    break
    assert found, "Documentation does not mention bounded validation runner"
