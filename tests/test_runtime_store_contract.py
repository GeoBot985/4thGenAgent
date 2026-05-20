from __future__ import annotations

from pathlib import Path

from runtime.runtime_store import ensure_runtime_store_layout, get_runtime_store_paths, runtime_store_contract


def test_runtime_store_contract_exposes_expected_folders(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_data"
    paths = get_runtime_store_paths(runtime_root)

    assert set(paths) == {
        "taskframes",
        "reports",
        "approval_packs",
        "evidence",
        "tool_health",
        "indexes",
        "backups",
        "cleanup",
        "migrations",
    }

    ensured = ensure_runtime_store_layout(runtime_root)
    assert all(path.is_dir() for path in ensured.values())


def test_runtime_store_contract_is_explicit_and_inspectable(tmp_path: Path) -> None:
    contract = runtime_store_contract(tmp_path / "runtime_data")

    assert contract["schema_version"] == 1
    assert "layout" in contract
    assert "backup_manifest_name" in contract
    assert "index_path" in contract
