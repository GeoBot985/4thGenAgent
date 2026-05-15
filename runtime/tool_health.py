from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from .business_store import load_business_dataset as load_business_store_dataset
from .business_context import get_business_order_context
from .memory_store import MemoryStore
from src.config_profiles import resolve_google_credentials_path, resolve_google_token_path
from src.toolpack_loader import check_toolpack_health
from .taskframe import utc_now
from .tool_capabilities import ToolHealthResult
from .tool_capability_registry import get_tool_capability, list_tool_capabilities


LATEST_TOOL_HEALTH_JSON = Path("runtime_data") / "tool_health" / "latest_tool_health.json"


def check_tool_health(tool_id: str, *, live: bool = False) -> ToolHealthResult:
    result = _check_tool_health(tool_id, live=live)
    snapshot = load_latest_tool_health_snapshot()
    previous = [ToolHealthResult.from_dict(item) for item in snapshot.get("results", []) if isinstance(item, dict) and str(item.get("tool_id", "")) != tool_id]
    previous.append(result)
    _persist_latest(previous, include_optional=bool(snapshot.get("include_optional", True)), live_rpa=bool(snapshot.get("live_rpa", False)) or live)
    return result


def check_all_tool_health(*, include_optional: bool = True, live_rpa: bool = False) -> list[ToolHealthResult]:
    results = []
    for capability in list_tool_capabilities():
        if not include_optional and capability.core_or_optional != "core":
            continue
        result = _check_tool_health(capability.tool_id, live=live_rpa if capability.tool_id == "rpa_google_messages" else False)
        if capability.core_or_optional == "optional" and capability.tool_id == "rpa_google_messages" and not live_rpa:
            result = ToolHealthResult(
                tool_id=capability.tool_id,
                ok=False,
                status="disabled_optional",
                severity="info",
                message="Optional Google Messages RPA is excluded from default health checks.",
                can_auto_resolve=False,
                recommended_action="Use the live RPA probe from the operator console if local browser setup is available.",
                checked_at=utc_now(),
                details={"capability": capability.to_dict()},
            )
        results.append(result)
    _persist_latest(results, include_optional=include_optional, live_rpa=live_rpa)
    return results


def load_latest_tool_health_snapshot() -> dict[str, Any]:
    if not LATEST_TOOL_HEALTH_JSON.is_file():
        return {"results": [], "by_tool": {}, "generated_at": "", "include_optional": True, "live_rpa": False}
    try:
        payload = json.loads(LATEST_TOOL_HEALTH_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"results": [], "by_tool": {}, "generated_at": "", "include_optional": True, "live_rpa": False}
    if not isinstance(payload, dict):
        return {"results": [], "by_tool": {}, "generated_at": "", "include_optional": True, "live_rpa": False}
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []
    return {
        "generated_at": str(payload.get("generated_at", "")),
        "include_optional": bool(payload.get("include_optional", True)),
        "live_rpa": bool(payload.get("live_rpa", False)),
        "results": [item for item in results if isinstance(item, dict)],
        "by_tool": dict(payload.get("by_tool", {}) or {}),
        "summary": dict(payload.get("summary", {}) or {}),
    }


def _check_tool_health(tool_id: str, *, live: bool = False) -> ToolHealthResult:
    capability = get_tool_capability(tool_id)
    checked_at = utc_now()

    if tool_id == "business_context":
        return _check_business_context(capability, checked_at)
    if tool_id == "business_database":
        return _check_business_database(capability, checked_at)
    if tool_id == "gmail":
        return _check_gmail(capability, checked_at, live=live)
    if tool_id == "google_sheets":
        return _check_google_sheets(capability, checked_at, live=live)
    if tool_id == "google_calendar":
        return _check_google_calendar(capability, checked_at, live=live)
    if tool_id == "llm_ollama":
        return _check_llm_ollama(capability, checked_at, live=live)
    if tool_id == "memory_store":
        return _check_memory_store(capability, checked_at)
    if tool_id == "report_generator":
        return _check_report_generator(capability, checked_at)
    if tool_id == "rpa_google_messages":
        return _check_google_messages_rpa(capability, checked_at, live=live)
    if str(tool_id).startswith("toolpack:"):
        return _check_toolpack(capability, checked_at, live=live)

    return ToolHealthResult(
        tool_id=tool_id,
        ok=False,
        status="unknown",
        severity="warning",
        message="Unknown tool capability.",
        can_auto_resolve=False,
        recommended_action=None,
        checked_at=checked_at,
        details={"capability": capability.to_dict()},
    )


