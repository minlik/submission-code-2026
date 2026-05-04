from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base_runner import BaseInferenceRunner
from ..tools.codec import decode_tool_call, encode_tool_result_message
from ..tools.registry import ToolRegistry
from ..tools.specs import ToolContext, ToolProfile, ToolResult
from utils.llm_util import merge_token_usage


class ToolCallingRunner(BaseInferenceRunner):
    def __init__(
        self,
        prompt_builder: Any,
        registry: ToolRegistry,
        profile: ToolProfile,
        max_tool_calls: int = 10,
        tool_choice: Any = "auto",
        parallel_tool_calls: bool = True,
        action_simulator: Any = None,
    ) -> None:
        super().__init__(
            prompt_builder=prompt_builder,
            action_simulator=action_simulator,
            max_tool_calls=max_tool_calls,
        )
        self.registry = registry
        self.profile = profile
        self.tool_choice = tool_choice
        self.parallel_tool_calls = parallel_tool_calls

    def _run_tool_loop_with_usage(
        self,
        messages: List[Dict[str, Any]],
        llm_runner: Any,
        env: Any,
        engine_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str], List[str], List[Dict[str, Any]], Dict[str, int]]:
        working_messages: List[Dict[str, Any]] = [dict(message) for message in messages]
        errors: List[str] = []
        action_errors: List[str] = []
        token_usage: Dict[str, int] = {}
        tools = self.registry.schemas(self.profile)
        resolved_engine = engine_data or {}

        for step in range(self.max_tool_calls + 1):
            response, error = self._call_llm(
                working_messages,
                llm_runner,
                tools=tools,
                tool_choice=self.tool_choice,
                parallel_tool_calls=self.parallel_tool_calls,
            )
            token_usage = merge_token_usage(token_usage, response.token_usage)
            if error:
                errors.append(f"execution llm error: {error}")
                return "", errors, action_errors, working_messages, token_usage

            tool_calls = self._normalize_tool_calls(response.tool_calls)
            assistant_message: Dict[str, Any] = dict(response.raw_message or {})
            assistant_message.setdefault("role", "assistant")
            if "content" not in assistant_message:
                assistant_message["content"] = self._normalize_text(response.content)
            if tool_calls and "tool_calls" not in assistant_message:
                assistant_message["tool_calls"] = tool_calls
            working_messages.append(assistant_message)

            if not tool_calls:
                text = self._normalize_text(response.content)
                if not text:
                    errors.append("empty final model content without tool_calls")
                return text, errors, action_errors, working_messages, token_usage

            if step >= self.max_tool_calls:
                errors.append(f"too many tool calls, max: {self.max_tool_calls}")
                return "", errors, action_errors, working_messages, token_usage

            for index, raw_tool_call in enumerate(tool_calls):
                result = self._execute_tool_call(
                    raw_tool_call=raw_tool_call,
                    env=env,
                    engine_data=resolved_engine,
                    step=step,
                    tool_index=index,
                )
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": result.call_id,
                        "content": encode_tool_result_message(result),
                    }
                )
                if not result.ok:
                    err = (
                        f"tool failed name={result.tool_name or 'unknown'} "
                        f"call_id={result.call_id}: {result.error_message or result.error_code or 'unknown error'}"
                    )
                    errors.append(err)
                    action_errors.append(err)

        errors.append(f"too many tool calls, max: {self.max_tool_calls}")
        return "", errors, action_errors, working_messages, token_usage

    def _execute_tool_call(
        self,
        raw_tool_call: Dict[str, Any],
        env: Any,
        engine_data: Dict[str, Any],
        step: int,
        tool_index: int,
    ) -> ToolResult:
        fallback_call_id = str(raw_tool_call.get("id") or f"call_{step}_{tool_index}")
        fallback_tool_name = str((raw_tool_call.get("function") or {}).get("name") or "unknown")
        try:
            call = decode_tool_call(raw_tool_call)
        except ValueError as exc:
            return ToolResult(
                call_id=fallback_call_id,
                tool_name=fallback_tool_name,
                ok=False,
                result={"raw_tool_call": dict(raw_tool_call)},
                error_code="INVALID_TOOL_CALL",
                error_message=str(exc),
            )
        context = ToolContext(
            env=env,
            engine_data=engine_data,
            profile_name=self.profile.name,
            step_index=step,
            sample_meta={},
        )
        return self.registry.execute(self.profile, call, context)

    @staticmethod
    def _normalize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
        if not isinstance(tool_calls, list):
            return []
        return [dict(call) for call in tool_calls if isinstance(call, dict)]

    def _reset_created_automations(self) -> None:
        self.registry.reset_runtime_state(self.profile)

    def _drain_created_automations(self) -> List[Dict[str, Any]]:
        return self.registry.drain_created_automations(self.profile)
