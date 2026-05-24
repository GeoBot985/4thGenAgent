from __future__ import annotations

from runtime.worker_identity import build_worker_identity, validate_worker_identity


def test_worker_identity_builds_and_generates_runtime_instance_id() -> None:
    identity = build_worker_identity(
        {
            "worker_id": "service-worker-1",
            "worker_role": "general",
            "environment": "service",
            "operator_id": "system",
            "approval_authority": "system",
        }
    )

    assert identity["worker_id"] == "service-worker-1"
    assert identity["worker_role"] == "general"
    assert identity["environment"] == "service"
    assert identity["operator_id"] == "system"
    assert identity["approval_authority"] == "system"
    assert identity["runtime_instance_id"].startswith("runtime_")
    assert validate_worker_identity(identity)["ok"] is True


def test_worker_identity_requires_worker_id() -> None:
    validation = validate_worker_identity(
        {
            "worker_role": "general",
            "environment": "service",
            "operator_id": "system",
            "approval_authority": "system",
            "runtime_instance_id": "runtime_123",
        }
    )

    assert validation["ok"] is False
    assert "worker_id is required" in validation["errors"]


def test_worker_identity_rejects_invalid_role_and_environment() -> None:
    validation = validate_worker_identity(
        {
            "worker_id": "w-1",
            "worker_role": "unknown",
            "environment": "prod",
            "operator_id": "system",
            "approval_authority": "system",
            "runtime_instance_id": "runtime_123",
        }
    )

    assert validation["ok"] is False
    assert any("worker_role" in error for error in validation["errors"])
    assert any("environment" in error for error in validation["errors"])
