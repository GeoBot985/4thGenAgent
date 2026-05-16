"""Contract test harness for external tool packs."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

_SMOKE_DEFAULTS: dict[str, Any] = {
    "str": "TEST",
    "int": 1,
    "float": 1.0,
    "bool": False,
    "dict": {},
    "list": [],
}

_REQUIRED_RESULT_KEYS = {"ok", "type", "data", "evidence", "error"}


def run_toolpack_contract_tests(
    toolpack_path: str | Path,
    *,
    runtime_data_dir: str | Path = "runtime_data",
    include_manifest_smoke: bool = True,
) -> dict[str, Any]:
    from src.toolpack_loader import load_toolpack_descriptor, validate_toolpack_descriptor

    path = Path(toolpack_path) if not Path(toolpack_path).is_absolute() else Path(toolpack_path)
    if not path.is_absolute():
        path = ROOT / path

    checks: list[dict[str, Any]] = []
    tool_checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    if not path.is_file():
        errors.append(f"Descriptor not found: {path}")
        return _result(False, "FAIL", "", checks, tool_checks, {}, errors, warnings)

    try:
        descriptor = load_toolpack_descriptor(path)
    except Exception as exc:
        errors.append(f"Descriptor load failed: {exc}")
        return _result(False, "FAIL", "", checks, tool_checks, {}, errors, warnings)

    try:
        validation = validate_toolpack_descriptor(descriptor, base_path=path.parent)
    except Exception as exc:
        errors.append(f"Descriptor validation raised: {exc}")
        validation = {"ok": False, "toolpack_id": "", "tool_count": 0, "errors": [str(exc)], "warnings": [], "descriptor": {}}

    toolpack_id = str(validation.get("toolpack_id") or descriptor.get("toolpack_id") or "")
    raw_errors = list(validation.get("errors", []))
    # Separate import errors from structural errors — import ability is checked separately per-tool.
    import_errors = [e for e in raw_errors if "module import failed" in e or "function not found" in e]
    structural_errors = [e for e in raw_errors if e not in import_errors]
    descriptor_ok = not structural_errors
    checks.append(_check("descriptor_valid", descriptor_ok, "Descriptor is valid." if descriptor_ok else f"Descriptor errors: {structural_errors}"))
    for w in validation.get("warnings", []):
        warnings.append(f"descriptor: {w}")

    if not descriptor_ok:
        errors.extend(structural_errors)
        return _result(False, "FAIL", toolpack_id, checks, tool_checks, {}, errors, warnings)

    descriptor_data = validation.get("descriptor", {})
    tools = descriptor_data.get("tools", [])

    pack_dir = path.parent
    for tool_spec in tools:
        tc = _run_tool_check(tool_spec, warnings, pack_dir=pack_dir)
        tool_checks.append(tc)
        if not tc.get("import_ok") or not tc.get("smoke_ok") or not tc.get("result_shape_ok") or not tc.get("safety_ok"):
            errors.append(f"Tool check failed: {tool_spec.get('tool', '')}")

    health_ok = _run_health_check(descriptor_data, pack_dir, warnings)
    checks.append(_check("health_check", health_ok, "Health check passed." if health_ok else "Health check failed."))

    manifest_smoke: dict[str, Any] = {}
    if include_manifest_smoke:
        manifest_smoke = _run_manifest_smoke(path.parent, toolpack_id, tools, runtime_data_dir)
        smoke_ok = bool(manifest_smoke.get("ok", True))
        checks.append(_check("manifest_smoke", smoke_ok, manifest_smoke.get("message", "Manifest smoke complete.")))
        if not smoke_ok:
            warnings.append(f"Manifest smoke: {manifest_smoke.get('message', '')}")

    all_tool_ok = all(
        tc.get("import_ok") and tc.get("smoke_ok") and tc.get("result_shape_ok") and tc.get("safety_ok")
        for tc in tool_checks
    )
    all_checks_ok = all(c["status"] == "PASS" for c in checks)
    ok = descriptor_ok and all_tool_ok and all_checks_ok and not errors

    return _result(ok, "PASS" if ok else "FAIL", toolpack_id, checks, tool_checks, manifest_smoke, errors, warnings)


def build_tool_invocation_smoke_args(tool_spec: dict[str, Any]) -> dict[str, Any]:
    required_args: list[str] = list(tool_spec.get("required_args", []))
    arg_types: dict[str, str] = dict(tool_spec.get("arg_types", {}))
    errors: list[str] = []
    kwargs: dict[str, Any] = {}

    for arg in required_args:
        arg_type = str(arg_types.get(arg, "str"))
        if arg_type not in _SMOKE_DEFAULTS:
            errors.append(f"UNKNOWN_ARG_TYPE: {arg}:{arg_type}")
            continue
        kwargs[arg] = _SMOKE_DEFAULTS[arg_type]

    return {"ok": not errors, "kwargs": kwargs, "errors": errors}


def validate_tool_result_shape(result: object, expected_type: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"ok": False, "errors": ["Result must be a dict."]}
    missing = [k for k in _REQUIRED_RESULT_KEYS if k not in result]
    if missing:
        return {"ok": False, "errors": [f"Missing required keys: {missing}"]}
    actual_type = str(result.get("type", ""))
    if expected_type and actual_type != expected_type:
        return {"ok": False, "errors": [f"Expected type {expected_type!r}, got {actual_type!r}"]}
    return {"ok": True, "errors": []}


def _import_module(module_name: str, pack_path: Path | None = None):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        pass
    if pack_path is None:
        raise ModuleNotFoundError(f"No module named {module_name!r}")
    file_stem = module_name.rsplit(".", 1)[-1]
    candidate = pack_path / f"{file_stem}.py"
    if not candidate.is_file():
        raise ModuleNotFoundError(f"No module named {module_name!r} and no file at {candidate}")
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Cannot load {module_name!r} from {candidate}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _run_tool_check(tool_spec: dict[str, Any], warnings: list[str], *, pack_dir: Path | None = None) -> dict[str, Any]:
    tool_key = str(tool_spec.get("tool", ""))
    module_name = str(tool_spec.get("module", ""))
    function_name = str(tool_spec.get("function", ""))
    output_type = str(tool_spec.get("output_type", ""))
    side_effect = bool(tool_spec.get("side_effect", False))
    requires_approval = bool(tool_spec.get("requires_approval", False))
    allow_live_side_effect = bool(tool_spec.get("allow_live_side_effect", False))
    live_guardrail = str(tool_spec.get("live_guardrail", ""))

    tc: dict[str, Any] = {
        "tool": tool_key,
        "import_ok": False,
        "smoke_ok": False,
        "result_shape_ok": False,
        "safety_ok": False,
        "errors": [],
        "warnings": [],
    }

    try:
        module = _import_module(module_name, pack_dir)
        func = getattr(module, function_name)
        tc["import_ok"] = True
    except Exception as exc:
        tc["errors"].append(f"Import failed: {exc}")
        return tc

    smoke_args = build_tool_invocation_smoke_args(tool_spec)
    if not smoke_args["ok"]:
        tc["errors"].extend(smoke_args["errors"])
        return tc

    try:
        raw_result = func(**smoke_args["kwargs"])
        tc["smoke_ok"] = True
    except Exception as exc:
        tc["errors"].append(f"Smoke call failed: {exc}")
        return tc

    shape = validate_tool_result_shape(raw_result, output_type)
    tc["result_shape_ok"] = shape["ok"]
    if not shape["ok"]:
        tc["errors"].extend(shape["errors"])

    safety_errors: list[str] = []
    if side_effect and not requires_approval:
        safety_errors.append("Side-effect tool must require approval.")
    if allow_live_side_effect:
        safety_errors.append("Scaffolded tool must not allow live side effects.")
    if live_guardrail not in ("blocked", ""):
        pass
    tc["safety_ok"] = not safety_errors
    if safety_errors:
        tc["errors"].extend(safety_errors)

    return tc


def _run_health_check(descriptor_data: dict[str, Any], base_path: Path, warnings: list[str]) -> bool:
    health_supported = bool(descriptor_data.get("health_supported", True))
    if not health_supported:
        return True
    health = descriptor_data.get("health", {})
    module_name = str(health.get("module", ""))
    function_name = str(health.get("function", ""))
    if not module_name or not function_name:
        return False
    try:
        module = _import_module(module_name, base_path)
        func = getattr(module, function_name)
        result = func(live=False)
        return bool(result.get("ok", False)) if isinstance(result, dict) else bool(result)
    except Exception as exc:
        warnings.append(f"Health check raised: {exc}")
        return False


def _run_manifest_smoke(pack_dir: Path, toolpack_id: str, tools: list[dict[str, Any]], runtime_data_dir: str | Path) -> dict[str, Any]:
    examples_dir = pack_dir / "examples"
    if not examples_dir.is_dir():
        return {"ok": True, "message": "No examples directory found; skipping manifest smoke."}

    manifests = list(examples_dir.glob("*.manifest.json"))
    if not manifests:
        return {"ok": True, "message": "No example manifests found; skipping manifest smoke."}

    ran = 0
    failed: list[str] = []
    for manifest_path in manifests[:3]:
        try:
            import json
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            _validate_manifest_structure(manifest, failed, manifest_path.name)
            ran += 1
        except Exception as exc:
            failed.append(f"{manifest_path.name}: {exc}")

    ok = not failed
    return {
        "ok": ok,
        "ran": ran,
        "failed": failed,
        "message": f"Manifest smoke: {ran} ran, {len(failed)} failed.",
    }


def _validate_manifest_structure(manifest: dict[str, Any], failed: list[str], name: str) -> None:
    required = {"manifest_id", "steps"}
    missing = required - manifest.keys()
    if missing:
        failed.append(f"{name}: missing fields {missing}")


def _check(check_id: str, ok: bool, message: str) -> dict[str, Any]:
    return {"id": check_id, "status": "PASS" if ok else "FAIL", "message": message}


def _result(
    ok: bool,
    status: str,
    toolpack_id: str,
    checks: list[dict[str, Any]],
    tool_checks: list[dict[str, Any]],
    manifest_smoke: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "toolpack_id": toolpack_id,
        "checks": checks,
        "tool_checks": tool_checks,
        "manifest_smoke": manifest_smoke,
        "errors": errors,
        "warnings": warnings,
    }