def _check_business_context(capability, checked_at: str) -> ToolHealthResult:
    try:
        import runtime.business_context as business_context  # noqa: F401

        dataset = load_business_store_dataset("runtime_data")
        order_context = get_business_order_context("ORD-10042", runtime_root="runtime_data")
        customers = dataset.get("customers", [])
        orders = dataset.get("orders", [])
        inventory = dataset.get("inventory", [])
        required = {
            "customer": any(str(item.get("customer_id", "")).upper() == "CUST-1001" for item in customers),
            "order": bool(order_context.get("order")),
            "shipment": bool(order_context.get("shipment")),
            "sku": any(str(item.get("sku", "")).upper() == "SKU-LAMP-01" for item in inventory),
        }
        ok = all(required.values())
        status = "ready" if ok else "failing"
        message = "Demo business context loaded and key fixtures are present." if ok else "Demo business context is missing expected fixtures."
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=ok,
            status=status,
            severity="info" if ok else "error",
            message=message,
            can_auto_resolve=not ok,
            recommended_action=None if ok else "Run the demo business dataset seed step.",
            checked_at=checked_at,
            details={
                "dataset_counts": {name: len(items) for name, items in dataset.items()},
                "required_checks": required,
                "order_context": {
                    "order_id": "ORD-10042",
                    "customer_found": bool(order_context.get("customer")),
                    "shipment_found": bool(order_context.get("shipment")),
                },
                "capability": capability.to_dict(),
            },
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Unable to load demo business context.", str(exc))


def _check_business_database(capability, checked_at: str) -> ToolHealthResult:
    try:
        dataset = load_business_store_dataset("runtime_data")
        counts = {name: len(items) for name, items in dataset.items()}
        ok = bool(counts.get("customers")) and bool(counts.get("orders")) and bool(counts.get("inventory"))
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=ok,
            status="ready" if ok else "failing",
            severity="info" if ok else "error",
            message="Demo business dataset store is readable." if ok else "Demo business dataset store is missing records.",
            can_auto_resolve=not ok,
            recommended_action=None if ok else "Reseed the local demo business dataset.",
            checked_at=checked_at,
            details={"dataset_counts": counts, "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Unable to read demo business dataset store.", str(exc))


def _google_dependency_state() -> dict[str, Any]:
    names = [
        "google.auth.transport.requests",
        "google.oauth2.credentials",
        "google_auth_oauthlib.flow",
        "googleapiclient.discovery",
    ]
    missing: list[str] = []
    for name in names:
        try:
            found = importlib.util.find_spec(name)
        except Exception:
            found = None
        if found is None:
            missing.append(name)
    return {"ok": not missing, "missing": missing}


def _google_auth_files() -> dict[str, Any]:
    base = Path(__file__).resolve().parents[1]
    credentials = resolve_google_credentials_path()
    token = resolve_google_token_path()
    fallback = (
        sorted((Path.home() / ".taskframe" / "google").glob("client_secret*.json"))
        + sorted(base.glob("client_secret*.json"))
        + [base / "credentials.json", base / "google_token.json", base / "token.json"]
    )
    return {
        "credentials": str(credentials),
        "credentials_exists": credentials.is_file() or any(path.is_file() for path in fallback),
        "token": str(token),
        "token_exists": token.is_file() or any(path.is_file() for path in [Path.home() / ".taskframe" / "google" / "google_token.json", base / "google_token.json", base / "token.json"]),
        "fallback_files": [str(path) for path in fallback],
    }


