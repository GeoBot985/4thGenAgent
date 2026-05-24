from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4
from typing import Any


VALID_WORKER_ROLES = {"customer_support", "procurement", "accounting", "general"}
VALID_ENVIRONMENTS = {"demo", "dev", "test", "release", "pilot", "service", "live"}


@dataclass(frozen=True)
class WorkerIdentity:
    worker_id: str
    worker_role: str
    environment: str
    operator_id: str
    approval_authority: str
    runtime_instance_id: str

    def to_dict(self) -> dict[str, Any]:
        return dict(asdict(self))


def generate_runtime_instance_id() -> str:
    return f"runtime_{uuid4().hex}"


def build_worker_identity(
    raw: dict[str, Any] | None = None,
    *,
    worker_id: str | None = None,
    worker_role: str | None = None,
    environment: str | None = None,
    operator_id: str | None = None,
    approval_authority: str | None = None,
    runtime_instance_id: str | None = None,
) -> dict[str, Any]:
    data = dict(raw or {})
    resolved_worker_id = _first_non_empty(worker_id, data.get("worker_id"))
    resolved_worker_role = _first_non_empty(worker_role, data.get("worker_role"), default="general")
    resolved_environment = _first_non_empty(environment, data.get("environment"), default="service")
    resolved_operator_id = _first_non_empty(operator_id, data.get("operator_id"), default="system")
    resolved_approval_authority = _first_non_empty(approval_authority, data.get("approval_authority"), default="system")
    resolved_runtime_instance_id = _first_non_empty(runtime_instance_id, data.get("runtime_instance_id"), default="")
    if not resolved_runtime_instance_id:
        resolved_runtime_instance_id = generate_runtime_instance_id()

    identity = WorkerIdentity(
        worker_id=resolved_worker_id,
        worker_role=resolved_worker_role,
        environment=resolved_environment,
        operator_id=resolved_operator_id,
        approval_authority=resolved_approval_authority,
        runtime_instance_id=resolved_runtime_instance_id,
    )
    validation = validate_worker_identity(identity.to_dict())
    if not validation["ok"]:
        raise ValueError("; ".join(validation["errors"]))
    return identity.to_dict()


def validate_worker_identity(identity: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(identity, dict):
        return {"ok": False, "errors": ["worker identity must be a dict"]}

    worker_id = _first_non_empty(identity.get("worker_id"))
    worker_role = _first_non_empty(identity.get("worker_role"), default="general")
    environment = _first_non_empty(identity.get("environment"), default="service")
    operator_id = _first_non_empty(identity.get("operator_id"), default="system")
    approval_authority = _first_non_empty(identity.get("approval_authority"), default="system")
    runtime_instance_id = _first_non_empty(identity.get("runtime_instance_id"))

    if not worker_id:
        errors.append("worker_id is required")
    if worker_role not in VALID_WORKER_ROLES:
        errors.append(f"worker_role must be one of: {sorted(VALID_WORKER_ROLES)}")
    if environment not in VALID_ENVIRONMENTS:
        errors.append(f"environment must be one of: {sorted(VALID_ENVIRONMENTS)}")
    if not operator_id:
        errors.append("operator_id is required")
    if not approval_authority:
        errors.append("approval_authority is required")
    if not runtime_instance_id:
        errors.append("runtime_instance_id is required")

    return {"ok": not errors, "errors": errors}


def _first_non_empty(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return default
