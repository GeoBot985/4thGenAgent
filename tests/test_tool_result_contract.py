from __future__ import annotations

from runtime.tool_result_contract import build_tool_evidence, normalize_evidence, validate_tool_result_contract


def test_valid_tool_result_contract_passes() -> None:
    result = {
        "ok": True,
        "type": "demo_result",
        "data": {"value": 1},
        "evidence": {"tool": "demo/run", "mode": "dry_run", "source": "builtin", "operation": "read", "input_refs": [], "output_ref": "demo_result"},
        "error": "",
        "metadata": {"tool": "demo/run", "mode": "dry_run"},
    }
    validation = validate_tool_result_contract(result, expected_type="demo_result")
    assert validation["ok"] is True
    assert validation["errors"] == []


def test_missing_required_key_fails() -> None:
    validation = validate_tool_result_contract({"ok": True, "type": "demo_result"}, expected_type="demo_result")
    assert validation["ok"] is False
    assert any("Missing required keys" in error for error in validation["errors"])


def test_evidence_must_be_dict() -> None:
    result = {
        "ok": True,
        "type": "demo_result",
        "data": {},
        "evidence": [],
        "error": "",
        "metadata": {},
    }
    validation = validate_tool_result_contract(result, expected_type="demo_result")
    assert validation["ok"] is False
    assert any("evidence must be a dict" in error for error in validation["errors"])


def test_empty_evidence_fails_when_required() -> None:
    result = {
        "ok": True,
        "type": "demo_result",
        "data": {},
        "evidence": {},
        "error": "",
        "metadata": {},
    }
    validation = validate_tool_result_contract(result, expected_type="demo_result")
    assert validation["ok"] is False
    assert any("evidence must not be empty" in error for error in validation["errors"])


def test_failed_result_requires_error_message() -> None:
    result = {
        "ok": False,
        "type": "demo_result",
        "data": {},
        "evidence": {"tool": "demo/run", "mode": "dry_run", "source": "builtin", "operation": "validation", "input_refs": [], "output_ref": "demo_result"},
        "error": "",
        "metadata": {},
    }
    validation = validate_tool_result_contract(result, expected_type="demo_result")
    assert validation["ok"] is False
    assert any("error must be populated" in error for error in validation["errors"])


def test_type_must_match_expected_type() -> None:
    result = {
        "ok": True,
        "type": "wrong_type",
        "data": {},
        "evidence": {"tool": "demo/run", "mode": "dry_run", "source": "builtin", "operation": "read", "input_refs": [], "output_ref": "wrong_type"},
        "error": "",
        "metadata": {},
    }
    validation = validate_tool_result_contract(result, expected_type="demo_result")
    assert validation["ok"] is False
    assert any("Expected type" in error for error in validation["errors"])


def test_build_tool_evidence_has_required_fields() -> None:
    evidence = build_tool_evidence(
        tool="demo/run",
        mode="dry_run",
        source="builtin",
        operation="read",
        input_refs=["inputs.foo"],
        output_ref="demo_result",
        extra={"query": "hello", "record_count": 2},
    )
    assert evidence["tool"] == "demo/run"
    assert evidence["mode"] == "dry_run"
    assert evidence["source"] == "builtin"
    assert evidence["operation"] == "read"
    assert evidence["input_refs"] == ["inputs.foo"]
    assert evidence["output_ref"] == "demo_result"
    assert evidence["query"] == "hello"
    assert evidence["record_count"] == 2


def test_normalize_evidence_uses_fallback_when_empty() -> None:
    fallback = build_tool_evidence(
        tool="demo/run",
        mode="dry_run",
        source="builtin",
        operation="read",
        output_ref="demo_result",
    )
    normalized = normalize_evidence({}, fallback=fallback)
    assert normalized == fallback
