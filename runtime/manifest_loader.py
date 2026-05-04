from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .command_parser import parse_command
from .conditions import validate_condition
from .errors import ManifestLoadError, ManifestValidationError
from .models import Manifest, ManifestStep, ParsedCommand
from .live_execution import normalize_live_execution_policy, validate_live_execution_policy
from .retry_policy import normalize_retry_policy, validate_retry_policy
from .timing import validate_timeout_seconds


_REQUIRED_TOP_LEVEL_FIELDS = (
    "manifest_id",
    "name",
    "version",
    "trigger",
    "inputs",
    "steps",
    "validations",
    "completion",
)


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ManifestLoadError(f"Manifest file not found: {manifest_path}")

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
        raw = json.loads(manifest_text)
    except OSError as exc:
        raise ManifestLoadError(f"Unable to read manifest file: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestLoadError(f"Invalid JSON in manifest file: {manifest_path}") from exc

    if not isinstance(raw, dict):
        raise ManifestValidationError("Manifest root must be a JSON object.")

    if _is_custom_event_manifest(raw):
        return _load_custom_event_manifest(raw, manifest_path)

    _validate_top_level_fields(raw)

    steps_raw = raw["steps"]
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ManifestValidationError("Manifest steps must be a non-empty list.")

    steps: list[ManifestStep] = []
    seen_step_ids: set[str] = set()
    for index, step_raw in enumerate(steps_raw):
        if not isinstance(step_raw, dict):
            raise ManifestValidationError(f"Step {index} must be an object.")
        step_id = step_raw.get("id")
        command = step_raw.get("command")
        step_kind = step_raw.get("kind")
        if not isinstance(step_id, str) or not step_id.strip():
            raise ManifestValidationError(f"Step {index} is missing a valid id.")
        if step_id in seen_step_ids:
            raise ManifestValidationError(f"Duplicate step id: {step_id}")
        if not isinstance(command, str) or not command.strip():
            if not isinstance(step_kind, str) or not step_kind.strip():
                raise ManifestValidationError(f"Step {step_id} is missing a valid command.")
        when = step_raw.get("when")
        if when is not None:
            if not isinstance(when, dict):
                raise ManifestValidationError(f"Step {step_id} when must be an object.")
            try:
                validate_condition(when)
            except Exception as exc:
                raise ManifestValidationError(f"Invalid when condition in step {step_id}: {exc}") from exc
        retry = step_raw.get("retry")
        if retry is not None:
            if not isinstance(retry, dict):
                raise ManifestValidationError(f"Step {step_id} retry must be an object.")
            try:
                retry = normalize_retry_policy(retry)
                validate_retry_policy(retry)
            except Exception as exc:
                raise ManifestValidationError(f"Invalid retry policy in step {step_id}: {exc}") from exc
        timeout_seconds = step_raw.get("timeout_seconds")
        if timeout_seconds is not None:
            try:
                timeout_seconds = validate_timeout_seconds(timeout_seconds)
            except Exception as exc:
                raise ManifestValidationError(f"Invalid timeout policy in step {step_id}: {exc}") from exc
        if isinstance(command, str) and command.strip():
            try:
                parsed_command = parse_command(command)
            except Exception as exc:
                raise ManifestValidationError(f"Invalid command in step {step_id}: {exc}") from exc
        else:
            parsed_command = ParsedCommand(
                raw=str(step_kind),
                kind=str(step_kind),
                namespace=None,
                action=str(step_raw.get("action", step_id)),
                output_alias=_string_or_none(step_raw.get("output")),
                payload="",
                args={key: str(value) for key, value in step_raw.items() if key not in {"id", "kind", "action", "output", "when", "retry", "timeout_seconds"}},
            )
        steps.append(
            ManifestStep(
                id=step_id,
                command=str(command or step_kind or ""),
                parsed_command=parsed_command,
                when=when,
                retry=retry,
                timeout_seconds=timeout_seconds,
            )
        )
        seen_step_ids.add(step_id)

    manifest_id = raw["manifest_id"]
    name = raw["name"]
    version = raw["version"]
    trigger = raw["trigger"]
    inputs = raw["inputs"]
    validations = raw["validations"]
    completion = raw["completion"]
    live_execution = raw.get("live_execution")

    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ManifestValidationError("manifest_id must be a non-empty string.")
    if not isinstance(name, str) or not name.strip():
        raise ManifestValidationError("name must be a non-empty string.")
    if not isinstance(version, int):
        raise ManifestValidationError("version must be an integer.")
    if not isinstance(trigger, dict):
        raise ManifestValidationError("trigger must be an object.")
    if not isinstance(inputs, list):
        raise ManifestValidationError("inputs must be a list.")
    if not isinstance(validations, list):
        raise ManifestValidationError("validations must be a list.")
    if not isinstance(completion, dict) or not completion:
        raise ManifestValidationError("completion must be a non-empty object.")

    if live_execution is not None and not isinstance(live_execution, dict):
        raise ManifestValidationError("live_execution must be an object.")
    try:
        live_execution = normalize_live_execution_policy(live_execution)
        validate_live_execution_policy(live_execution)
    except Exception as exc:
        raise ManifestValidationError(f"Invalid live_execution policy: {exc}") from exc

    return Manifest(
        manifest_id=manifest_id,
        name=name,
        version=version,
        trigger=trigger,
        inputs=inputs,
        steps=steps,
        validations=validations,
        completion=completion,
        raw=raw,
        live_execution=live_execution,
    )


def load_manifest_catalog(manifest_dir: str | Path = "manifests") -> dict[str, Path]:
    base_dir = Path(manifest_dir)
    extra_dir = Path("config/manifests")
    if not base_dir.is_dir() and not extra_dir.is_dir():
        raise ManifestLoadError(f"Manifest directory not found: {base_dir}")

    catalog: dict[str, Path] = {}
    for manifest_path in _iter_manifest_paths(base_dir, extra_dir):
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ManifestLoadError(f"Unable to read manifest file: {manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise ManifestLoadError(f"Invalid JSON in manifest file: {manifest_path}") from exc

        if not isinstance(raw, dict):
            raise ManifestValidationError(f"Manifest root must be a JSON object: {manifest_path}")

        manifest_id = raw.get("manifest_id", raw.get("id"))
        if not isinstance(manifest_id, str) or not manifest_id.strip():
            raise ManifestValidationError(f"Manifest is missing a valid manifest_id: {manifest_path}")

        if manifest_id in catalog:
            raise ManifestValidationError(f"Duplicate manifest_id in catalog: {manifest_id}")

        catalog[manifest_id] = manifest_path

    return catalog


def load_manifest_by_id(
    manifest_id: str,
    manifest_dir: str | Path = "manifests",
) -> Manifest:
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ManifestValidationError("manifest_id must be a non-empty string.")

    catalog = load_manifest_catalog(manifest_dir)
    try:
        manifest_path = catalog[manifest_id]
    except KeyError as exc:
        raise ManifestLoadError(f"Manifest not found for manifest_id: {manifest_id}") from exc
    return load_manifest(manifest_path)


def _validate_top_level_fields(raw: dict) -> None:
    missing = [field for field in _REQUIRED_TOP_LEVEL_FIELDS if field not in raw]
    if missing:
        raise ManifestValidationError(f"Missing required manifest fields: {', '.join(missing)}")


def _is_custom_event_manifest(raw: dict[str, object]) -> bool:
    return "id" in raw and "trigger_type" in raw and "steps" in raw and "manifest_id" not in raw


def _load_custom_event_manifest(raw: dict[str, Any], manifest_path: Path) -> Manifest:
    manifest_id = raw.get("id")
    name = raw.get("name")
    steps_raw = raw.get("steps")
    inputs = raw.get("inputs", {})
    completion = raw.get("completion", {})
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ManifestValidationError(f"Custom manifest is missing a valid id: {manifest_path}")
    if not isinstance(name, str) or not name.strip():
        raise ManifestValidationError(f"Custom manifest is missing a valid name: {manifest_path}")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ManifestValidationError(f"Custom manifest steps must be a non-empty list: {manifest_path}")
    if not isinstance(inputs, dict):
        raise ManifestValidationError(f"Custom manifest inputs must be an object: {manifest_path}")
    if not isinstance(completion, dict) or not completion:
        raise ManifestValidationError(f"Custom manifest completion must be an object: {manifest_path}")

    required_inputs = inputs.get("required", [])
    if not isinstance(required_inputs, list):
        raise ManifestValidationError(f"Custom manifest required inputs must be a list: {manifest_path}")

    steps: list[ManifestStep] = []
    seen_step_ids: set[str] = set()
    for index, step_raw in enumerate(steps_raw):
        if not isinstance(step_raw, dict):
            raise ManifestValidationError(f"Custom manifest step {index} must be an object.")
        step_id = step_raw.get("step_id")
        kind = step_raw.get("kind")
        command = step_raw.get("command")
        when = step_raw.get("when")
        if not isinstance(step_id, str) or not step_id.strip():
            raise ManifestValidationError(f"Custom manifest step {index} is missing a valid step_id.")
        if step_id in seen_step_ids:
            raise ManifestValidationError(f"Duplicate step id: {step_id}")
        if not isinstance(kind, str) or not kind.strip():
            raise ManifestValidationError(f"Custom manifest step {step_id} is missing a valid kind.")
        if when is not None:
            if not isinstance(when, dict):
                raise ManifestValidationError(f"Custom manifest step {step_id} when must be an object.")
            try:
                validate_condition(when)
            except Exception as exc:
                raise ManifestValidationError(f"Invalid when condition in custom manifest step {step_id}: {exc}") from exc

        metadata = dict(step_raw)
        if isinstance(command, str) and command.strip():
            parsed_command = parse_command(command)
        else:
            parsed_command = ParsedCommand(
                raw=kind,
                kind=kind,
                namespace=None,
                action=step_id,
                output_alias=_string_or_none(step_raw.get("output")),
                payload="",
                args={key: str(value) for key, value in step_raw.items() if key not in {"step_id", "kind", "command", "output"}},
            )
        steps.append(
            ManifestStep(
                id=step_id,
                command=str(command or kind),
                parsed_command=parsed_command,
                when=when,
                metadata=metadata,
            )
        )
        seen_step_ids.add(step_id)

    trigger = {"type": str(raw.get("trigger_type", "event"))}
    validations = list(raw.get("validations", [])) if isinstance(raw.get("validations", []), list) else []
    live_execution = raw.get("live_execution")
    if live_execution is not None and not isinstance(live_execution, dict):
        raise ManifestValidationError("live_execution must be an object.")
    try:
        live_execution = normalize_live_execution_policy(live_execution)
        validate_live_execution_policy(live_execution)
    except Exception as exc:
        raise ManifestValidationError(f"Invalid live_execution policy: {exc}") from exc
    return Manifest(
        manifest_id=manifest_id,
        name=name,
        version=1,
        trigger=trigger,
        inputs=required_inputs,
        steps=steps,
        validations=validations,
        completion=completion,
        raw=raw,
        live_execution=live_execution,
    )


def _iter_manifest_paths(*directories: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for directory in directories[:1]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.manifest.json")):
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    if len(directories) > 1:
        for directory in directories[1:]:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                if path in seen:
                    continue
                seen.add(path)
                paths.append(path)
    return paths


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
