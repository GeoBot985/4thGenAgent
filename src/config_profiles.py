from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_CONFIG_DIR = ROOT / "config"
CONFIG_EXAMPLES_DIR = REPO_CONFIG_DIR / "examples"
DEFAULT_USER_CONFIG_DIR = Path.home() / ".taskframe"
DEFAULT_RUNTIME_DATA_DIR = Path("runtime_data")
DEFAULT_PROFILE = "default"
PROFILE_FILE_TEMPLATE = "taskframe.{profile}.json"
PROFILE_EXAMPLE_TEMPLATE = "taskframe.{profile}.example.json"
ACCOUNTING_EXAMPLE_FILE = "accounting_google_sheet.example.json"


@dataclass(frozen=True)
class ConfigProfile:
    name: str
    config_dir: Path
    runtime_data_dir: Path
    llm_provider: str
    ollama_model: str
    ollama_base_url: str
    google_credentials_path: Path | None
    google_token_path: Path | None
    accounting_sheet_config_path: Path | None
    rpa_browser_user_data_dir: Path | None
    optional_rpa_enabled: bool
    google_enabled: bool
    rpa_enabled: bool
    live_execution_enabled: bool
    active_config_file: Path | None = None
    source: str = "internal"
    raw: dict[str, Any] = field(default_factory=dict)


