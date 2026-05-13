from __future__ import annotations

from typing import Any

from .arg_resolver import resolve_command_args
from .command_parser import parse_command
from .errors import LLMActionNotAllowedError, LLMCommandError, LLMOutputParseError
from .llm_adapter import BaseLLMAdapter, FakeLLMAdapter, extract_json_from_text
from .llm_tools import LLMToolInputError, LLMToolNotFoundError, render_llm_prompt, validate_llm_output
from .llm_micro_tools import (
    is_llm_micro_tool,
    validate_micro_tool_output,
)
from .llm_prompts import (
    SYSTEM_PROMPT,
    build_classify_prompt,
    build_compare_prompt,
    build_draft_prompt,
    build_extract_prompt,
    build_summarize_prompt,
)
from .models import LLMResult, StepRuntime, TaskFrame, llm_result_error, llm_result_ok
from .taskframe import add_audit_event, record_error, set_output, utc_now


_LLM_ACTIONS = {
    "summarize",
    "extract",
    "classify",
    "draft",
    "compare",
    "extract_order_ref",
    "classify_customer_message",
    "summarize_customer_message",
    "summarize_business_context",
    "draft_customer_status_reply",
    "compare_reply_to_facts",
    "draft_supplier_reorder_message",
    "draft_reconciliation_exception_summary",
}


