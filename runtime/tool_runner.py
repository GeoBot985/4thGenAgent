from __future__ import annotations

import asyncio
import importlib
import inspect
from typing import Any
from uuid import uuid4

from .arg_resolver import resolve_command_args
from .errors import (
    ArgumentResolutionError,
    LiveToolExecutionBlocked,
    LiveExecutionBlocked,
    ToolArgumentError,
    ToolExecutionBlocked,
    ToolFunctionError,
    ToolImportError,
    ToolNotRegisteredError,
    ToolResultNormalizationError,
)
from .live_execution import assert_live_execution_allowed
from .live_guardrails import run_live_guardrail
from .models import StepRuntime, TaskFrame, ToolResult
from .command_parser import parse_command
from .pending_actions import transition_pending_action
from .taskframe import (
    add_audit_event,
    record_error,
    set_output,
    tool_result_error,
    tool_result_ok,
    transition_state,
    utc_now,
)
from .tool_registry import coerce_tool_args, get_tool_spec, tool_key, validate_tool_args


class ToolRunner:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> ToolResult:
        step.status = "RUNNING"
        parsed = parse_command(step.command)
        tool_call = _make_tool_call_record(
            step=step,
            tool=None,
            function="",
            args={},
            dry_run=self.dry_run,
            live=False,
        )
        frame.tool_calls.append(tool_call)

        if step.kind not in {"tool", "pending"}:
            message = f"Unsupported step kind: {step.kind}"
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            record_error(frame, "unsupported_step_kind", message, {"step_id": step.step_id})
            frame.state = "FAILED_EXECUTION"
            add_audit_event(frame, "STEP_UNSUPPORTED", message, {"step_id": step.step_id})
            _finalize_tool_call(tool_call, ok=False, result_type="step_failed", error=message, dry_run=self.dry_run, live=False)
            return tool_result_error(
                "step_failed",
                message,
                metadata={"step_id": step.step_id, "error_type": "UnsupportedStepKind", "tag": "unknown"},
            )

        if not step.namespace or not step.action:
            message = "Tool step is missing namespace or action."
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            record_error(frame, "tool_lookup_failed", message, {"step_id": step.step_id})
            frame.state = "FAILED_EXECUTION"
            _finalize_tool_call(tool_call, ok=False, result_type="step_failed", error=message, dry_run=self.dry_run, live=False)
            return tool_result_error(
                "step_failed",
                message,
                metadata={"step_id": step.step_id, "error_type": "ToolExecutionError", "tag": "unknown"},
            )

        key = tool_key(step.namespace, step.action)
        try:
            tool_spec = get_tool_spec(step.namespace, step.action)
        except ToolNotRegisteredError as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            record_error(frame, "tool_not_registered", message, {"tool": key, "step_id": step.step_id})
            frame.state = "FAILED_EXECUTION"
            _finalize_tool_call(tool_call, ok=False, result_type="step_failed", error=message, dry_run=self.dry_run, live=False)
            return tool_result_error(
                "step_failed",
                message,
                metadata={"tool": key, "step_id": step.step_id, "error_type": "ToolNotRegisteredError", "tag": "unknown"},
            )

        try:
            resolved_args = resolve_command_args(frame, parsed.args)
        except ArgumentResolutionError as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            record_error(frame, "argument_resolution_failed", message, {"tool": key, "step_id": step.step_id})
            frame.state = "FAILED_EXECUTION"
            _finalize_tool_call(tool_call, ok=False, result_type="step_failed", error=message, dry_run=self.dry_run, live=False)
            return tool_result_error(
                "step_failed",
                message,
                metadata={"tool": key, "step_id": step.step_id, "error_type": "ArgumentResolutionError", "tag": "unknown"},
            )

        try:
            validate_tool_args(tool_spec, resolved_args)
            coerced_args = coerce_tool_args(tool_spec, {k: v for k, v in resolved_args.items() if isinstance(v, str)})
            for arg_key, arg_value in resolved_args.items():
                if arg_key not in coerced_args:
                    coerced_args[arg_key] = arg_value
        except ToolArgumentError as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            record_error(frame, "tool_argument_error", message, {"tool": key, "step_id": step.step_id})
            frame.state = "FAILED_EXECUTION"
            _finalize_tool_call(tool_call, ok=False, result_type="step_failed", error=message, dry_run=self.dry_run, live=False)
            return tool_result_error(
                "step_failed",
                message,
                metadata={"tool": key, "step_id": step.step_id, "error_type": "ToolArgumentError", "tag": "unknown"},
            )

        tool_call.update(
            {
                "tool": key,
                "namespace": step.namespace,
                "action": step.action,
                "function": tool_spec["function"],
                "args": dict(coerced_args),
                "output_alias": step.output_alias,
                "source": str(tool_spec.get("source", "legacy_fallback")),
                "toolpack_id": str(tool_spec.get("toolpack_id", "")),
                "toolpack_name": str(tool_spec.get("toolpack_name", "")),
            }
        )

        if should_stage_command(step.kind, tool_spec):
            pending_action = create_pending_action(frame, step, tool_spec, coerced_args)
            frame.pending_actions.append(pending_action)
            step.result_ref = pending_action["action_id"]
            step.status = "STAGED"
            if step.output_alias and key in {"supplier/prepare_message_action", "customer/prepare_message_action", "sheet/prepare_write_rows"}:
                set_output(frame, step.output_alias, pending_action)
            if frame.state == "RUNNING":
                transition_state(frame, "WAITING_FOR_EXECUTE")
            add_audit_event(
                frame,
                "PENDING_ACTION_STAGED",
                "Step staged as pending action.",
                {"step_id": step.step_id, "tool": key, "action_id": pending_action["action_id"]},
            )
            result = tool_result_ok("pending_action", data=pending_action, metadata={"staged": True})
            _finalize_tool_call(
                tool_call,
                ok=True,
                result_type=result.type,
                error="",
                dry_run=self.dry_run,
                live=False,
            )
            return result

        if self.dry_run and tool_spec.get("dry_run_executes"):
            add_audit_event(
                frame,
                "TOOL_DRY_RUN_READONLY_EXECUTION_STARTED",
                "Read-only tool executed during dry-run.",
                {
                    "step_id": step.step_id,
                    "tool": key,
                    "function": tool_spec["function"],
                    "args": dict(coerced_args),
                },
            )
            try:
                func = import_tool_function(tool_spec["module"], tool_spec["function"])
                raw_result = call_tool_function(func, coerced_args)
                result = normalize_tool_result(raw_result, key, tool_spec, coerced_args, dry_run=True)
            except (ToolImportError, ToolFunctionError, ToolResultNormalizationError) as exc:
                result = tool_result_error(
                    tool_spec["output_type"],
                    str(exc),
                    metadata={
                        "tool": key,
                        "function": tool_spec["function"],
                        "live": False,
                        "dry_run": True,
                        "exception_type": type(exc).__name__,
                        "error_type": type(exc).__name__,
                        "tag": "transient",
                    },
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                result = tool_result_error(
                    tool_spec["output_type"],
                    str(exc),
                    metadata={
                        "tool": key,
                        "function": tool_spec["function"],
                        "live": False,
                        "dry_run": True,
                        "exception_type": type(exc).__name__,
                        "error_type": type(exc).__name__,
                        "tag": "unknown",
                    },
                )
            if step.output_alias and result.ok:
                set_output(frame, step.output_alias, result.data)
                step.result_ref = step.output_alias
                if key in {"customer/extract_order_ref", "order/extract_ref_from_text"} and isinstance(result.data, dict) and result.data.get("order_ref"):
                    set_output(frame, "order_id", result.data.get("order_ref"))
                if key == "customer/read" and isinstance(result.data, dict) and isinstance(result.data.get("customer"), dict):
                    set_output(frame, "customer", result.data.get("customer"))
                if key == "order/read" and isinstance(result.data, dict) and isinstance(result.data.get("order"), dict):
                    set_output(frame, "order", result.data.get("order"))
                if key == "shipment/read" and isinstance(result.data, dict) and isinstance(result.data.get("shipment"), dict):
                    set_output(frame, "shipment", result.data.get("shipment"))
                if key == "payment/read_by_order" and isinstance(result.data, dict) and isinstance(result.data.get("payment"), dict):
                    set_output(frame, "payment", result.data.get("payment"))
                if key == "customer/order_context" and isinstance(result.data, dict):
                    for alias in ("customer", "order", "shipment", "payment"):
                        if alias in result.data:
                            set_output(frame, alias, result.data.get(alias))
                    set_output(frame, "business_lookups", result.data)
                if key == "customer/build_status_context" and isinstance(result.data, dict):
                    set_output(frame, "order_context", result.data)
                    set_output(frame, "status_context", result.data)
                    set_output(frame, "business_lookups", result.data)
                if key == "order_context/build" and isinstance(result.data, dict):
                    set_output(frame, "order_context", result.data)
                if key == "customer/validate_owns_order" and isinstance(result.data, dict):
                    set_output(frame, "ownership_check", result.data)
                if key in {"customer/validate_status_reply", "message/validate_customer_status_reply"} and isinstance(result.data, dict):
                    set_output(frame, "reply_validation", result.data)
                if key == "customer/prepare_message_action" and isinstance(result.data, dict):
                    set_output(frame, "customer_reply_send", result.data)
                if key == "customer/order_context" and isinstance(result.data, dict) and isinstance(result.data.get("evidence"), list):
                    frame.evidence.extend([item for item in result.data.get("evidence", []) if isinstance(item, dict)])
                if key == "customer/build_status_context" and isinstance(result.data, dict):
                    frame.evidence.append({"kind": "business_lookup", "step_id": step.step_id, "datasets": result.data.get("evidence", [])})
            if result.ok:
                step.status = "COMPLETED"
            else:
                step.status = "FAILED"
                step.error = result.error
                step.last_error = result.error
                frame.state = tool_spec.get("failure_state", "FAILED_EXECUTION")
                record_error(
                    frame,
                    "live_tool_execution_failed",
                    result.error,
                    {
                        "step_id": step.step_id,
                        "tool": key,
                        "function": tool_spec["function"],
                        "error_type": result.metadata.get("exception_type", "ToolFunctionError"),
                        "tag": "transient",
                    },
                )
            _finalize_tool_call(
                tool_call,
                ok=result.ok,
                result_type=result.type,
                error=result.error,
                dry_run=True,
                live=False,
            )
            return result

        if self.dry_run:
            result = dry_run_tool_result(key, tool_spec, coerced_args)
            if step.output_alias:
                set_output(frame, step.output_alias, result.data)
                step.result_ref = step.output_alias
                if key in {"customer/order_context", "customer/build_status_context", "order_context/build"}:
                    set_output(frame, "business_lookups", result.data)
            step.status = "COMPLETED"
            add_audit_event(
                frame,
                "TOOL_STEP_COMPLETED",
                "Step completed in dry-run mode.",
                {"step_id": step.step_id, "tool": key, "output_alias": step.output_alias},
            )
            _finalize_tool_call(
                tool_call,
                ok=result.ok,
                result_type=result.type,
                error=result.error,
                dry_run=True,
                live=False,
            )
            return result

        if tool_spec.get("side_effect") or not tool_spec.get("allow_live", False):
            message = f"Live execution is blocked for tool: {key}"
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "live_tool_execution_blocked",
                message,
                {
                    "step_id": step.step_id,
                    "tool": key,
                    "function": tool_spec["function"],
                    "side_effect": tool_spec["side_effect"],
                    "allow_live": tool_spec.get("allow_live", False),
                },
            )
            add_audit_event(
                frame,
                "TOOL_LIVE_EXECUTION_BLOCKED",
                message,
                {
                    "step_id": step.step_id,
                    "tool": key,
                    "function": tool_spec["function"],
                    "side_effect": tool_spec["side_effect"],
                    "allow_live": tool_spec.get("allow_live", False),
                },
            )
            result = tool_result_error(
                tool_spec["output_type"],
                message,
                metadata={
                    "tool": key,
                    "function": tool_spec["function"],
                    "live": False,
                    "dry_run": False,
                    "error_type": "LiveToolExecutionBlocked",
                    "tag": "policy",
                },
            )
            _finalize_tool_call(
                tool_call,
                ok=False,
                result_type=result.type,
                error=message,
                dry_run=False,
                live=False,
            )
            return result

        result = self.execute_live_tool(frame, step, key, tool_spec, coerced_args)
        if step.output_alias and result.ok:
            set_output(frame, step.output_alias, result.data)
            step.result_ref = step.output_alias

        if result.ok:
            step.status = "COMPLETED"
        else:
            step.status = "FAILED"
            step.error = result.error
            step.last_error = result.error
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "live_tool_execution_failed",
                result.error,
                {
                    "step_id": step.step_id,
                    "tool": key,
                    "function": tool_spec["function"],
                    "error_type": result.metadata.get("exception_type", "ToolFunctionError"),
                    "tag": "transient",
                },
            )

        _finalize_tool_call(
            tool_call,
            ok=result.ok,
            result_type=result.type,
            error=result.error,
            dry_run=False,
            live=True,
        )
        return result

    def execute_live_tool(
        self,
        frame: TaskFrame,
        step: StepRuntime,
        tool_key: str,
        tool_spec: dict,
        args: dict[str, object],
    ) -> ToolResult:
        if self.dry_run:
            raise LiveToolExecutionBlocked("Live tool execution is not available when ToolRunner.dry_run is True.")
        if tool_spec.get("side_effect") or not tool_spec.get("allow_live", False):
            raise LiveToolExecutionBlocked(f"Live execution is blocked for tool: {tool_key}")

        audit_data = {
            "step_id": step.step_id,
            "tool": tool_key,
            "function": tool_spec["function"],
            "args": dict(args),
            "side_effect": tool_spec["side_effect"],
            "allow_live": tool_spec.get("allow_live", False),
        }
        add_audit_event(frame, "TOOL_LIVE_EXECUTION_STARTED", "Live tool execution started.", audit_data)

        try:
            func = import_tool_function(tool_spec["module"], tool_spec["function"])
            raw_result = call_tool_function(func, args)
            result = normalize_tool_result(raw_result, tool_key, tool_spec, args, dry_run=False)
        except (ToolImportError, ToolFunctionError, ToolResultNormalizationError) as exc:
            failure = tool_result_error(
                tool_spec["output_type"],
                str(exc),
                metadata={
                    "tool": tool_key,
                    "function": tool_spec["function"],
                    "live": True,
                    "dry_run": False,
                    "exception_type": type(exc).__name__,
                    "error_type": type(exc).__name__,
                    "tag": "transient",
                },
            )
            add_audit_event(
                frame,
                "TOOL_LIVE_EXECUTION_FAILED",
                str(exc),
                {
                    **audit_data,
                    "exception_type": type(exc).__name__,
                },
            )
            return failure
        except Exception as exc:  # pragma: no cover - defensive guard
            failure = tool_result_error(
                tool_spec["output_type"],
                str(exc),
                metadata={
                    "tool": tool_key,
                    "function": tool_spec["function"],
                    "live": True,
                    "dry_run": False,
                    "exception_type": type(exc).__name__,
                    "error_type": type(exc).__name__,
                    "tag": "unknown",
                },
            )
            add_audit_event(
                frame,
                "TOOL_LIVE_EXECUTION_FAILED",
                str(exc),
                {
                    **audit_data,
                    "exception_type": type(exc).__name__,
                },
            )
            return failure

        event_type = "TOOL_LIVE_EXECUTION_COMPLETED" if result.ok else "TOOL_LIVE_EXECUTION_FAILED"
        add_audit_event(frame, event_type, "Live tool execution finished.", {**audit_data, "ok": result.ok})
        return result

    def execute_pending_action(
        self,
        frame: TaskFrame,
        pending_action: dict,
    ) -> ToolResult:
        if not self.dry_run:
            raise ToolExecutionBlocked("Live pending-action execution is not implemented in Spec 005.")

        action_id = pending_action.get("action_id", "")
        tool = pending_action.get("tool")
        output_alias = pending_action.get("output_alias")
        namespace = pending_action.get("namespace")
        action_name = pending_action.get("action")
        status = pending_action.get("status")

        if status != "APPROVED":
            message = f"Pending action must be APPROVED before execution: {status}"
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            record_error(frame, "pending_action_not_approved", message, {"action_id": action_id, "tool": tool})
            add_audit_event(frame, "PENDING_ACTION_FAILED", message, {"action_id": action_id, "tool": tool})
            return tool_result_error(
                "pending_action_failed",
                message,
                metadata={"action_id": action_id, "tool": tool},
            )

        if not tool or not namespace or not action_name:
            message = "Pending action is missing tool metadata."
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            record_error(frame, "pending_action_invalid", message, {"action_id": action_id, "tool": tool})
            add_audit_event(frame, "PENDING_ACTION_FAILED", message, {"action_id": action_id, "tool": tool})
            return tool_result_error("pending_action_failed", message, metadata={"action_id": action_id, "tool": tool})

        lookup_tool = tool if isinstance(tool, str) and "/" in tool else None
        try:
            if lookup_tool:
                lookup_namespace, lookup_action = lookup_tool.split("/", 1)
                tool_spec = get_tool_spec(lookup_namespace, lookup_action)
            else:
                tool_spec = get_tool_spec(namespace, action_name)
        except ToolNotRegisteredError as exc:
            message = str(exc)
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            record_error(frame, "tool_not_registered", message, {"action_id": action_id, "tool": tool})
            add_audit_event(frame, "PENDING_ACTION_FAILED", message, {"action_id": action_id, "tool": tool})
            return tool_result_error("pending_action_failed", message, metadata={"action_id": action_id, "tool": tool})

        if output_alias is None or output_alias == "":
            message = "Pending action missing output alias."
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            record_error(frame, "pending_action_missing_output", message, {"action_id": action_id, "tool": tool})
            add_audit_event(frame, "PENDING_ACTION_FAILED", message, {"action_id": action_id, "tool": tool})
            return tool_result_error("pending_action_failed", message, metadata={"action_id": action_id, "tool": tool})

        args = dict(pending_action.get("args", {}))
        if tool in {"gb/book", "gb/cancel"}:
            args["confirm"] = False
        pending_action["args"] = dict(args)
        allowed_args = set(tool_spec.get("required_args", [])) | set(tool_spec.get("optional_args", []))
        exec_args = {key: value for key, value in args.items() if key in allowed_args}

        try:
            validate_tool_args(tool_spec, exec_args)
        except ToolArgumentError as exc:
            message = str(exc)
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            record_error(frame, "tool_argument_error", message, {"action_id": action_id, "tool": tool})
            add_audit_event(frame, "PENDING_ACTION_FAILED", message, {"action_id": action_id, "tool": tool})
            return tool_result_error("pending_action_failed", message, metadata={"action_id": action_id, "tool": tool})

        transition_pending_action(pending_action, "EXECUTING")
        add_audit_event(
            frame,
            "PENDING_ACTION_EXECUTING",
            "Pending action executing in dry-run mode.",
            {"action_id": action_id, "tool": tool, "output_alias": output_alias},
        )

        result = None
        if "dry_run" in tool_spec.get("optional_args", []):
            try:
                func = import_tool_function(tool_spec["module"], tool_spec["function"])
                call_args = dict(exec_args)
                call_args["dry_run"] = True
                raw_result = call_tool_function(func, call_args)
                result = normalize_tool_result(raw_result, tool, tool_spec, call_args, dry_run=True)
            except (ToolImportError, ToolFunctionError, ToolResultNormalizationError) as exc:
                result = tool_result_error(
                    tool_spec["output_type"],
                    str(exc),
                    metadata={
                        "action_id": action_id,
                        "tool": tool,
                        "function": tool_spec["function"],
                        "live_side_effect": False,
                        "dry_run": True,
                        "error_type": type(exc).__name__,
                        "tag": "transient",
                    },
                )
        if result is None:
            result = tool_result_ok(
                tool_spec["output_type"],
                data={
                    "dry_run": True,
                    "approved_execution": True,
                    "tool": tool,
                    "function": tool_spec["function"],
                    "args": exec_args,
                },
                metadata={
                    "action_id": action_id,
                    "side_effect": True,
                    "requires_approval": True,
                    "executed_from_pending_action": True,
                },
            )

        if output_alias:
            set_output(frame, output_alias, result.data)

        executed_record = {
            "action_id": action_id,
            "step_id": pending_action.get("step_id"),
            "tool": tool,
            "namespace": namespace,
            "action": action_name,
            "output_alias": output_alias,
            "args": dict(exec_args),
            "status": "EXECUTED",
            "dry_run": True,
            "result_type": tool_spec["output_type"],
            "executed_at": utc_now(),
        }
        frame.executed_actions.append(executed_record)
        frame.tool_calls.append(
            {
                "step_id": pending_action.get("step_id"),
                "kind": "pending",
                "namespace": namespace,
                "action": action_name,
                "output_alias": output_alias,
                "command": pending_action.get("tool"),
                "created_at": utc_now(),
                "action_id": action_id,
                "phase": "approved_execution",
                "function": tool_spec["function"],
                "args": dict(exec_args),
                "ok": True,
                "result_type": tool_spec["output_type"],
                "dry_run": True,
                "live": False,
                "error": "",
                "timestamp": utc_now(),
            }
        )
        transition_pending_action(pending_action, "EXECUTED")
        pending_action["executed_at"] = utc_now()
        pending_action["dry_run"] = True
        pending_action["result_type"] = tool_spec["output_type"]
        add_audit_event(
            frame,
            "PENDING_ACTION_EXECUTED",
            "Pending action executed in dry-run mode.",
            {"action_id": action_id, "tool": tool, "output_alias": output_alias},
        )
        return result

    def execute_live_pending_action(
        self,
        frame: TaskFrame,
        manifest,
        pending_action: dict[str, Any],
        runtime_live_mode: bool = False,
    ) -> ToolResult:
        if self.dry_run:
            raise LiveExecutionBlocked("Live pending-action execution requires ToolRunner.dry_run=False.")
        action_id = pending_action.get("action_id", "")
        tool = pending_action.get("tool")
        output_alias = pending_action.get("output_alias")
        namespace = pending_action.get("namespace")
        action_name = pending_action.get("action")

        if pending_action.get("status") != "APPROVED":
            message = f"Pending action must be APPROVED before live execution: {pending_action.get('status')}"
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(frame, "pending_action_not_approved", message, {"action_id": action_id, "tool": tool})
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_BLOCKED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": pending_action.get("guardrail", ""),
                    "args": dict(pending_action.get("args", {})),
                },
            )
            return tool_result_error(
                "pending_action_failed",
                message,
                metadata={"action_id": action_id, "tool": tool, "live_side_effect": True},
            )

        if not tool or not namespace or not action_name:
            message = "Pending action is missing tool metadata."
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(frame, "pending_action_invalid", message, {"action_id": action_id, "tool": tool})
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_BLOCKED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": pending_action.get("guardrail", ""),
                    "args": dict(pending_action.get("args", {})),
                },
            )
            return tool_result_error("pending_action_failed", message, metadata={"action_id": action_id, "tool": tool})

        lookup_tool = tool if isinstance(tool, str) and "/" in tool else None
        try:
            if lookup_tool:
                lookup_namespace, lookup_action = lookup_tool.split("/", 1)
                tool_spec = get_tool_spec(lookup_namespace, lookup_action)
            else:
                tool_spec = get_tool_spec(namespace, action_name)
        except ToolNotRegisteredError as exc:
            message = str(exc)
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(frame, "tool_not_registered", message, {"action_id": action_id, "tool": tool})
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_BLOCKED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": pending_action.get("guardrail", ""),
                    "args": dict(pending_action.get("args", {})),
                },
            )
            return tool_result_error("pending_action_failed", message, metadata={"action_id": action_id, "tool": tool})

        add_audit_event(
            frame,
            "LIVE_EXECUTION_POLICY_CHECK_STARTED",
            "Live execution policy check started.",
            {
                "frame_id": frame.frame_id,
                "action_id": action_id,
                "tool": tool,
                "manifest_id": getattr(manifest, "manifest_id", ""),
                "runtime_live_mode": runtime_live_mode,
                "guardrail": tool_spec.get("live_guardrail"),
                "args": dict(pending_action.get("args", {})),
            },
        )
        try:
            assert_live_execution_allowed(frame, manifest, pending_action, tool_spec, runtime_live_mode=runtime_live_mode)
        except Exception as exc:
            message = str(exc)
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "live_execution_blocked",
                message,
                {
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": tool_spec.get("live_guardrail"),
                },
            )
            add_audit_event(
                frame,
                "LIVE_EXECUTION_POLICY_CHECK_FAILED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": tool_spec.get("live_guardrail"),
                    "args": dict(pending_action.get("args", {})),
                },
            )
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_BLOCKED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": tool_spec.get("live_guardrail"),
                    "args": dict(pending_action.get("args", {})),
                },
            )
            return tool_result_error(
                "pending_action_failed",
                message,
                metadata={
                    "action_id": action_id,
                    "tool": tool,
                    "error_type": type(exc).__name__,
                    "tag": "policy",
                    "live_side_effect": True,
                },
            )
        add_audit_event(
            frame,
            "LIVE_EXECUTION_POLICY_CHECK_PASSED",
            "Live execution policy check passed.",
            {
                "frame_id": frame.frame_id,
                "action_id": action_id,
                "tool": tool,
                "manifest_id": getattr(manifest, "manifest_id", ""),
                "runtime_live_mode": runtime_live_mode,
                "guardrail": tool_spec.get("live_guardrail"),
                "args": dict(pending_action.get("args", {})),
            },
        )

        guardrail_name = str(tool_spec.get("live_guardrail", "blocked"))
        add_audit_event(
            frame,
            "LIVE_GUARDRAIL_CHECK_STARTED",
            "Live guardrail check started.",
            {
                "frame_id": frame.frame_id,
                "action_id": action_id,
                "tool": tool,
                "manifest_id": getattr(manifest, "manifest_id", ""),
                "runtime_live_mode": runtime_live_mode,
                "guardrail": guardrail_name,
                "args": dict(pending_action.get("args", {})),
            },
        )
        guardrail_result = run_live_guardrail(guardrail_name, pending_action, tool_spec)
        if not guardrail_result.get("ok", False):
            message = str(guardrail_result.get("error", "Live guardrail check failed."))
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "live_guardrail_failed",
                message,
                {
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                },
            )
            add_audit_event(
                frame,
                "LIVE_GUARDRAIL_CHECK_FAILED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                    "args": dict(pending_action.get("args", {})),
                    "checks": guardrail_result.get("checks", []),
                },
            )
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_BLOCKED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                    "args": dict(pending_action.get("args", {})),
                },
            )
            return tool_result_error(
                "pending_action_failed",
                message,
                metadata={
                    "action_id": action_id,
                    "tool": tool,
                    "guardrail": guardrail_name,
                    "live_side_effect": True,
                },
            )
        add_audit_event(
            frame,
            "LIVE_GUARDRAIL_CHECK_PASSED",
            "Live guardrail check passed.",
            {
                "frame_id": frame.frame_id,
                "action_id": action_id,
                "tool": tool,
                "manifest_id": getattr(manifest, "manifest_id", ""),
                "runtime_live_mode": runtime_live_mode,
                "guardrail": guardrail_name,
                "args": dict(pending_action.get("args", {})),
                "checks": guardrail_result.get("checks", []),
            },
        )

        transition_pending_action(pending_action, "EXECUTING")
        add_audit_event(
            frame,
            "LIVE_SIDE_EFFECT_EXECUTION_STARTED",
            "Live side effect execution started.",
            {
                "frame_id": frame.frame_id,
                "action_id": action_id,
                "tool": tool,
                "manifest_id": getattr(manifest, "manifest_id", ""),
                "runtime_live_mode": runtime_live_mode,
                "guardrail": guardrail_name,
                "args": dict(pending_action.get("args", {})),
            },
        )

        try:
            func = import_tool_function(tool_spec["module"], tool_spec["function"])
            live_args = dict(pending_action.get("args", {}))
            if "dry_run" in set(tool_spec.get("optional_args", [])):
                live_args["dry_run"] = False
            raw_result = call_tool_function(func, live_args)
            normalized = normalize_tool_result(raw_result, tool, tool_spec, live_args, dry_run=False)
            if not normalized.ok:
                raise ToolFunctionError(normalized.error or "Live tool returned failure.")
            live_data = {
                "live": True,
                "dry_run": False,
                "approved_execution": True,
                "tool": tool,
                "function": tool_spec["function"],
                "args": live_args,
                "result": normalized.data,
            }
            result = tool_result_ok(
                tool_spec["output_type"],
                data=live_data,
                metadata={
                    "action_id": action_id,
                    "side_effect": True,
                    "requires_approval": True,
                    "executed_from_pending_action": True,
                    "live_side_effect": True,
                    "guardrail": guardrail_name,
                },
            )
        except (ToolImportError, ToolFunctionError, ToolResultNormalizationError) as exc:
            message = str(exc)
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "live_side_effect_execution_failed",
                message,
                {
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                },
            )
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_FAILED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                    "args": dict(pending_action.get("args", {})),
                },
            )
            pending_action["executed_at"] = utc_now()
            pending_action["live"] = True
            pending_action["live_side_effect"] = True
            return tool_result_error(
                tool_spec["output_type"],
                message,
                metadata={
                    "action_id": action_id,
                    "tool": tool,
                    "guardrail": guardrail_name,
                    "live_side_effect": True,
                    "error_type": type(exc).__name__,
                    "tag": "transient",
                },
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            message = str(exc)
            pending_action["status"] = "FAILED"
            pending_action["last_error"] = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "live_side_effect_execution_failed",
                message,
                {
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                },
            )
            add_audit_event(
                frame,
                "LIVE_SIDE_EFFECT_EXECUTION_FAILED",
                message,
                {
                    "frame_id": frame.frame_id,
                    "action_id": action_id,
                    "tool": tool,
                    "manifest_id": getattr(manifest, "manifest_id", ""),
                    "runtime_live_mode": runtime_live_mode,
                    "guardrail": guardrail_name,
                    "args": dict(pending_action.get("args", {})),
                },
            )
            pending_action["executed_at"] = utc_now()
            pending_action["live"] = True
            pending_action["live_side_effect"] = True
            return tool_result_error(
                tool_spec["output_type"],
                message,
                metadata={
                    "action_id": action_id,
                    "tool": tool,
                    "guardrail": guardrail_name,
                    "live_side_effect": True,
                    "error_type": type(exc).__name__,
                    "tag": "unknown",
                },
            )

        if output_alias:
            set_output(frame, output_alias, result.data)

        executed_record = {
            "action_id": action_id,
            "step_id": pending_action.get("step_id"),
            "tool": tool,
            "namespace": namespace,
            "action": action_name,
            "output_alias": output_alias,
            "args": dict(pending_action.get("args", {})),
            "status": "EXECUTED",
            "dry_run": False,
            "live": True,
            "live_side_effect": True,
            "guardrail": guardrail_name,
            "result_type": tool_spec["output_type"],
            "executed_at": utc_now(),
        }
        frame.executed_actions.append(executed_record)
        frame.tool_calls.append(
            {
                "step_id": pending_action.get("step_id"),
                "kind": "pending",
                "namespace": namespace,
                "action": action_name,
                "output_alias": output_alias,
                "command": pending_action.get("tool"),
                "created_at": utc_now(),
                "action_id": action_id,
                "phase": "live_execution",
                "function": tool_spec["function"],
                "args": dict(pending_action.get("args", {})),
                "ok": True,
                "result_type": tool_spec["output_type"],
                "dry_run": False,
                "live": True,
                "error": "",
                "timestamp": utc_now(),
            }
        )
        transition_pending_action(pending_action, "EXECUTED")
        pending_action["executed_at"] = utc_now()
        pending_action["dry_run"] = False
        pending_action["live"] = True
        pending_action["live_side_effect"] = True
        pending_action["guardrail"] = guardrail_name
        pending_action["result_type"] = tool_spec["output_type"]
        add_audit_event(
            frame,
            "LIVE_SIDE_EFFECT_EXECUTION_COMPLETED",
            "Live side effect execution completed.",
            {
                "frame_id": frame.frame_id,
                "action_id": action_id,
                "tool": tool,
                "manifest_id": getattr(manifest, "manifest_id", ""),
                "runtime_live_mode": runtime_live_mode,
                "guardrail": guardrail_name,
                "args": dict(pending_action.get("args", {})),
            },
        )
        return result


