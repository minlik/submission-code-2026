from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .action_simulator import ActionSimulator
from ..core.types import Prediction, Sample
from ..llm.llm import LLMResponse, run_async
from utils.llm_util import merge_token_usage


class BaseInferenceRunner:
    def __init__(
        self,
        prompt_builder: Any,
        action_simulator: Optional[ActionSimulator] = None,
        max_tool_calls: int = 10,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.action_simulator = action_simulator or ActionSimulator()
        self.max_tool_calls = max_tool_calls

    def infer_clarifications_text(
        self, sample: Sample, llm_runner: Any
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]], Dict[str, int]]:
        clarifications: List[str] = []
        errors: List[str] = []
        message_stages: List[Dict[str, Any]] = []
        token_usage: Dict[str, int] = {}
        indices = sample._clarification_indices()
        for order, idx in enumerate(indices):
            history_slice = sample.history[:idx]
            messages = self.prompt_builder.build_messages(
                engine_data=sample.engine,
                entrance=sample.entrance,
                initial_query=sample.initial_query,
                history=history_slice,
                initial_chat_history=sample.initial_chat_history,
                memory_list=sample.memory_list,
            )
            env = self.action_simulator.adapter.build_env(sample.engine)
            response_text, loop_errors, _, transcript, loop_usage = self._run_tool_loop_with_usage(
                messages, llm_runner, env, sample.engine
            )
            if loop_errors:
                errors.extend([f"clarification[{order}] {msg}" for msg in loop_errors])
            clarifications.append(response_text)
            message_stages.append(self._stage_record("clarification", order, transcript))
            token_usage = merge_token_usage(token_usage, loop_usage)
        return clarifications, errors, message_stages, token_usage

    def infer_final_with_tools(
        self, sample: Sample, llm_runner: Any
    ) -> Tuple[Prediction, str, List[str], List[str], List[Dict[str, Any]], Dict[str, int]]:
        errors: List[str] = []
        action_errors: List[str] = []
        self._reset_created_automations()

        history = [turn for turn in sample.history if not self._is_execution(turn)]
        messages = self.prompt_builder.build_messages(
            engine_data=sample.engine,
            entrance=sample.entrance,
            initial_query=sample.initial_query,
            history=history,
            initial_chat_history=sample.initial_chat_history,
            memory_list=sample.memory_list,
        )
        env = self.action_simulator.adapter.build_env(sample.engine)
        before = self.action_simulator._snapshot(env)
        final_response, loop_errors, loop_action_errors, transcript, token_usage = self._run_tool_loop_with_usage(
            messages, llm_runner, env, sample.engine
        )
        errors.extend(loop_errors)
        action_errors.extend(loop_action_errors)
        created_automations = self._drain_created_automations()
        if created_automations:
            labels, automation_errors = self._labels_from_automations(sample.engine, created_automations)
            if automation_errors:
                errors.extend(automation_errors)
                action_errors.extend(automation_errors)
            conditions = [dict(auto.get("conditions") or {}) for auto in created_automations]
            prediction = Prediction(labels=labels, conditions=conditions, response=final_response)
        else:
            after = self.action_simulator._snapshot(env)
            labels = self._labels_from_snapshots(before, after)
            prediction = Prediction(labels=labels, response=final_response)
        message_stages = [self._stage_record("final", 0, transcript)]
        return (
            prediction,
            final_response,
            errors,
            action_errors,
            message_stages,
            token_usage,
        )

    def infer_sample(
        self, sample: Sample, llm_runner: Any
    ) -> Tuple[Prediction, List[Dict[str, Any]], List[str], List[str], List[Dict[str, Any]]]:
        errors: List[str] = []
        clarifications: List[str] = []
        message_stages: List[Dict[str, Any]] = []
        total_usage: Dict[str, int] = {}
        if sample.has_clarification():
            clarifications, clarify_errors, clarification_messages, clarification_usage = self.infer_clarifications_text(
                sample, llm_runner
            )
            errors.extend(clarify_errors)
            message_stages.extend(clarification_messages)
            total_usage = merge_token_usage(total_usage, clarification_usage)
        prediction, final_response, exec_errors, action_errors, exec_messages, execution_usage = self.infer_final_with_tools(
            sample, llm_runner
        )
        errors.extend(exec_errors)
        message_stages.extend(exec_messages)
        total_usage = merge_token_usage(total_usage, execution_usage)
        if clarifications:
            prediction.clarifications = clarifications
        if total_usage:
            prediction.token_usage = total_usage
        predicted_history = self._build_predicted_history(sample, clarifications, final_response)
        return prediction, predicted_history, errors, action_errors, message_stages

    def _run_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        llm_runner: Any,
        env: Any,
        engine_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str], List[str], List[Dict[str, Any]]]:
        response, errors, action_errors, transcript, _ = self._run_tool_loop_with_usage(
            messages, llm_runner, env, engine_data
        )
        return response, errors, action_errors, transcript

    def _run_tool_loop_with_usage(
        self,
        messages: List[Dict[str, Any]],
        llm_runner: Any,
        env: Any,
        engine_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str], List[str], List[Dict[str, Any]], Dict[str, int]]:
        raise NotImplementedError

    def _labels_from_automations(
        self,
        engine_data: Dict[str, Any],
        automations: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        from mha.env import PyExec

        env = self.action_simulator.adapter.build_env(engine_data)
        before = self.action_simulator._snapshot(env)
        errors: List[str] = []
        for automation in automations:
            code = automation.get("code")
            actions = automation.get("actions")
            if isinstance(code, str) and code.strip():
                obs, *_ = env.step(PyExec(code))
                error = getattr(obs, "error", None)
                if error is not None:
                    errors.append(f"automation code failed: {error}")
            elif isinstance(actions, list) and actions:
                for action in actions:
                    try:
                        normalized = self.action_simulator.normalize_action(engine_data, action)
                        self.action_simulator._apply_action(env, normalized)
                    except Exception as exc:
                        did = action.get("did") if isinstance(action, dict) else None
                        locator = action.get("locator") if isinstance(action, dict) else None
                        errors.append(f"automation action failed did={did} locator={locator}: {exc}")
            else:
                errors.append("automation missing code or actions")
        after = self.action_simulator._snapshot(env)
        return self._labels_from_snapshots(before, after), errors

    def _reset_created_automations(self) -> None:
        return None

    def _drain_created_automations(self) -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def _labels_from_snapshots(
        before: Dict[Tuple[str, str], Any],
        after: Dict[Tuple[str, str], Any],
    ) -> List[Dict[str, Any]]:
        labels: List[Dict[str, Any]] = []
        for key, prev_value in before.items():
            if key not in after:
                continue
            cur_value = after[key]
            if cur_value != prev_value:
                did, attribute = key
                labels.append({"did": did, "attribute": attribute, "value": cur_value})
        return labels

    @staticmethod
    def _normalize_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        return str(content).strip()

    def _stage_record(
        self,
        stage: str,
        order: int,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {"stage": stage, "order": order, "messages": self._recordable_messages(messages)}

    @staticmethod
    def _recordable_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        recorded: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role not in {"system", "user", "assistant", "tool"}:
                continue
            item: Dict[str, Any] = {"role": role, "content": message.get("content", "")}
            if "tool_calls" in message:
                item["tool_calls"] = message.get("tool_calls")
            if "tool_call_id" in message:
                item["tool_call_id"] = message.get("tool_call_id")
            recorded.append(item)
        return recorded

    @staticmethod
    def _call_llm(
        messages: Any,
        llm_runner: Any,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Any = None,
        parallel_tool_calls: Optional[bool] = None,
    ) -> Tuple[LLMResponse, Optional[str]]:
        try:
            response = run_async(
                llm_runner.generate_chat(
                    messages,
                    is_json_output=False,
                    tools=tools,
                    tool_choice=tool_choice,
                    parallel_tool_calls=parallel_tool_calls,
                )
            )
            return response, None
        except Exception as exc:
            return LLMResponse(content=""), str(exc)

    @staticmethod
    def _is_execution(turn: Dict[str, Any]) -> bool:
        if turn.get("role") != "assistant":
            return False
        content = turn.get("content")
        return isinstance(content, dict) and content.get("mode") == "execution"

    @staticmethod
    def _has_automation(sample: Sample) -> bool:
        if sample.ground_truth.get("conditions"):
            return True
        execution_turns = [
            turn
            for turn in sample.history
            if turn.get("role") == "assistant" and isinstance(turn.get("content"), dict)
        ]
        for turn in execution_turns:
            content = turn.get("content") or {}
            if content.get("automations"):
                return True
        return False

    def _build_predicted_history(
        self,
        sample: Sample,
        clarifications: List[str],
        final_response: str,
    ) -> List[Dict[str, Any]]:
        predicted: List[Dict[str, Any]] = []
        clarification_order = 0
        for turn in sample.history:
            role = turn.get("role")
            content = turn.get("content")
            if role == "assistant" and isinstance(content, dict):
                mode = content.get("mode")
                if mode == "clarification":
                    response = clarifications[clarification_order] if clarification_order < len(clarifications) else ""
                    predicted.append(
                        {
                            "role": "assistant",
                            "content": {"mode": "clarification", "response": response},
                        }
                    )
                    clarification_order += 1
                    continue
                if mode == "execution":
                    predicted.append(
                        {
                            "role": "assistant",
                            "content": {"mode": "execution", "response": final_response},
                        }
                    )
                    continue
            predicted.append(turn)
        if not predicted and final_response:
            predicted.append(
                {
                    "role": "assistant",
                    "content": {"mode": "execution", "response": final_response},
                }
            )
        return predicted