def _check_gmail(capability, checked_at: str, *, live: bool) -> ToolHealthResult:
    deps = _google_dependency_state()
    files = _google_auth_files()
    if not deps["ok"]:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="missing_dependency",
            severity="error",
            message="Google OAuth/Gmail dependencies are not installed.",
            can_auto_resolve=False,
            recommended_action="Install the Google client dependencies.",
            checked_at=checked_at,
            details={"missing": deps["missing"], "auth_files": files, "capability": capability.to_dict()},
        )
    if not (files["token_exists"] or files["credentials_exists"] or files["fallback_files"]):
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="needs_auth",
            severity="warning",
            message="Gmail credentials are not configured.",
            can_auto_resolve=False,
            recommended_action="Add Google OAuth credentials and authorize Gmail access manually.",
            checked_at=checked_at,
            details={"auth_files": files, "capability": capability.to_dict()},
        )
    if not live:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Gmail dependencies and local auth files are present.",
            can_auto_resolve=False,
            recommended_action=None,
            checked_at=checked_at,
            details={"auth_files": files, "capability": capability.to_dict()},
        )
    try:
        from tools.google_auth import build_service

        service = build_service("gmail", "v1")
        labels = service.users().labels().list(userId="me").execute()
        count = len(labels.get("labels", []) or [])
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="live_verified",
            severity="info",
            message="Gmail labels were read successfully.",
            can_auto_resolve=False,
            recommended_action=None,
            checked_at=checked_at,
            details={"label_count": count, "auth_files": files, "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Gmail live probe failed.", str(exc), details={"auth_files": files})


def _check_google_sheets(capability, checked_at: str, *, live: bool) -> ToolHealthResult:
    deps = _google_dependency_state()
    try:
        from runtime.google_sheet_tools import load_accounting_sheet_config

        config = load_accounting_sheet_config()
    except Exception as exc:
        return _failed_result(capability, checked_at, "missing_dependency", "Google Sheets helper module is unavailable.", str(exc))

    spreadsheet_id = str(config.get("spreadsheet_id", "")).strip()
    if not deps["ok"]:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="missing_dependency",
            severity="error",
            message="Google Sheets dependencies are not installed.",
            can_auto_resolve=False,
            recommended_action="Install the Google client dependencies.",
            checked_at=checked_at,
            details={"missing": deps["missing"], "config": config, "capability": capability.to_dict()},
        )
    if not spreadsheet_id:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="misconfigured",
            severity="warning",
            message="Google Sheets spreadsheet_id is not configured.",
            can_auto_resolve=False,
            recommended_action="Select a spreadsheet ID in config/accounting_google_sheet.json.",
            checked_at=checked_at,
            details={"config": config, "capability": capability.to_dict()},
        )
    if not live:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Google Sheets configuration is present.",
            can_auto_resolve=False,
            recommended_action=None,
            checked_at=checked_at,
            details={"config": config, "capability": capability.to_dict()},
        )
    try:
        from runtime.google_sheet_tools import sheet_read_range

        tabs = config.get("tabs", {}) if isinstance(config.get("tabs", {}), dict) else {}
        first_range = next(iter(tabs.values()), "Sheet1!A1:A1")
        result = sheet_read_range(spreadsheet_id, first_range)
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=bool(result.get("ok", False)),
            status="live_verified" if result.get("ok") else "failing",
            severity="info" if result.get("ok") else "error",
            message="Google Sheets read probe completed." if result.get("ok") else str(result.get("error", "Google Sheets read failed.")),
            can_auto_resolve=False,
            recommended_action=None if result.get("ok") else "Recheck spreadsheet authorization and range configuration.",
            checked_at=checked_at,
            details={"probe_result": result, "config": config, "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Google Sheets live probe failed.", str(exc), details={"config": config})


def _check_google_calendar(capability, checked_at: str, *, live: bool) -> ToolHealthResult:
    deps = _google_dependency_state()
    files = _google_auth_files()
    if not deps["ok"]:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="missing_dependency",
            severity="error",
            message="Google Calendar dependencies are not installed.",
            can_auto_resolve=False,
            recommended_action="Install the Google client dependencies.",
            checked_at=checked_at,
            details={"missing": deps["missing"], "auth_files": files, "capability": capability.to_dict()},
        )
    if not (files["token_exists"] or files["credentials_exists"] or files["fallback_files"]):
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="needs_auth",
            severity="warning",
            message="Google Calendar credentials are not configured.",
            can_auto_resolve=False,
            recommended_action="Add Google OAuth credentials and authorize Calendar access manually.",
            checked_at=checked_at,
            details={"auth_files": files, "capability": capability.to_dict()},
        )
    if not live:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Google Calendar dependencies and local auth files are present.",
            can_auto_resolve=False,
            recommended_action=None,
            checked_at=checked_at,
            details={"auth_files": files, "capability": capability.to_dict()},
        )
    try:
        from tools.google_auth import build_service

        service = build_service("calendar", "v3")
        result = service.calendarList().list().execute()
        items = result.get("items", []) or []
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="live_verified",
            severity="info",
            message="Google Calendar list probe completed.",
            can_auto_resolve=False,
            recommended_action=None,
            checked_at=checked_at,
            details={"calendar_count": len(items), "auth_files": files, "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Google Calendar live probe failed.", str(exc), details={"auth_files": files})


