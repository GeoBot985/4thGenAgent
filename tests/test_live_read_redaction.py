from __future__ import annotations

import pytest
from runtime.live_read_proof import (
    redact_credential_evidence,
    redact_proof_result,
)

_REDACTED = "[REDACTED]"


def test_redact_credential_removes_access_token():
    cred = {"access_token": "ya29.secret", "credentials_present": True}
    result = redact_credential_evidence(cred)
    assert result["access_token"] == _REDACTED


def test_redact_credential_removes_refresh_token():
    cred = {"refresh_token": "1//secret", "credentials_present": True}
    result = redact_credential_evidence(cred)
    assert result["refresh_token"] == _REDACTED


def test_redact_credential_removes_client_secret():
    cred = {"client_secret": "GOCSPX-secret", "credentials_present": True}
    result = redact_credential_evidence(cred)
    assert result["client_secret"] == _REDACTED


def test_redact_credential_removes_client_id():
    cred = {"client_id": "1234.apps.googleusercontent.com"}
    result = redact_credential_evidence(cred)
    assert result["client_id"] == _REDACTED


def test_redact_credential_removes_raw_json():
    cred = {"raw_json": '{"client_secret": "s"}', "credentials_present": True}
    result = redact_credential_evidence(cred)
    assert result["raw_json"] == _REDACTED


def test_redact_credential_removes_email_body():
    cred = {"email_body": "sensitive content", "credentials_present": True}
    result = redact_credential_evidence(cred)
    assert result["email_body"] == _REDACTED


def test_redact_credential_preserves_safe_fields():
    cred = {
        "credentials_present": True,
        "token_present": False,
        "token_parseable": False,
        "scopes_detected": False,
        "token_expired": "unknown",
    }
    result = redact_credential_evidence(cred)
    assert result["credentials_present"] is True
    assert result["token_present"] is False
    assert result["token_expired"] == "unknown"


def test_redact_proof_result_redacts_credential_check():
    proof = {
        "ok": True,
        "profile": "controlled_live_read",
        "credential_check": {
            "access_token": "ya29.secret",
            "credentials_present": True,
        },
        "probes": [],
    }
    result = redact_proof_result(proof)
    assert result["credential_check"]["access_token"] == _REDACTED
    assert result["credential_check"]["credentials_present"] is True


def test_redact_proof_result_redacts_probe_evidence():
    proof = {
        "ok": True,
        "credential_check": {},
        "probes": [
            {
                "probe_id": "gmail_search_readonly",
                "tool": "gmail/search",
                "status": "PASS",
                "evidence": {
                    "access_token": "ya29.secret",
                    "records_returned": 3,
                },
            }
        ],
    }
    result = redact_proof_result(proof)
    probe_ev = result["probes"][0]["evidence"]
    assert probe_ev["access_token"] == _REDACTED
    assert probe_ev["records_returned"] == 3


def test_redact_proof_result_preserves_structure():
    proof = {
        "ok": True,
        "profile": "controlled_live_read",
        "live_side_effects_performed": False,
        "credential_check": {},
        "probes": [],
    }
    result = redact_proof_result(proof)
    assert result["ok"] is True
    assert result["profile"] == "controlled_live_read"
    assert result["live_side_effects_performed"] is False
