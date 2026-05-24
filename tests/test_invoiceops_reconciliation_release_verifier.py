from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import tools.run_release_candidate_verification as verifier


def test_release_verifier_has_invoiceops_post_write_reconciliation_check(monkeypatch, tmp_path: Path) -> None:
    reconcile_json = tmp_path / "reconcile.json"
    reconcile_md = tmp_path / "reconcile.md"
    reconcile_json.write_text("{}", encoding="utf-8")
    reconcile_md.write_text("# reconcile", encoding="utf-8")
    pack_json = tmp_path / "pack.json"
    pack_md = tmp_path / "pack.md"
    pack_json.write_text("{}", encoding="utf-8")
    pack_md.write_text("# pack", encoding="utf-8")

    reconcile_payload = {
        "ok": False,
        "status": "MISSING_POSTING_EVIDENCE",
        "invoice_number": "fake",
        "checks": [],
        "report_paths": {"json": str(reconcile_json), "markdown": str(reconcile_md)},
    }
    pack_payload = {
        "ok": True,
        "pack_id": "ACP-fake",
        "invoice_number": "fake",
        "sections": {
            "invoice_source": [],
            "extraction": [],
            "validation": [],
            "matching": [],
            "posting": [],
            "reconciliation": [],
            "rollback": [],
            "audit_trail": [],
        },
            "reconciliation": reconcile_payload,
            "report_paths": {"json": str(pack_json), "markdown": str(pack_md)},
        }

    def _fake_run(command, **kwargs):
        joined = " ".join(command)
        if "invoiceops reconcile" in joined:
            return SimpleNamespace(returncode=1, stdout=json.dumps(reconcile_payload), stderr="")
        if "invoiceops evidence-pack" in joined:
            return SimpleNamespace(returncode=0, stdout=json.dumps(pack_payload), stderr="")
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(verifier.subprocess, "run", _fake_run)

    result = verifier._check_invoiceops_post_write_reconciliation()

    assert result["status"] == "PASS"
    assert result["missing"] == []
    assert result["failures"] == []
