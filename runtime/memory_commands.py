from __future__ import annotations

from typing import Any

from .arg_resolver import resolve_command_args
from .errors import MemoryCommandError
from .models import StepRuntime, TaskFrame, MemoryResult
from .memory_store import MemoryStore
from .taskframe import add_audit_event, record_error, set_output


class MemoryCommandRunner:
    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> MemoryResult:
        step.status = "RUNNING"
        try:
            if step.kind != "memory":
                raise MemoryCommandError(f"Unsupported memory step kind: {step.kind}")
            if not step.output_alias:
                raise MemoryCommandError("Memory command requires an output alias.")

            parsed_args = resolve_command_args(frame, _step_args(step))
            action = step.action
            if action == "delete":
                raise MemoryCommandError("Memory delete is not implemented in Spec 008.")
            if action == "get":
                result = self._run_get(frame, step, parsed_args)
            elif action == "set":
                result = self._run_set(frame, step, parsed_args)
            elif action == "list":
                result = self._run_list(frame, step, parsed_args)
            else:
                raise MemoryCommandError(f"Unsupported memory action: {action}")

            set_output(frame, step.output_alias, _memory_result_payload(result))
            step.result_ref = step.output_alias
            step.status = "COMPLETED"
            add_audit_event(
                frame,
                "MEMORY_" + action.upper(),
                f"Memory command completed: {action}",
                {
                    "step_id": step.step_id,
                    "action": action,
                    "output_alias": step.output_alias,
                    "key": result.key,
                },
            )
            return result
        except MemoryCommandError as exc:
            step.status = "FAILED"
            step.error = str(exc)
            step.last_error = str(exc)
            record_error(
                frame,
                "memory_command_error",
                str(exc),
                {"step_id": step.step_id, "action": step.action},
            )
            add_audit_event(
                frame,
                "MEMORY_COMMAND_FAILED",
                str(exc),
                {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            step.status = "FAILED"
            step.error = str(exc)
            step.last_error = str(exc)
            record_error(
                frame,
                "memory_command_error",
                str(exc),
                {"step_id": step.step_id, "action": step.action},
            )
            add_audit_event(
                frame,
                "MEMORY_COMMAND_FAILED",
                str(exc),
                {"step_id": step.step_id, "action": step.action, "output_alias": step.output_alias},
            )
            raise MemoryCommandError(str(exc)) from exc

    def _run_get(self, frame: TaskFrame, step: StepRuntime, args: dict[str, str]) -> MemoryResult:
        key = _require_arg(args, "key")
        memory_result = self.store.get(key)
        return MemoryResult(
            ok=True,
            action="get",
            key=key,
            value=memory_result.value,
            found=memory_result.found,
            metadata={"output_alias": step.output_alias},
        )

    def _run_set(self, frame: TaskFrame, step: StepRuntime, args: dict[str, str]) -> MemoryResult:
        key = _require_arg(args, "key")
        if "value" not in args:
            raise MemoryCommandError("Memory set requires value.")
        value = args["value"]
        stored = self.store.set(
            key,
            value,
            metadata={
                "source": "manifest",
                "frame_id": frame.frame_id,
                "step_id": step.step_id,
            },
        )
        return MemoryResult(
            ok=True,
            action="set",
            key=key,
            value=value,
            found=True,
            metadata={"stored": True, "output_alias": step.output_alias, **stored.metadata},
        )

    def _run_list(self, frame: TaskFrame, step: StepRuntime, args: dict[str, str]) -> MemoryResult:
        prefix = args.get("prefix", "")
        memory_result = self.store.list(prefix=prefix)
        return MemoryResult(
            ok=True,
            action="list",
            items=list(memory_result.items),
            metadata={"prefix": prefix, "count": len(memory_result.items), "output_alias": step.output_alias},
        )


def _step_args(step: StepRuntime) -> dict[str, str]:
    from .command_parser import parse_command

    return parse_command(step.command).args


def _require_arg(args: dict[str, str], name: str) -> str:
    value = args.get(name)
    if value is None or value == "":
        raise MemoryCommandError(f"Memory command requires {name}.")
    return value


def _memory_result_payload(result: MemoryResult) -> dict[str, Any]:
    if result.action == "get":
        return {"found": result.found, "key": result.key, "value": result.value}
    if result.action == "set":
        payload = {"ok": result.ok, "key": result.key, "value": result.value, "stored": True}
        payload.update({k: v for k, v in result.metadata.items() if k not in payload})
        return payload
    if result.action == "list":
        return {
            "prefix": result.metadata.get("prefix", ""),
            "count": result.metadata.get("count", len(result.items)),
            "items": list(result.items),
        }
    return {
        "ok": result.ok,
        "action": result.action,
        "key": result.key,
        "value": result.value,
        "items": list(result.items),
        "found": result.found,
        "metadata": dict(result.metadata),
    }