def resolve_config_dir(cli_config_dir: str | Path | None = None) -> Path:
    if cli_config_dir:
        return Path(cli_config_dir).expanduser()
    env_dir = os.getenv("TASKFRAME_CONFIG_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return DEFAULT_USER_CONFIG_DIR


def resolve_runtime_data_dir(cli_runtime_data_dir: str | Path | None = None) -> Path:
    if cli_runtime_data_dir:
        return Path(cli_runtime_data_dir).expanduser()
    env_dir = os.getenv("TASKFRAME_RUNTIME_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return DEFAULT_RUNTIME_DATA_DIR


def resolve_profile_name(cli_profile: str | None = None) -> str:
    value = (cli_profile or os.getenv("TASKFRAME_PROFILE") or DEFAULT_PROFILE).strip()
    return value or DEFAULT_PROFILE


def profile_file_path(profile: str, config_dir: str | Path | None = None) -> Path:
    return resolve_config_dir(config_dir) / PROFILE_FILE_TEMPLATE.format(profile=profile)


def example_profile_path(profile: str) -> Path:
    return CONFIG_EXAMPLES_DIR / PROFILE_EXAMPLE_TEMPLATE.format(profile=profile)


def resolve_accounting_config_path(config_dir: str | Path | None = None) -> Path:
    explicit = os.getenv("TASKFRAME_ACCOUNTING_SHEET_CONFIG", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    user_path = resolve_config_dir(config_dir) / "accounting_google_sheet.json"
    if user_path.is_file():
        return user_path
    repo_path = REPO_CONFIG_DIR / "accounting_google_sheet.json"
    return repo_path


def resolve_google_credentials_path(config_dir: str | Path | None = None) -> Path:
    user_dir = resolve_config_dir(config_dir)
    candidates = [
        user_dir / "google" / "credentials.json",
        user_dir / "credentials.json",
        Path.home() / ".taskframe" / "google" / "credentials.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def resolve_google_token_path(config_dir: str | Path | None = None) -> Path:
    user_dir = resolve_config_dir(config_dir)
    candidates = [
        user_dir / "google" / "google_token.json",
        user_dir / "google_token.json",
        Path.home() / ".taskframe" / "google" / "google_token.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_config_profile(
    profile_name: str | None = None,
    *,
    config_dir: str | Path | None = None,
    runtime_data_dir: str | Path | None = None,
) -> ConfigProfile:
    resolved_profile = resolve_profile_name(profile_name)
    resolved_config_dir = resolve_config_dir(config_dir)

    active_config_file = profile_file_path(resolved_profile, resolved_config_dir)
    raw, source = _load_profile_json(resolved_profile, resolved_config_dir)
    profile_data = dict(raw)

    runtime_value = _resolve_runtime_dir(runtime_data_dir, profile_data.get("runtime_data_dir"))
    llm_data = dict(profile_data.get("llm") or {})
    google_data = dict(profile_data.get("google") or {})
    rpa_data = dict(profile_data.get("rpa") or {})
    accounting_data = dict(profile_data.get("accounting") or {})
    live_execution_data = dict(profile_data.get("live_execution") or {})

    llm_provider = _override_string("TASKFRAME_LLM_PROVIDER", _string_or_default(llm_data.get("provider"), "fake"))
    ollama_model = _override_string("TASKFRAME_OLLAMA_MODEL", _string_or_default(llm_data.get("ollama_model"), "granite3.3:8b"))
    ollama_base_url = _override_string("TASKFRAME_OLLAMA_BASE_URL", _string_or_default(llm_data.get("ollama_base_url"), "http://127.0.0.1:11434"))

    google_enabled = _string_to_bool(google_data.get("enabled"), default=False)
    rpa_enabled = _string_to_bool(rpa_data.get("enabled"), default=False)
    optional_rpa_enabled = _string_to_bool(os.getenv("ENABLE_OPTIONAL_RPA_TOOLS", ""), default=False) or rpa_enabled
    live_execution_enabled = _string_to_bool(live_execution_data.get("enabled"), default=False)

    credentials_path = _resolved_optional_path(
        google_data.get("credentials_path"),
        default=Path.home() / ".taskframe" / "google" / "credentials.json",
    )
    token_path = _resolved_optional_path(
        google_data.get("token_path"),
        default=Path.home() / ".taskframe" / "google" / "google_token.json",
    )
    accounting_sheet_path = _resolved_optional_path(
        accounting_data.get("sheet_config_path"),
        default=resolve_accounting_config_path(resolved_config_dir),
    )
    rpa_user_data_dir = _resolved_optional_path(
        rpa_data.get("browser_user_data_dir"),
        default=None,
    )

    return ConfigProfile(
        name=resolved_profile,
        config_dir=resolved_config_dir,
        runtime_data_dir=Path(runtime_value).expanduser(),
        llm_provider=llm_provider,
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url,
        google_credentials_path=credentials_path,
        google_token_path=token_path,
        accounting_sheet_config_path=accounting_sheet_path,
        rpa_browser_user_data_dir=rpa_user_data_dir,
        optional_rpa_enabled=optional_rpa_enabled,
        google_enabled=google_enabled,
        rpa_enabled=rpa_enabled,
        live_execution_enabled=live_execution_enabled,
        active_config_file=active_config_file if active_config_file.is_file() else None,
        source=source,
        raw=profile_data,
    )


def describe_config_profile(profile: ConfigProfile) -> dict[str, Any]:
    return {
        "profile": profile.name,
        "config_dir": str(profile.config_dir),
        "runtime_data_dir": str(profile.runtime_data_dir),
        "llm_provider": profile.llm_provider,
        "ollama_model": profile.ollama_model,
        "ollama_base_url": profile.ollama_base_url,
        "google_enabled": profile.google_enabled,
        "google_credentials_path": str(profile.google_credentials_path) if profile.google_credentials_path else "",
        "google_token_path": str(profile.google_token_path) if profile.google_token_path else "",
        "accounting_sheet_config_path": str(profile.accounting_sheet_config_path) if profile.accounting_sheet_config_path else "",
        "rpa_enabled": profile.rpa_enabled,
        "rpa_browser_user_data_dir": str(profile.rpa_browser_user_data_dir) if profile.rpa_browser_user_data_dir else "",
        "optional_rpa_enabled": profile.optional_rpa_enabled,
        "live_execution_enabled": profile.live_execution_enabled,
        "active_config_file": str(profile.active_config_file) if profile.active_config_file else "<default internal config>",
        "source": profile.source,
    }


def list_config_lookup_paths(profile_name: str | None = None, config_dir: str | Path | None = None) -> dict[str, Any]:
    resolved_profile = resolve_profile_name(profile_name)
    resolved_config_dir = resolve_config_dir(config_dir)
    return {
        "explicit_config_dir": str(config_dir) if config_dir else "<none>",
        "taskframe_config_dir": os.getenv("TASKFRAME_CONFIG_DIR", "<not set>"),
        "user_config_dir": str(DEFAULT_USER_CONFIG_DIR),
        "repo_config_examples": str(CONFIG_EXAMPLES_DIR),
        "active_profile": resolved_profile,
        "active_config_file": str(profile_file_path(resolved_profile, resolved_config_dir)) if profile_file_path(resolved_profile, resolved_config_dir).is_file() else "<default internal config>",
        "runtime_data_dir": str(resolve_runtime_data_dir()),
    }


def copy_profile_example(profile_name: str, *, force: bool = False, config_dir: str | Path | None = None) -> Path:
    resolved_profile = resolve_profile_name(profile_name)
    source = example_profile_path(resolved_profile)
    if not source.is_file():
        raise FileNotFoundError(f"Example config file not found: {source}")
    destination_dir = resolve_config_dir(config_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / PROFILE_FILE_TEMPLATE.format(profile=resolved_profile)
    if destination.exists() and not force:
        raise FileExistsError(f"Config file already exists: {destination}")
    shutil.copyfile(source, destination)
    return destination


def _load_profile_json(profile: str, config_dir: Path) -> tuple[dict[str, Any], str]:
    user_file = profile_file_path(profile, config_dir)
    if user_file.is_file():
        return _load_json(user_file), "user"
    example = example_profile_path(profile)
    if example.is_file():
        return _load_json(example), "example"
    return _default_profile_data(profile), "internal"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _default_profile_data(profile: str) -> dict[str, Any]:
    base = {
        "profile": profile,
        "runtime_data_dir": str(DEFAULT_RUNTIME_DATA_DIR),
        "llm": {
            "provider": "fake",
            "ollama_model": "granite3.3:8b",
            "ollama_base_url": "http://127.0.0.1:11434",
        },
        "google": {
            "enabled": False,
            "credentials_path": "",
            "token_path": "",
        },
        "rpa": {
            "enabled": False,
            "browser_user_data_dir": "",
            "browser_profile_dir": "",
        },
        "live_execution": {"enabled": False},
    }
    if profile == "local-llm":
        base["llm"]["provider"] = "ollama"
    if profile == "google-live":
        base["google"]["enabled"] = True
        base["google"]["credentials_path"] = str(Path.home() / ".taskframe" / "google" / "credentials.json")
        base["google"]["token_path"] = str(Path.home() / ".taskframe" / "google" / "google_token.json")
        base["accounting"] = {"sheet_config_path": str(Path.home() / ".taskframe" / "accounting_google_sheet.json")}
    if profile == "rpa-local":
        base["rpa"]["enabled"] = True
    return base


def _resolved_optional_path(value: Any, default: Path | None) -> Path | None:
    raw = _string_or_default(value, "")
    if raw:
        return Path(raw).expanduser()
    return default.expanduser() if default is not None else None


def _override_string(name: str, fallback: str) -> str:
    value = os.getenv(name, "").strip()
    return value or fallback


def _string_or_default(value: Any, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _string_to_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "enabled"}


def _resolve_runtime_dir(cli_runtime_data_dir: str | Path | None, profile_runtime_data_dir: Any) -> str:
    if cli_runtime_data_dir:
        return str(Path(cli_runtime_data_dir).expanduser())
    env_runtime = os.getenv("TASKFRAME_RUNTIME_DIR", "").strip()
    if env_runtime:
        return str(Path(env_runtime).expanduser())
    text = str(profile_runtime_data_dir).strip() if profile_runtime_data_dir is not None else ""
    return text or str(DEFAULT_RUNTIME_DATA_DIR)