def import_tool_function(module_path: str, function_name: str):
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:  # pragma: no cover - exercised in failure tests
        raise ToolImportError(f"Tool module could not be imported: {module_path}") from exc

    try:
        return getattr(module, function_name)
    except AttributeError as exc:
        raise ToolImportError(f"Tool function not found: {module_path}.{function_name}") from exc


def call_tool_function(func, args: dict[str, object]):
    try:
        result = func(**args)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        return result
    except ToolImportError:
        raise
    except Exception as exc:
        raise ToolFunctionError(str(exc)) from exc


def normalize_tool_result(
    result: object,
    tool_key: str,
    tool_spec: dict,
    args: dict[str, object],
    dry_run: bool,
) -> ToolResult:
    metadata_base = {
        "tool": tool_key,
        "function": tool_spec["function"],
        "live": not dry_run,
        "dry_run": dry_run,
    }

    if isinstance(result, ToolResult):
        metadata = dict(result.metadata)
        metadata.update(metadata_base)
        return ToolResult(
            ok=result.ok,
            type=result.type,
            data=result.data,
            evidence=list(result.evidence),
            error=result.error,
            raw=result.raw,
            metadata=metadata,
        )

    if _is_workspace_result_like(result):
        payload = getattr(result, "payload", None)
        action_name = getattr(result, "action")
        if action_name in {"customer_read", "order_read", "shipment_read", "order_context_build"} and isinstance(payload, dict):
            data = payload
        else:
            data = {
                "action": action_name,
                "output": getattr(result, "output"),
                "payload": payload,
            }
        error = getattr(result, "error", "") or ""
        ok = bool(getattr(result, "ok"))
        return ToolResult(
            ok=ok,
            type=tool_spec["output_type"],
            data=data,
            evidence=[],
            error=error,
            raw=result,
            metadata=metadata_base,
        )

    if isinstance(result, dict):
        ok_value = result.get("ok")
        if isinstance(ok_value, bool):
            error = str(result.get("error") or result.get("message") or "")
            metadata = dict(metadata_base)
            metadata["tool_result"] = dict(result)
            if not ok_value:
                metadata["error_type"] = error or "ToolResultError"
                metadata["tag"] = "validation" if error else "unknown"
            return ToolResult(
                ok=ok_value,
                type=tool_spec["output_type"],
                data=result,
                evidence=[],
                error=error,
                raw=result,
                metadata=metadata,
            )
        return ToolResult(
            ok=True,
            type=tool_spec["output_type"],
            data=result,
            evidence=[],
            error="",
            raw=result,
            metadata=metadata_base,
        )

    if result is None or isinstance(result, (list, str, bool, int, float)):
        return ToolResult(
            ok=True,
            type=tool_spec["output_type"],
            data=result,
            evidence=[],
            error="",
            raw=result,
            metadata=metadata_base,
        )

    if _is_simple_object(result):
        return ToolResult(
            ok=True,
            type=tool_spec["output_type"],
            data=result,
            evidence=[],
            error="",
            raw=result,
            metadata=metadata_base,
        )

    raise ToolResultNormalizationError(
        f"Unsupported tool result type for {tool_key}: {type(result).__name__}"
    )


