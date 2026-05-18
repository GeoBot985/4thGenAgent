from __future__ import annotations

from types import SimpleNamespace

from runtime.tool_health import _check_toolpack, check_all_tool_health


def test_live_health_probe_blocked_for_high_risk_demo(monkeypatch) -> None:
    fake_capability = SimpleNamespace(
        tool_id="toolpack:demo_high_risk",
        toolpack_id="demo_high_risk",
        core_or_optional="optional",
        to_dict=lambda: {"tool_id": "toolpack:demo_high_risk", "toolpack_id": "demo_high_risk"},
    )

    monkeypatch.setattr(
        "runtime.tool_health.evaluate_tool_governance",
        lambda *args, **kwargs: {
            "ok": False,
            "decision": "BLOCK",
            "reason": "High-risk toolpack is not allowed in demo.",
            "tool": "toolpack:demo_high_risk",
            "toolpack_id": "demo_high_risk",
            "classification": "high_risk",
            "environment": "demo",
            "dry_run": False,
            "live_requested": True,
            "policy": {},
            "errors": ["blocked"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "runtime.tool_health.check_toolpack_health",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live health probe should not run")),
    )

    result = _check_toolpack(fake_capability, "2026-05-01T00:00:00Z", live=True)

    assert result.ok is False
    assert result.status == "blocked"


def test_safe_core_health_checks_still_run_in_demo() -> None:
    results = check_all_tool_health(include_optional=False, live_rpa=False)
    assert any(result.tool_id == "business_context" and result.ok for result in results)


def test_optional_readonly_health_check_requires_enabled_pack(monkeypatch) -> None:
    fake_capability = SimpleNamespace(
        tool_id="toolpack:google_workspace",
        toolpack_id="google_workspace",
        core_or_optional="optional",
        to_dict=lambda: {"tool_id": "toolpack:google_workspace", "toolpack_id": "google_workspace"},
    )

    monkeypatch.setattr(
        "runtime.tool_health.evaluate_tool_governance",
        lambda *args, **kwargs: {
            "ok": False,
            "decision": "BLOCK",
            "reason": "Not enabled for demo.",
            "tool": "toolpack:google_workspace",
            "toolpack_id": "google_workspace",
            "classification": "optional",
            "environment": "demo",
            "dry_run": False,
            "live_requested": True,
            "policy": {},
            "errors": ["blocked"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "runtime.tool_health.check_toolpack_health",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("health probe should not run")),
    )

    result = _check_toolpack(fake_capability, "2026-05-01T00:00:00Z", live=True)

    assert result.ok is False
    assert result.status == "blocked"


def test_default_all_health_checks_do_not_run_rpa_live_probe() -> None:
    results = check_all_tool_health(include_optional=True, live_rpa=False)
    rpa = next((result for result in results if result.tool_id == "rpa_google_messages"), None)
    assert rpa is not None
    assert rpa.status == "disabled_optional"
