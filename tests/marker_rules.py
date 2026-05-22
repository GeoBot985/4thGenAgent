from __future__ import annotations

from pathlib import Path


def markers_for_path(path: str | Path) -> set[str]:
    file_path = Path(path)
    name = file_path.name
    parts = {part.lower() for part in file_path.parts}
    markers: set[str] = set()

    if "integration" in parts:
        markers.update({"integration", "live", "full_ci"})

    if name.startswith("test_production_backend_"):
        markers.add("backend")

    if (
        name.startswith("test_manifest_")
        or name in {
            "test_event_router.py",
            "test_event_to_manifest_routing.py",
            "test_external_event_intake.py",
            "test_event_idempotency.py",
            "test_generated_manifest_smoke_runner.py",
            "test_event_source_route_alignment.py",
            "test_event_source_contracts.py",
            "test_event_source_builders.py",
            "test_event_source_registry.py",
        }
        or name.startswith("test_manifest_regression_gallery_")
    ):
        markers.update({"manifest", "smoke"})

    if name.startswith("test_manifest_regression_gallery_"):
        markers.update({"gallery", "slow"})

    if name.startswith("test_toolpack_") or name.startswith("test_builtin_toolpack_") or name in {
        "test_tool_inventory.py",
        "test_tool_registry_compat.py",
        "test_tool_result_contract.py",
        "test_tool_capabilities.py",
        "test_tool_health.py",
        "test_tool_contract_checklist.py",
    }:
        markers.add("toolpack")
        if name == "test_toolpack_manifest_execution.py":
            markers.add("full_ci")
            markers.add("live")

    if (
        name.startswith("test_runtime_")
        or name.startswith("test_taskframe_")
        or name.startswith("test_orchestrator_")
        or name.startswith("test_event_queue_")
        or name in {
            "test_event_queue.py",
            "test_event.py",
            "test_events.py",
            "test_scheduler.py",
            "test_conditions.py",
            "test_completion_gate.py",
            "test_retry_policy.py",
            "test_retry_tool_failures.py",
            "test_run_ledger.py",
            "test_live_execution_safety.py",
        }
    ):
        markers.add("runtime")
        if name == "test_runtime_engine.py":
            markers.add("full_ci")
            markers.add("live")

    if (
        "report" in name
        or "evidence" in name
        or "portfolio" in name
        or name.startswith("test_release_")
        or name.startswith("test_release_candidate_")
        or name.startswith("test_release_verifier_")
        or name.startswith("test_safety_verification")
    ):
        markers.add("reports")

    if (
        name.startswith("test_release_")
        or name.startswith("test_release_candidate_")
        or name.startswith("test_release_verifier_")
        or name.startswith("test_safety_verification")
    ):
        markers.add("full_ci")
        markers.add("release")

    if not markers and "live" not in name:
        markers.add("unit")

    return markers