def create_pending_action(
    frame: TaskFrame,
    step: StepRuntime,
    tool_spec: dict,
    args: dict[str, object],
) -> dict[str, object]:
    tool = tool_key(tool_spec["namespace"], tool_spec["action"])
    staged_args = dict(args)
    if tool in {"gb/book", "gb/cancel"}:
        staged_args["confirm"] = False
    if tool == "customer/prepare_message_action":
        customer = args.get("customer") if isinstance(args.get("customer"), dict) else {}
        message = args.get("message") if isinstance(args.get("message"), dict) else {}
        staged_args = {
            "customer": customer,
            "customer_id": str(customer.get("customer_id", "") or args.get("customer_id", "")),
            "chat": str(customer.get("whatsapp_chat") or customer.get("name") or customer.get("customer_id") or ""),
            "channel": str(args.get("channel", "")),
            "message": message,
            "reply": str(message.get("reply") or message.get("body") or args.get("reply") or args.get("body") or ""),
            "draft_po": args.get("draft_po", {}),
        }
    if tool == "supplier/prepare_message_action":
        supplier = args.get("supplier") if isinstance(args.get("supplier"), dict) else {}
        message = args.get("message") if isinstance(args.get("message"), dict) else {}
        draft_po = args.get("draft_po") if isinstance(args.get("draft_po"), dict) else {}
        staged_args = {
            "to": str(supplier.get("email", "")),
            "subject": str(message.get("subject", f"Purchase Order {draft_po.get('po_id', '')}")),
            "body": str(message.get("body", "")),
            "draft_po": draft_po,
            "supplier": supplier,
            "message": message,
        }
    if tool == "sheet/prepare_write_rows":
        staged_args = {
            "spreadsheet_id": str(args.get("spreadsheet_id", "")),
            "range_name": str(args.get("range_name", "")),
            "rows": args.get("rows", []),
            "mode": str(args.get("mode", "append")),
            "dry_run": True,
        }
    action_type = "send_customer_message" if tool == "customer/prepare_message_action" else "send_supplier_message" if tool == "supplier/prepare_message_action" else "sheet_write_rows" if tool == "sheet/prepare_write_rows" else tool_spec["action"]
    staged_tool = "wa/send" if tool == "customer/prepare_message_action" else "supplier/send_message" if tool == "supplier/prepare_message_action" else "sheet/write_rows" if tool == "sheet/prepare_write_rows" else tool
    body_value = ""
    if tool in {"customer/prepare_message_action", "supplier/prepare_message_action"}:
        message = staged_args.get("message", staged_args.get("reply"))
        if isinstance(message, dict):
            body_value = str(message.get("reply") or message.get("body") or "")
        else:
            body_value = str(message or staged_args.get("body") or "")

    return {
        "action_id": f"pa_{uuid4().hex}",
        "step_id": step.step_id,
        "tool": staged_tool,
        "namespace": tool_spec["namespace"],
        "action": tool_spec["action"],
        "action_type": action_type,
        "output_alias": step.output_alias,
        "args": staged_args,
        "body": body_value,
        "status": "PENDING_APPROVAL",
        "side_effect": True,
        "requires_approval": True,
        "created_at": utc_now(),
    }


