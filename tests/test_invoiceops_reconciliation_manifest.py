from __future__ import annotations

import json
from pathlib import Path

from src.manifest_contract_strict import validate_manifest_strict


MANIFEST_PATH = Path("manifests/invoiceops_reconcile_posted_invoice.manifest.json")


def test_manifest_file_exists_and_is_valid_json() -> None:
    assert MANIFEST_PATH.is_file()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)


def test_manifest_includes_reconciliation_and_evidence_pack_outputs() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    step_commands = [step.get("command", "") for step in manifest.get("steps", [])]
    assert any("invoiceops/reconcile" in command for command in step_commands)
    assert any("invoiceops/evidence_pack" in command for command in step_commands)
    assert manifest.get("completion", {}).get("success_outputs") == ["reconciliation_result", "accounting_evidence_pack"]
    assert manifest.get("completion", {}).get("acceptable_statuses") == [
        "RECONCILED",
        "RECONCILED_WITH_WARNINGS",
        "MANUAL_REVIEW_REQUIRED",
    ]


def test_manifest_passes_strict_validation() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    result = validate_manifest_strict(manifest, manifest_path=str(MANIFEST_PATH), active_catalog=True)
    assert result["ok"] is True, result

