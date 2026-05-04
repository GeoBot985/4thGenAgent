from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_index import load_artifact_index, rebuild_and_save_artifact_index


class ArtifactSearcher:
    def __init__(self, runtime_data_dir: str | Path = "runtime_data"):
        self.runtime_data_dir = Path(runtime_data_dir)

    def search_failed_runs(self, limit: int = 20, rebuild: bool = True) -> dict[str, Any]:
        records = self._records(rebuild)
        matched = [record for record in records if str(record.get("state", "")).startswith("FAILED_") or bool(record.get("has_errors", False))]
        return self._wrap("failed_runs", matched[: int(limit)])

    def search_pending_runs(self, limit: int = 20, rebuild: bool = True) -> dict[str, Any]:
        records = self._records(rebuild)
        matched = [record for record in records if bool(record.get("has_pending_actions", False))]
        return self._wrap("pending_runs", matched[: int(limit)])

    def search_live_packs(self, limit: int = 20, rebuild: bool = True) -> dict[str, Any]:
        records = self._records(rebuild)
        matched = [record for record in records if bool(record.get("has_approval_packs", False))]
        return self._wrap("live_packs", matched[: int(limit)])

    def summarize(self, rebuild: bool = True) -> dict[str, Any]:
        records = self._records(rebuild)
        return {
            "index_record_count": len(records),
            "failed_runs": sum(1 for record in records if str(record.get("state", "")).startswith("FAILED_") or bool(record.get("has_errors", False))),
            "pending_runs": sum(1 for record in records if bool(record.get("has_pending_actions", False))),
            "runs_with_reports": sum(1 for record in records if bool(record.get("has_reports", False))),
            "runs_with_approval_packs": sum(1 for record in records if bool(record.get("has_approval_packs", False))),
            "live_execution_runs": sum(1 for record in records if bool(record.get("has_live_execution", False))),
        }

    def _records(self, rebuild: bool) -> list[dict[str, Any]]:
        if rebuild:
            data = rebuild_and_save_artifact_index(self.runtime_data_dir)
        else:
            data = load_artifact_index(self.runtime_data_dir)
        records = data.get("records", [])
        return records if isinstance(records, list) else []

    def _wrap(self, name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {"action": name, "count": len(records), "runs": records}
