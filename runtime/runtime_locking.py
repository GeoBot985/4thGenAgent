from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from .persistence import ensure_dir, read_json, write_json_atomic
from .runtime_versions import bump_runtime_version, read_runtime_version
from .taskframe import utc_now


T = TypeVar("T")
LOCK_DIR_NAME = "locks"
LOCK_SUFFIX = ".lock"
DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0
DEFAULT_LOCK_TTL_SECONDS = 5.0
AUDIT_DIR_NAME = "runtime_store_audit"
AUDIT_FILE_NAME = "runtime_store_audit.jsonl"


@dataclass(frozen=True)
class RuntimeLock:
    resource_key: str
    lock_id: str
    owner: str
    pid: int
    created_at: str
    expires_at: str
    path: str


class RuntimeLockError(RuntimeError):
    pass


class RuntimeLockTimeoutError(RuntimeLockError):
    pass


def get_runtime_lock_dir(runtime_data_dir: str | Path = "runtime_data") -> Path:
    return Path(runtime_data_dir) / LOCK_DIR_NAME


def get_runtime_lock_path(resource_key: str, runtime_data_dir: str | Path = "runtime_data") -> Path:
    safe = _safe_resource_key(resource_key)
    return get_runtime_lock_dir(runtime_data_dir) / f"{safe}{LOCK_SUFFIX}"


def acquire_runtime_lock(
    resource_key: str,
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    *,
    owner: str = "runtime",
    runtime_data_dir: str | Path = "runtime_data",
    ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS,
    request_id: str = "",
) -> RuntimeLock:
    if not str(resource_key or "").strip():
        raise RuntimeLockError("resource_key is required.")
    lock_dir = ensure_dir(get_runtime_lock_dir(runtime_data_dir))
    lock_path = get_runtime_lock_path(resource_key, runtime_data_dir)
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))

    while True:
        existing = _read_lock(lock_path)
        if existing and not _lock_is_expired(existing):
            if time.monotonic() >= deadline:
                _audit_lock_event(
                    runtime_data_dir,
                    "RUNTIME_LOCK_TIMEOUT",
                    resource_key=resource_key,
                    request_id=request_id,
                    details={"owner": owner},
                )
                raise RuntimeLockTimeoutError(f"Timed out waiting for lock: {resource_key}")
            time.sleep(0.05)
            continue

        if existing and _lock_is_expired(existing):
            _audit_lock_event(
                runtime_data_dir,
                "RUNTIME_LOCK_EXPIRED_RECLAIMED",
                resource_key=resource_key,
                request_id=request_id,
                details={"lock_id": str(existing.get("lock_id", "")), "owner": str(existing.get("owner", ""))},
            )
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass

        lock = RuntimeLock(
            resource_key=resource_key,
            lock_id=f"LOCK-{uuid.uuid4().hex}",
            owner=owner,
            pid=os.getpid(),
            created_at=utc_now(),
            expires_at=_future_timestamp(ttl_seconds),
            path=str(lock_path),
        )
        try:
            _write_lock_exclusive(lock_path, lock)
            _audit_lock_event(
                runtime_data_dir,
                "RUNTIME_LOCK_ACQUIRED",
                resource_key=resource_key,
                request_id=request_id,
                details={"lock_id": lock.lock_id, "owner": owner},
            )
            return lock
        except FileExistsError:
            if time.monotonic() >= deadline:
                _audit_lock_event(
                    runtime_data_dir,
                    "RUNTIME_LOCK_TIMEOUT",
                    resource_key=resource_key,
                    request_id=request_id,
                    details={"owner": owner},
                )
                raise RuntimeLockTimeoutError(f"Timed out waiting for lock: {resource_key}")
            time.sleep(0.05)


def release_runtime_lock(lock: RuntimeLock, runtime_data_dir: str | Path = "runtime_data", *, request_id: str = "") -> None:
    lock_path = Path(lock.path)
    existing = _read_lock(lock_path)
    if not existing:
        return
    if str(existing.get("lock_id", "")) != lock.lock_id:
        return
    try:
        lock_path.unlink(missing_ok=True)
    finally:
        _audit_lock_event(
            runtime_data_dir,
            "RUNTIME_LOCK_RELEASED",
            resource_key=lock.resource_key,
            request_id=request_id,
            details={"lock_id": lock.lock_id, "owner": lock.owner},
        )


def with_runtime_lock(
    resource_key: str,
    fn: Callable[[], T],
    *,
    owner: str = "runtime",
    runtime_data_dir: str | Path = "runtime_data",
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS,
    request_id: str = "",
) -> T:
    lock = acquire_runtime_lock(
        resource_key,
        timeout_seconds=timeout_seconds,
        owner=owner,
        runtime_data_dir=runtime_data_dir,
        ttl_seconds=ttl_seconds,
        request_id=request_id,
    )
    try:
        return fn()
    finally:
        release_runtime_lock(lock, runtime_data_dir, request_id=request_id)