def _check_llm_ollama(capability, checked_at: str, *, live: bool) -> ToolHealthResult:
    provider = os.getenv("TASKFRAME_LLM_PROVIDER", "ollama")
    model = os.getenv("TASKFRAME_OLLAMA_MODEL", "granite3.3:8b")
    base_url = os.getenv("TASKFRAME_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    if provider == "fake":
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Fake LLM provider is configured for deterministic local runs.",
            can_auto_resolve=True,
            recommended_action=None,
            checked_at=checked_at,
            details={"provider": provider, "model": model, "base_url": base_url, "capability": capability.to_dict()},
        )
    if provider != "ollama":
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="not_run",
            severity="info",
            message=f"LLM provider '{provider}' is not configured for this tool health probe.",
            can_auto_resolve=False,
            recommended_action="Set TASKFRAME_LLM_PROVIDER=fake for deterministic clean-clone runs or configure Ollama locally.",
            checked_at=checked_at,
            details={"provider": provider, "model": model, "base_url": base_url, "capability": capability.to_dict()},
        )
    if not live:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="not_run",
            severity="info",
            message="Ollama live probe not requested.",
            can_auto_resolve=False,
            recommended_action="Run the live probe once a local Ollama endpoint is available.",
            checked_at=checked_at,
            details={"provider": provider, "model": model, "base_url": base_url, "capability": capability.to_dict()},
        )
    try:
        from runtime.llm_adapter import check_llm_available

        result = check_llm_available(provider=provider, model=model)
        if result.get("ok"):
            return ToolHealthResult(
                tool_id=capability.tool_id,
                ok=True,
                status="live_verified",
                severity="info",
                message="Ollama endpoint responded to a tiny probe.",
                can_auto_resolve=False,
                recommended_action=None,
                checked_at=checked_at,
                details={"probe_result": result, "base_url": base_url, "capability": capability.to_dict()},
            )
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="failing",
            severity="error",
            message=str(result.get("error", "Ollama probe failed.")),
            can_auto_resolve=False,
            recommended_action="Start a local Ollama server or switch to the fake provider.",
            checked_at=checked_at,
            details={"probe_result": result, "base_url": base_url, "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Ollama live probe failed.", str(exc), details={"provider": provider, "model": model, "base_url": base_url})


def _check_memory_store(capability, checked_at: str) -> ToolHealthResult:
    try:
        store = MemoryStore()
        data = store.load()
        items = data.get("items", {}) if isinstance(data.get("items", {}), dict) else {}
        probe_key = "tool_health/probe"
        probe_value = {"checked_at": checked_at}
        probe = None
        try:
            store.set(probe_key, probe_value, metadata={"probe": True})
            probe = store.get(probe_key)
        finally:
            # Keep the probe local and disposable.
            if store.path.exists():
                try:
                    current = json.loads(store.path.read_text(encoding="utf-8"))
                    if isinstance(current, dict):
                        current_items = current.get("items", {})
                        if isinstance(current_items, dict) and probe_key in current_items:
                            current_items.pop(probe_key, None)
                            store.save(current)
                except Exception:
                    pass
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=bool(probe and probe.found),
            status="ready" if probe and probe.found else "failing",
            severity="info" if probe and probe.found else "error",
            message="Memory store opened and local probe completed." if probe and probe.found else "Memory store probe failed.",
            can_auto_resolve=not bool(probe and probe.found),
            recommended_action=None if probe and probe.found else "Check the local runtime_data/memory_store.json file.",
            checked_at=checked_at,
            details={"items_count": len(items), "probe_key": probe_key, "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Unable to open the local memory store.", str(exc))