def dry_run_tool_result(
    tool_key: str,
    tool_spec: dict,
    args: dict[str, object],
) -> ToolResult:
    return tool_result_ok(
        tool_spec["output_type"],
        data={
            "dry_run": True,
            "tool": tool_key,
            "function": tool_spec["function"],
            "args": args,
        },
        metadata={
            "side_effect": tool_spec["side_effect"],
            "requires_approval": tool_spec["requires_approval"],
        },
    )


def should_stage_command(parsed_kind: str, tool_spec: dict) -> bool:
    return parsed_kind == "pending" or bool(tool_spec.get("side_effect"))


def _make_tool_call_record(
    step: StepRuntime,
    tool: str | None,
    function: str,
    args: dict[str, object],
    dry_run: bool,
    live: bool,
) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "kind": step.kind,
        "namespace": step.namespace,
        "action": step.action,
        "output_alias": step.output_alias,
        "command": step.command,
        "created_at": utc_now(),
        "tool": tool,
        "function": function,
        "args": dict(args),
        "ok": None,
        "result_type": "",
        "dry_run": dry_run,
        "live": live,
        "error": "",
        "timestamp": utc_now(),
    }


def _finalize_tool_call(
    tool_call: dict[str, Any],
    *,
    ok: bool,
    result_type: str,
    error: str,
    dry_run: bool,
    live: bool,
) -> None:
    tool_call.update(
        {
            "ok": ok,
            "result_type": result_type,
            "dry_run": dry_run,
            "live": live,
            "error": error,
            "timestamp": utc_now(),
        }
    )


def _is_workspace_result_like(result: object) -> bool:
    return all(hasattr(result, attr) for attr in ("ok", "action", "output", "error"))


def _is_simple_object(result: object) -> bool:
    return hasattr(result, "__dict__") and not isinstance(result, type)