def cleanup_expired_runtime_locks(runtime_data_dir: str | Path = "runtime_data") -> dict[str, Any]:
    lock_dir = get_runtime_lock_dir(runtime_data_dir)
    ensure_dir(lock_dir)
    removed: list[str] = []
    active: list[dict[str, Any]] = []
    for path in sorted(lock_dir.glob(f"*{LOCK_SUFFIX}")):
        existing = _read_lock(path)
        if not existing:
            continue
        if _lock_is_expired(existing):
            removed.append(path.name)
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            active.append(existing)
    return {"ok": True, "removed": removed, "active": active, "expired_count": len(removed), "active_count": len(active)}


def list_runtime_locks(runtime_data_dir: str | Path = "runtime_data") -> list[dict[str, Any]]:
    lock_dir = get_runtime_lock_dir(runtime_data_dir)
    if not lock_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(lock_dir.glob(f"*{LOCK_SUFFIX}")):
        existing = _read_lock(path)
        if existing:
            records.append(existing)
    return records


def mutate_runtime_json(
    path: str | Path,
    mutator: Callable[[dict[str, Any]], dict[str, Any] | None],
    *,
    expected_version: int | None = None,
    resource_key: str | None = None,
    runtime_data_dir: str | Path | None = None,
    owner: str = "runtime",
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    request_id: str = "",
) -> dict[str, Any]:
    target = Path(path)
    resource = resource_key or target.as_posix()
    runtime_root = runtime_data_dir or (target.parents[2] if len(target.parents) >= 3 else target.parent)
    lock: RuntimeLock | None = None
    try:
        lock = acquire_runtime_lock(resource, timeout_seconds=timeout_seconds, owner=owner, runtime_data_dir=runtime_root, request_id=request_id)
    except RuntimeLockTimeoutError as exc:
        _audit_lock_event(runtime_root, "RUNTIME_LOCK_TIMEOUT", resource_key=resource, request_id=request_id, details={"path": str(target)})
        return {"ok": False, "error": "LOCK_TIMEOUT", "message": str(exc), "path": str(target)}

    try:
        current = read_json(target)
        if not isinstance(current, dict):
            current = {}
        current_version = read_runtime_version(current)
        if expected_version is not None and current_version != int(expected_version):
            _audit_version_conflict(runtime_root, resource, expected_version, current_version, str(target), request_id=request_id)
            return {
                "ok": False,
                "error": "VERSION_CONFLICT",
                "expected_version": int(expected_version),
                "actual_version": current_version,
                "path": str(target),
            }

        updated = mutator(dict(current))
        if updated is None:
            updated = dict(current)
        if not isinstance(updated, dict):
            return {"ok": False, "error": "MUTATION_FAILED", "message": "Mutator must return a dict.", "path": str(target)}
        if updated.get("ok") is False and str(updated.get("error", "")).strip():
            return updated

        if read_runtime_version(updated) <= current_version:
            updated = bump_runtime_version(updated)
        else:
            updated = dict(updated)
            if not str(updated.get("updated_at", "") or "").strip():
                updated["updated_at"] = utc_now()
            updated.setdefault("schema_version", 1)

        write_json_atomic(target, updated)
        _audit_lock_event(
            runtime_root,
            "RUNTIME_MUTATION_COMMITTED",
            resource_key=resource,
            request_id=request_id,
            details={"path": str(target), "runtime_version": read_runtime_version(updated)},
        )
        return {"ok": True, "path": str(target), "runtime_version": read_runtime_version(updated), "data": updated}
    except RuntimeLockError:
        raise
    except Exception as exc:
        return {"ok": False, "error": "MUTATION_FAILED", "message": str(exc), "path": str(target)}
    finally:
        if lock is not None:
            release_runtime_lock(lock, runtime_root, request_id=request_id)


def _safe_resource_key(resource_key: str) -> str:
    safe = [ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(resource_key).strip()]
    return "".join(safe).strip("._") or "resource"


def _future_timestamp(ttl_seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(0.1, float(ttl_seconds)))).isoformat().replace("+00:00", "Z")


def _lock_is_expired(lock: dict[str, Any]) -> bool:
    expires_at = str(lock.get("expires_at", "") or "")
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except Exception:
        return True
    if expiry <= datetime.now(timezone.utc):
        return True
    pid = int(lock.get("pid", 0) or 0)
    if pid > 0 and not _pid_running(pid):
        return True
    return False


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _read_lock(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_lock_exclusive(path: Path, lock: RuntimeLock) -> None:
    ensure_dir(path.parent)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lock.__dict__, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _audit_lock_event(
    runtime_data_dir: str | Path,
    event_type: str,
    *,
    resource_key: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    record = {
        "event_type": event_type,
        "resource_key": resource_key,
        "expected_version": details.get("expected_version") if details else None,
        "actual_version": details.get("actual_version") if details else None,
        "request_id": request_id,
        "timestamp": utc_now(),
        "details": dict(details or {}),
    }
    audit_dir = ensure_dir(Path(runtime_data_dir) / AUDIT_DIR_NAME)
    with (audit_dir / AUDIT_FILE_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _audit_version_conflict(
    runtime_data_dir: str | Path,
    resource_key: str,
    expected_version: int,
    actual_version: int,
    path: str,
    *,
    request_id: str = "",
) -> None:
    _audit_lock_event(
        runtime_data_dir,
        "RUNTIME_VERSION_CONFLICT",
        resource_key=resource_key,
        request_id=request_id,
        details={"expected_version": expected_version, "actual_version": actual_version, "path": path},
    )