def _check_report_generator(capability, checked_at: str) -> ToolHealthResult:
    try:
        reports_dir = Path("runtime_data") / "tool_health" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = reports_dir / "report_generator_probe.md"
        html_path = reports_dir / "report_generator_probe.html"
        markdown_path.write_text("# Report Generator Probe\n\nThis file was generated during a safe health check.\n", encoding="utf-8")
        html_path.write_text("<!doctype html><html><body><h1>Report Generator Probe</h1></body></html>", encoding="utf-8")
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=True,
            status="ready",
            severity="info",
            message="Local report files were generated successfully.",
            can_auto_resolve=True,
            recommended_action=None,
            checked_at=checked_at,
            details={"markdown_path": str(markdown_path), "html_path": str(html_path), "capability": capability.to_dict()},
        )
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Unable to generate a local report probe.", str(exc))


def _check_google_messages_rpa(capability, checked_at: str, *, live: bool) -> ToolHealthResult:
    optional_enabled = os.getenv("ENABLE_OPTIONAL_RPA_TOOLS", "").strip().lower() in {"1", "true", "yes", "on"}
    if not optional_enabled and not live:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="disabled_optional",
            severity="info",
            message="Optional Google Messages RPA is disabled by default.",
            can_auto_resolve=False,
            recommended_action="Enable optional RPA tools only when local browser state is available.",
            checked_at=checked_at,
            details={"capability": capability.to_dict(), "optional_enabled": optional_enabled},
        )
    if not live:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="live_probe_required",
            severity="warning",
            message="Google Messages RPA requires a live browser probe.",
            can_auto_resolve=False,
            recommended_action="Run the live probe from the operator console on a local machine with browser auth.",
            checked_at=checked_at,
            details={"capability": capability.to_dict(), "optional_enabled": optional_enabled},
        )
    if not optional_enabled:
        return ToolHealthResult(
            tool_id=capability.tool_id,
            ok=False,
            status="disabled_optional",
            severity="info",
            message="Optional Google Messages RPA is not enabled.",
            can_auto_resolve=False,
            recommended_action="Enable optional RPA tools first.",
            checked_at=checked_at,
            details={"capability": capability.to_dict(), "optional_enabled": optional_enabled},
        )
    try:
        import asyncio
        from optional_tools.rpa.google_messages_absa.health import live_probe_google_messages

        probe = asyncio.run(live_probe_google_messages({"runtime_root": "runtime_data"}))
        return probe
    except Exception as exc:
        return _failed_result(capability, checked_at, "failing", "Google Messages RPA live probe failed.", str(exc))


def _failed_result(capability, checked_at: str, status: str, message: str, error: str, *, details: dict[str, Any] | None = None) -> ToolHealthResult:
    payload = dict(details or {})
    payload.setdefault("error", error)
    payload.setdefault("capability", capability.to_dict())
    return ToolHealthResult(
        tool_id=capability.tool_id,
        ok=False,
        status=status,
        severity="error" if status in {"failing", "misconfigured", "missing_dependency"} else "warning",
        message=message,
        can_auto_resolve=False,
        recommended_action=None,
        checked_at=checked_at,
        details=payload,
    )


def _check_toolpack(capability, checked_at: str, *, live: bool = False) -> ToolHealthResult:
    pack_id = str(capability.toolpack_id or capability.tool_id.removeprefix("toolpack:"))
    result = check_toolpack_health(pack_id, live=live)
    status = str(result.get("status", "unknown"))
    severity = str(result.get("severity", "warning"))
    message = str(result.get("message", "Tool pack health check completed."))
    ok = bool(result.get("ok", False))
    return ToolHealthResult(
        tool_id=capability.tool_id,
        ok=ok,
        status=status,
        severity=severity,
        message=message,
        can_auto_resolve=False,
        recommended_action=None,
        checked_at=checked_at,
        details=dict(result),
    )


def _persist_latest(results: list[ToolHealthResult], *, include_optional: bool, live_rpa: bool) -> None:
    LATEST_TOOL_HEALTH_JSON.parent.mkdir(parents=True, exist_ok=True)
    results_payload = [result.to_dict() for result in results]
    by_tool = {result.tool_id: result.to_dict() for result in results}
    payload = {
        "generated_at": utc_now(),
        "include_optional": include_optional,
        "live_rpa": live_rpa,
        "results": results_payload,
        "by_tool": by_tool,
        "summary": {
            "tool_count": len(results_payload),
            "ready_count": sum(1 for result in results if result.ok),
            "failed_count": sum(1 for result in results if not result.ok),
        },
    }
    LATEST_TOOL_HEALTH_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