class LLMCommandRunner:
    def __init__(self, adapter: BaseLLMAdapter | None = None):
        self.adapter = adapter or FakeLLMAdapter()

    def run_step(self, frame: TaskFrame, step: StepRuntime) -> LLMResult:
        step.status = "RUNNING"
        parsed = None
        llm_call = _make_llm_call_record(step, provider=self._provider_name(), model=self._model_name())
        frame.llm_calls.append(llm_call)

        try:
            parsed = parse_command(step.command)
            if parsed.kind != "llm":
                raise LLMCommandError(f"Unsupported step kind for LLM runner: {parsed.kind}")
            if parsed.action not in _LLM_ACTIONS:
                raise LLMActionNotAllowedError(f"LLM action not allowed: {parsed.action}")
            if not parsed.output_alias:
                raise LLMCommandError("LLM commands require an output alias.")

            args = resolve_command_args(frame, parsed.args)
            if is_llm_micro_tool(parsed.action):
                return self._run_micro_tool(frame, step, parsed.action, parsed.output_alias, args, llm_call)
            prompt = self._build_prompt(parsed.action, args)
            add_audit_event(
                frame,
                "LLM_COMMAND_STARTED",
                "LLM command started.",
                {
                    "step_id": step.step_id,
                    "action": parsed.action,
                    "output_alias": parsed.output_alias,
                    "args": dict(args),
                },
            )
            raw_text = self.adapter.generate(
                prompt,
                system=SYSTEM_PROMPT,
                metadata={
                    "action": parsed.action,
                    "step_id": step.step_id,
                    "output_alias": parsed.output_alias,
                    "args": dict(args),
                },
            )
            result = self._normalize_result(parsed.action, parsed.output_alias, raw_text, args, llm_call)
            if result.ok:
                set_output(frame, parsed.output_alias, result.output)
                step.status = "COMPLETED"
                step.result_ref = parsed.output_alias
                add_audit_event(
                    frame,
                    "LLM_COMMAND_COMPLETED",
                    "LLM command completed.",
                    {
                        "step_id": step.step_id,
                        "action": parsed.action,
                        "output_alias": parsed.output_alias,
                    },
                )
            else:
                step.status = "FAILED"
                step.error = result.error
                step.last_error = result.error
                frame.state = "FAILED_EXECUTION"
                record_error(
                    frame,
                    "llm_command_failed",
                    result.error,
                    {
                        "step_id": step.step_id,
                        "action": parsed.action,
                        "output_alias": parsed.output_alias,
                    },
                )
                add_audit_event(
                    frame,
                    "LLM_COMMAND_FAILED",
                    result.error,
                    {
                        "step_id": step.step_id,
                        "action": parsed.action,
                        "output_alias": parsed.output_alias,
                    },
                )

            _finalize_llm_call(
                llm_call,
                ok=result.ok,
                result_type=f"llm_{parsed.action}_result",
                error=result.error,
                error_type=result.metadata.get("error_type", "") if isinstance(result.metadata, dict) else "",
                output_alias=parsed.output_alias,
                action=parsed.action,
                args=args,
                raw_output=raw_text,
                parsed_output=result.output if hasattr(result, "output") else None,
            )
            return result
        except Exception as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            frame.state = "FAILED_EXECUTION"
            record_error(
                frame,
                "llm_command_failed",
                message,
                {
                    "step_id": step.step_id,
                    "action": getattr(parsed, "action", step.action),
                    "output_alias": step.output_alias,
                },
            )
            add_audit_event(
                frame,
                "LLM_COMMAND_FAILED",
                message,
                {
                    "step_id": step.step_id,
                    "action": getattr(parsed, "action", step.action),
                    "output_alias": step.output_alias,
                },
            )
            _finalize_llm_call(
                llm_call,
                ok=False,
                result_type=f"llm_{getattr(parsed, 'action', step.action)}_result",
                error=message,
                error_type=type(exc).__name__,
                output_alias=step.output_alias,
                action=getattr(parsed, "action", step.action),
                args={},
                raw_output="",
                parsed_output=None,
            )
            return llm_result_error(
                getattr(parsed, "action", step.action),
                message,
                metadata={
                    "error_type": type(exc).__name__,
                    "tag": "transient" if type(exc).__name__ in {"LLMOutputParseError"} else "unknown",
                },
            )

    def _run_micro_tool(
        self,
        frame: TaskFrame,
        step: StepRuntime,
        action: str,
        output_alias: str,
        args: dict[str, Any],
        llm_call: dict[str, Any],
    ) -> LLMResult:
        try:
            system, prompt = render_llm_prompt(action, args)
        except (LLMToolInputError, LLMToolNotFoundError) as exc:
            message = str(exc)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            frame.state = "FAILED_EXECUTION"
            record_error(frame, "llm_micro_tool_failed", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias})
            add_audit_event(frame, "LLM_MICRO_TOOL_FAILED", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias})
            _finalize_llm_call(llm_call, ok=False, result_type=f"llm_{action}_result", error=message, error_type=type(exc).__name__, output_alias=output_alias, action=action, args=args, raw_output="", parsed_output=None)
            return llm_result_error(action, message, metadata={"error_type": type(exc).__name__, "micro_tool": True})
        add_audit_event(
            frame,
            "LLM_MICRO_TOOL_STARTED",
            "LLM micro-tool started.",
            {"step_id": step.step_id, "action": action, "output_alias": output_alias},
        )
        raw_text = self.adapter.generate(
            prompt,
            system=system,
            metadata={
                "action": action,
                "step_id": step.step_id,
                "output_alias": output_alias,
                "args": dict(args),
                "micro_tool": True,
                "manifest_id": getattr(frame, "manifest_id", ""),
                "frame_id": getattr(frame, "frame_id", ""),
            },
        )
        validated = validate_llm_output(action, raw_text)
        if not validated["ok"]:
            message = validated["error"] or "LLM micro-tool validation failed."
            validations = validate_micro_tool_output(action, {}, args)
            step.status = "FAILED"
            step.error = message
            step.last_error = message
            frame.state = "FAILED_EXECUTION"
            record_error(frame, "llm_micro_tool_failed", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias, "error_type": validated.get("error_type", "LLM_OUTPUT_SCHEMA_INVALID")})
            add_audit_event(frame, "LLM_MICRO_TOOL_FAILED", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias})
            _finalize_llm_call(llm_call, ok=False, result_type=f"llm_{action}_result", error=message, error_type=validated.get("error_type", "LLM_OUTPUT_SCHEMA_INVALID"), output_alias=output_alias, action=action, args=args, raw_output=raw_text, parsed_output=validated.get("data"))
            return llm_result_error(action, message, raw_text=raw_text, metadata={"error_type": validated.get("error_type", "LLM_OUTPUT_SCHEMA_INVALID"), "micro_tool": True})
        output = validated["data"]
        if action == "draft_customer_status_reply" and isinstance(output, dict):
            output = dict(output)
            output.setdefault("body", output.get("reply", ""))
        if action == "draft_supplier_reorder_message" and isinstance(output, dict):
            supplier = args.get("supplier", {}) if isinstance(args.get("supplier", {}), dict) else {}
            draft_po = args.get("draft_po", {}) if isinstance(args.get("draft_po", {}), dict) else {}
            po_id = str(draft_po.get("po_id", "")).strip()
            supplier_name = str(supplier.get("name", "")).strip()
            skus = [str(line.get("sku", "")).strip() for line in draft_po.get("lines", []) if isinstance(line, dict)]
            body = str(output.get("body", ""))
            if not output.get("subject"):
                message = "Supplier message subject is required."
                return self._micro_tool_failure(frame, step, action, output_alias, args, llm_call, message, raw_text, "LLM_OUTPUT_SCHEMA_INVALID", output)
            if not output.get("body"):
                message = "Supplier message body is required."
                return self._micro_tool_failure(frame, step, action, output_alias, args, llm_call, message, raw_text, "LLM_OUTPUT_SCHEMA_INVALID", output)
            if output.get("included_po_id") is not True or po_id and po_id not in body:
                message = "Supplier message must include the draft PO id."
                return self._micro_tool_failure(frame, step, action, output_alias, args, llm_call, message, raw_text, "LLM_OUTPUT_SCHEMA_INVALID", output)
            if supplier_name and supplier_name not in body:
                message = "Supplier message must include the supplier name."
                return self._micro_tool_failure(frame, step, action, output_alias, args, llm_call, message, raw_text, "LLM_OUTPUT_SCHEMA_INVALID", output)
            if output.get("included_sku_lines") is not True or any(sku and sku not in body for sku in skus):
                message = "Supplier message must include all SKU lines."
                return self._micro_tool_failure(frame, step, action, output_alias, args, llm_call, message, raw_text, "LLM_OUTPUT_SCHEMA_INVALID", output)
            if output.get("invented_terms") is True:
                message = "Supplier message must not invent terms."
                return self._micro_tool_failure(frame, step, action, output_alias, args, llm_call, message, raw_text, "LLM_OUTPUT_SCHEMA_INVALID", output)
        validations = validate_micro_tool_output(action, output, args)
        frame.validations.extend([dict(item) for item in validations if isinstance(item, dict)])
        llm_call["metadata"] = {"micro_tool": True}
        llm_call["prompt_ref"] = output_alias
        if validations and all(bool(item.get("ok")) for item in validations):
            set_output(frame, output_alias, output)
            step.status = "COMPLETED"
            step.result_ref = output_alias
            add_audit_event(frame, "LLM_MICRO_TOOL_COMPLETED", "LLM micro-tool completed.", {"step_id": step.step_id, "action": action, "output_alias": output_alias})
            _finalize_llm_call(llm_call, ok=True, result_type=f"llm_{action}_result", error="", error_type="", output_alias=output_alias, action=action, args=args, raw_output=raw_text, parsed_output=output)
            return llm_result_ok(action, output=output, raw_text=raw_text, parsed_json=output if isinstance(output, (dict, list)) else None, metadata={"output_alias": output_alias, "provider": self._provider_name(), "model": self._model_name(), "result_type": f"llm_{action}_result", "micro_tool": True})

        step.status = "FAILED"
        message = validations[0]["message"] if validations else "LLM micro-tool validation failed."
        step.error = message
        step.last_error = message
        frame.state = "FAILED_EXECUTION"
        record_error(frame, "llm_micro_tool_failed", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias, "validations": validations})
        add_audit_event(frame, "LLM_MICRO_TOOL_FAILED", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias})
        _finalize_llm_call(llm_call, ok=False, result_type=f"llm_{action}_result", error=message, error_type="LLMMicroToolValidationError", output_alias=output_alias, action=action, args=args, raw_output=raw_text, parsed_output=output)
        return llm_result_error(action, message, raw_text=raw_text, metadata={"error_type": "LLM_OUTPUT_SCHEMA_INVALID", "micro_tool": True})

    def _micro_tool_failure(
        self,
        frame: TaskFrame,
        step: StepRuntime,
        action: str,
        output_alias: str,
        args: dict[str, Any],
        llm_call: dict[str, Any],
        message: str,
        raw_text: str,
        error_type: str,
        output: Any,
    ) -> LLMResult:
        step.status = "FAILED"
        step.error = message
        step.last_error = message
        frame.state = "FAILED_EXECUTION"
        record_error(frame, "llm_micro_tool_failed", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias, "error_type": error_type})
        add_audit_event(frame, "LLM_MICRO_TOOL_FAILED", message, {"step_id": step.step_id, "action": action, "output_alias": output_alias})
        _finalize_llm_call(llm_call, ok=False, result_type=f"llm_{action}_result", error=message, error_type=error_type, output_alias=output_alias, action=action, args=args, raw_output=raw_text, parsed_output=output)
        return llm_result_error(action, message, raw_text=raw_text, metadata={"error_type": error_type, "micro_tool": True})

    def _build_prompt(self, action: str, args: dict[str, Any]) -> str:
        if action == "summarize":
            return build_summarize_prompt(args["text"], args.get("max_words", 80))
        if action == "extract":
            fields = _split_csv(args.get("fields", "")) if args.get("fields") else None
            return build_extract_prompt(args["text"], args["schema"], fields=fields)
        if action == "classify":
            labels = _split_csv(args["labels"])
            return build_classify_prompt(args["text"], labels)
        if action == "draft":
            return build_draft_prompt(args["instruction"], context=args.get("context", ""), tone=args.get("tone", "plain"))
        if action == "compare":
            return build_compare_prompt(args["left"], args["right"], criteria=args.get("criteria", ""))
        raise LLMActionNotAllowedError(f"LLM action not allowed: {action}")

    def _normalize_result(
        self,
        action: str,
        output_alias: str,
        raw_text: str,
        args: dict[str, Any],
        llm_call: dict[str, Any],
    ) -> LLMResult:
        if action in {"summarize", "draft"}:
            output = raw_text.strip()
            return llm_result_ok(
                action,
                output=output,
                raw_text=raw_text,
                metadata={
                    "output_alias": output_alias,
                    "provider": self._provider_name(),
                    "model": self._model_name(),
                    "result_type": f"llm_{action}_result",
                },
            )

        parsed_json = extract_json_from_text(raw_text)
        if action == "extract":
            if not isinstance(parsed_json, dict):
                raise LLMOutputParseError("LLM extract output must be a JSON object.")
            return llm_result_ok(
                action,
                output=parsed_json,
                raw_text=raw_text,
                parsed_json=parsed_json,
                metadata={
                    "output_alias": output_alias,
                    "provider": self._provider_name(),
                    "model": self._model_name(),
                    "result_type": f"llm_{action}_result",
                },
            )

        if action == "classify":
            if not isinstance(parsed_json, dict):
                raise LLMOutputParseError("LLM classify output must be a JSON object.")
            labels = _split_csv(args["labels"])
            label = parsed_json.get("label")
            if label not in labels:
                raise LLMCommandError(f"Classified label is not allowed: {label}")
            if "confidence" not in parsed_json:
                raise LLMCommandError("LLM classify output must include confidence.")
            return llm_result_ok(
                action,
                output=parsed_json,
                raw_text=raw_text,
                parsed_json=parsed_json,
                metadata={
                    "output_alias": output_alias,
                    "provider": self._provider_name(),
                    "model": self._model_name(),
                    "result_type": f"llm_{action}_result",
                },
            )

        if action == "compare":
            if not isinstance(parsed_json, dict):
                raise LLMOutputParseError("LLM compare output must be a JSON object.")
            return llm_result_ok(
                action,
                output=parsed_json,
                raw_text=raw_text,
                parsed_json=parsed_json,
                metadata={
                    "output_alias": output_alias,
                    "provider": self._provider_name(),
                    "model": self._model_name(),
                    "result_type": f"llm_{action}_result",
                },
            )

        raise LLMActionNotAllowedError(f"LLM action not allowed: {action}")

    def _provider_name(self) -> str:
        return getattr(self.adapter, "provider", self.adapter.__class__.__name__.lower())

    def _model_name(self) -> str:
        return getattr(self.adapter, "model", "")


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _make_llm_call_record(step: StepRuntime, provider: str, model: str) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "action": step.action,
        "output_alias": step.output_alias,
        "args": {},
        "ok": None,
        "result_type": "",
        "provider": provider,
        "model": model,
        "error": "",
        "error_type": "",
        "raw_output": "",
        "parsed_output": None,
        "timestamp": utc_now(),
    }


def _finalize_llm_call(
    llm_call: dict[str, Any],
    *,
    ok: bool,
    result_type: str,
    error: str,
    error_type: str = "",
    output_alias: str | None,
    action: str,
    args: dict[str, Any],
    raw_output: str = "",
    parsed_output: Any = None,
) -> None:
    llm_call.update(
        {
            "ok": ok,
            "result_type": result_type,
            "error": error,
            "error_type": error_type,
            "output_alias": output_alias,
            "action": action,
            "args": dict(args),
            "raw_output": raw_output,
            "parsed_output": parsed_output,
            "timestamp": utc_now(),
        }
    )
