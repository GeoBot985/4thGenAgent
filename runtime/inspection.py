from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_cleanup import get_cleanup_dir
from .models import InspectionResult, inspection_error, inspection_ok
from .persistence import DEFAULT_RUNTIME_DATA_DIR, get_summary_path, get_taskframe_path, read_json
from .run_ledger import get_ledger_path, read_ledger_records


class RunInspector:
    def __init__(self, runtime_data_dir: str | Path = "runtime_data"):
        self.runtime_data_dir = Path(runtime_data_dir)

    def list_runs(self, limit: int = 20) -> InspectionResult:
        records = read_ledger_records(self.runtime_data_dir)
        latest: dict[str, dict[str, Any]] = {}
        for record in records:
            frame_id = record.get("frame_id")
            if not frame_id:
                continue
            latest[frame_id] = record
        ordered = sorted(latest.values(), key=lambda item: str(item.get("updated_at", "")), reverse=True)
        if limit is not None:
            ordered = ordered[: int(limit)]
        return inspection_ok(
            "list_runs",
            {"count": len(ordered), "runs": ordered},
            metadata={"ledger_path": str(get_ledger_path(self.runtime_data_dir))},
        )

    def get_run_summary(self, frame_id: str) -> InspectionResult:
        return self._read_frame_file(frame_id, "summary", get_summary_path(frame_id, self.runtime_data_dir))

    def get_taskframe(self, frame_id: str) -> InspectionResult:
        return self._read_frame_file(frame_id, "taskframe", get_taskframe_path(frame_id, self.runtime_data_dir))

    def get_outputs(self, frame_id: str) -> InspectionResult:
        path = Path(self.runtime_data_dir) / "runs" / frame_id / "outputs.json"
        if not path.is_file():
            return inspection_error("outputs", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        outputs = read_json(path)
        return inspection_ok(
            "outputs",
            {"frame_id": frame_id, "output_keys": sorted(outputs.keys()) if isinstance(outputs, dict) else [], "outputs": outputs},
            frame_id=frame_id,
        )

    def get_audit(self, frame_id: str, limit: int | None = None) -> InspectionResult:
        audit = self._artifact_file(frame_id, "audit.json")
        if not audit.is_file():
            return inspection_error("audit", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        events = read_json(audit)
        if not isinstance(events, list):
            return inspection_error("audit", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        if limit is not None:
            events = events[-int(limit) :]
        return inspection_ok("audit", {"frame_id": frame_id, "count": len(events), "audit": events}, frame_id=frame_id)

    def get_validations(self, frame_id: str, failed_only: bool = False) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "validations")
        if taskframe is None:
            return inspection_error("validations", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        validations = taskframe.get("validations", [])
        if not isinstance(validations, list):
            validations = []
        if failed_only:
            validations = [item for item in validations if isinstance(item, dict) and item.get("ok") is False]
        return inspection_ok(
            "validations",
            {"frame_id": frame_id, "count": len(validations), "failed_only": failed_only, "validations": validations},
            frame_id=frame_id,
        )

    def get_errors(self, frame_id: str) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "errors")
        if taskframe is None:
            return inspection_error("errors", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        return inspection_ok("errors", {"frame_id": frame_id, "count": len(taskframe.get("errors", [])), "errors": taskframe.get("errors", [])}, frame_id=frame_id)

    def get_pending_actions(self, frame_id: str) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "pending_actions")
        if taskframe is None:
            return inspection_error("pending_actions", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        pending = taskframe.get("pending_actions", [])
        return inspection_ok("pending_actions", {"frame_id": frame_id, "count": len(pending), "pending_actions": pending}, frame_id=frame_id)

    def get_executed_actions(self, frame_id: str) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "executed_actions")
        if taskframe is None:
            return inspection_error("executed_actions", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        executed = taskframe.get("executed_actions", [])
        return inspection_ok("executed_actions", {"frame_id": frame_id, "count": len(executed), "executed_actions": executed}, frame_id=frame_id)

    def get_attempts(self, frame_id: str) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "attempts")
        if taskframe is None:
            return inspection_error("attempts", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        attempts = taskframe.get("attempts", [])
        return inspection_ok("attempts", {"frame_id": frame_id, "count": len(attempts), "attempts": attempts}, frame_id=frame_id)

    def get_tool_calls(self, frame_id: str) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "tool_calls")
        if taskframe is None:
            return inspection_error("tool_calls", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        tool_calls = taskframe.get("tool_calls", [])
        return inspection_ok("tool_calls", {"frame_id": frame_id, "count": len(tool_calls), "tool_calls": tool_calls}, frame_id=frame_id)

    def get_llm_calls(self, frame_id: str) -> InspectionResult:
        taskframe = self._taskframe_dict_or_error(frame_id, "llm_calls")
        if taskframe is None:
            return inspection_error("llm_calls", f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        llm_calls = taskframe.get("llm_calls", [])
        return inspection_ok("llm_calls", {"frame_id": frame_id, "count": len(llm_calls), "llm_calls": llm_calls}, frame_id=frame_id)

    def get_cleanup_reports(self) -> InspectionResult:
        cleanup_dir = get_cleanup_dir(self.runtime_data_dir)
        if not cleanup_dir.is_dir():
            return inspection_ok("cleanup_reports", {"count": 0, "cleanup_reports": []})

        cleanup_reports: list[dict[str, Any]] = []
        for path in sorted(cleanup_dir.glob("cleanup_*.json")):
            if not path.is_file():
                continue
            data = read_json(path)
            if not isinstance(data, dict):
                continue
            summary = data.get("summary", {})
            if not isinstance(summary, dict):
                summary = {}
            cleanup_reports.append(
                {
                    "cleanup_id": str(data.get("cleanup_id", "")),
                    "path": str(path),
                    "dry_run": bool(data.get("dry_run", True)),
                    "created_at": str(data.get("created_at", "")),
                    "candidate_count": int(summary.get("candidate_count", 0) or 0),
                    "deleted_count": int(summary.get("deleted_count", 0) or 0),
                    "error_count": int(summary.get("error_count", 0) or 0),
                }
            )
        return inspection_ok("cleanup_reports", {"count": len(cleanup_reports), "cleanup_reports": cleanup_reports})

    def _artifact_file(self, frame_id: str, filename: str) -> Path:
        return Path(self.runtime_data_dir) / "runs" / frame_id / filename

    def _read_frame_file(self, frame_id: str, action: str, path: Path) -> InspectionResult:
        if not path.is_file():
            return inspection_error(action, f"TaskFrame artifact not found: {frame_id}", frame_id=frame_id)
        data = read_json(path)
        return inspection_ok(action, data, frame_id=frame_id)

    def _taskframe_dict_or_error(self, frame_id: str, action: str) -> dict[str, Any] | None:
        path = get_taskframe_path(frame_id, self.runtime_data_dir)
        if not path.is_file():
            return None
        data = read_json(path)
        if not isinstance(data, dict):
            return None
        return data
