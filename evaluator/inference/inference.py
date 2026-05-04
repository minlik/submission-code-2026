from typing import Any, Dict, List, Optional, Tuple

from .action_simulator import ActionSimulator
from .assistant_parser import AssistantResponseParser
from .assistant_prompt import AssistantPromptBuilder
from ..core.types import Prediction, Sample
from ..llm.llm import LLMResponse, run_async
from utils.llm_util import merge_token_usage


class AssistantInferenceRunner:
    def __init__(
        self,
        prompt_builder: AssistantPromptBuilder,
        parser: Optional[AssistantResponseParser] = None,
        action_simulator: Optional[ActionSimulator] = None,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.parser = parser or AssistantResponseParser()
        self.action_simulator = action_simulator or ActionSimulator()

    def infer_clarifications(
        self, sample: Sample, llm_runner: Any
    ) -> Tuple[List[str], List[Optional[bool]], List[str], List[Dict[str, Any]], Dict[str, int]]:
        clarifications: List[str] = []
        clarification_mode_ok: List[Optional[bool]] = []
        errors: List[str] = []
        message_stages: List[Dict[str, Any]] = []
        token_usage: Dict[str, int] = {}
        indices = sample._clarification_indices()
        for order, idx in enumerate(indices):
            history_slice = sample.history[:idx]
            messages = self.prompt_builder.build(
                engine_data=sample.engine,
                entrance=sample.entrance,
                initial_query=sample.initial_query,
                history=history_slice,
                initial_chat_history=sample.initial_chat_history,
                memory_list=sample.memory_list,
            )
            response, error = self._call_llm(messages, llm_runner)
            token_usage = merge_token_usage(token_usage, response.token_usage)
            if error:
                errors.append(f"clarification[{order}] llm error: {error}")
                clarifications.append("")
                message_stages.append(self._stage_record("clarification", order, messages, ""))
                clarification_mode_ok.append(None)
                continue
            try:
                payload = self.parser.parse(response.content)
                mode = self.parser.normalize_mode(payload)
                if mode != "clarification":
                    errors.append(f"clarification[{order}] unexpected mode: {mode}")
                    clarification_mode_ok.append(False)
                else:
                    clarification_mode_ok.append(True)
                text = str(payload.get("response") or "")
                clarifications.append(text)
                message_stages.append(self._stage_record("clarification", order, messages, text))
            except Exception as exc:
                errors.append(f"clarification[{order}] parse error: {exc}")
                clarifications.append("")
                message_stages.append(self._stage_record("clarification", order, messages, ""))
                clarification_mode_ok.append(None)
        return clarifications, clarification_mode_ok, errors, message_stages, token_usage

    def infer_execution(
        self, sample: Sample, llm_runner: Any
    ) -> Tuple[Prediction, Optional[Dict[str, Any]], List[str], List[str], List[Dict[str, Any]], Dict[str, int]]:
        errors: List[str] = []
        token_usage: Dict[str, int] = {}
        history = [turn for turn in sample.history if not self._is_execution(turn)]
        messages = self.prompt_builder.build(
            engine_data=sample.engine,
            entrance=sample.entrance,
            initial_query=sample.initial_query,
            history=history,
            initial_chat_history=sample.initial_chat_history,
            memory_list=sample.memory_list,
        )
        response, error = self._call_llm(messages, llm_runner)
        token_usage = merge_token_usage(token_usage, response.token_usage)
        if error:
            errors.append(f"execution llm error: {error}")
            return Prediction(), None, errors, [], [self._stage_record("final", 0, messages, "")], token_usage
        try:
            payload = self.parser.parse(response.content)
        except Exception as exc:
            errors.append(f"execution parse error: {exc}")
            return Prediction(), None, errors, [], [self._stage_record("final", 0, messages, "")], token_usage
        mode = self.parser.normalize_mode(payload)
        message_stages: List[Dict[str, Any]] = [
            self._stage_record("final", 0, messages, str(payload.get("response") or ""))
        ]
        if mode != "execution":
            errors.append(f"execution unexpected mode: {mode}")
            payload = {"mode": "execution", "response": "", "actions": []}
        prediction, action_errors = self._build_prediction_from_payload(sample, payload, errors)
        return prediction, payload, errors, action_errors, message_stages, token_usage

    def infer_sample(
        self, sample: Sample, llm_runner: Any
    ) -> Tuple[Prediction, List[Dict[str, Any]], List[str], List[str], List[Dict[str, Any]]]:
        errors: List[str] = []
        clarifications: List[str] = []
        message_stages: List[Dict[str, Any]] = []
        clarification_mode_ok: List[Optional[bool]] = []
        total_usage: Dict[str, int] = {}
        if sample.has_clarification():
            clarifications, clarification_mode_ok, errs, clarification_messages, clarification_usage = self.infer_clarifications(
                sample, llm_runner
            )
            errors.extend(errs)
            message_stages.extend(clarification_messages)
            total_usage = merge_token_usage(total_usage, clarification_usage)
        prediction, exec_payload, exec_errors, action_errors, exec_messages, execution_usage = self.infer_execution(
            sample, llm_runner
        )
        errors.extend(exec_errors)
        message_stages.extend(exec_messages)
        total_usage = merge_token_usage(total_usage, execution_usage)
        if clarifications:
            prediction.clarifications = clarifications
            prediction.clarification_mode_ok = clarification_mode_ok
        if total_usage:
            prediction.token_usage = total_usage
        predicted_history = self._build_predicted_history(sample, exec_payload)
        return prediction, predicted_history, errors, action_errors, message_stages

    def _build_prediction_from_payload(
        self, sample: Sample, payload: Dict[str, Any], errors: List[str]
    ) -> Tuple[Prediction, List[str]]:
        mode = self.parser.normalize_mode(payload)
        if mode == "clarification":
            return Prediction(clarifications=[str(payload.get("response") or "")]), []
        if mode != "execution":
            errors.append(f"unsupported mode: {mode}")
            return Prediction(), []
        actions = list(payload.get("actions") or [])
        automations = list(payload.get("automations") or [])
        conditions = [auto.get("conditions") for auto in automations if auto.get("conditions")]
        for auto in automations:
            for action in auto.get("actions") or []:
                actions.append(action)
        labels, action_errors = self.action_simulator.labels_from_actions(sample.engine, actions)
        if action_errors:
            errors.extend(action_errors)
        return Prediction(
            labels=labels,
            conditions=conditions,
            response=str(payload.get("response") or ""),
        ), action_errors

    def _build_predicted_history(
        self,
        sample: Sample,
        exec_payload: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        predicted: List[Dict[str, Any]] = []
        for turn in sample.history:
            role = turn.get("role")
            content = turn.get("content")
            if role == "assistant" and isinstance(content, dict):
                mode = content.get("mode")
                if mode == "execution":
                    predicted.append(
                        {
                            "role": "assistant",
                            "content": exec_payload or {"mode": "execution", "response": ""},
                        }
                    )
                    continue
            predicted.append(turn)
        if not predicted and exec_payload:
            predicted.append({"role": "assistant", "content": exec_payload})
        return predicted

    @staticmethod
    def _is_execution(turn: Dict[str, Any]) -> bool:
        if turn.get("role") != "assistant":
            return False
        content = turn.get("content")
        return isinstance(content, dict) and content.get("mode") == "execution"

    def _stage_record(
        self,
        stage: str,
        order: int,
        messages: List[Dict[str, Any]],
        assistant_content: str,
    ) -> Dict[str, Any]:
        recorded = self._recordable_messages(messages)
        if assistant_content:
            recorded.append({"role": "assistant", "content": assistant_content})
        return {"stage": stage, "order": order, "messages": recorded}

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
    def _call_llm(messages: Any, llm_runner: Any) -> Tuple[LLMResponse, Optional[str]]:
        try:
            response = run_async(llm_runner.generate_chat(messages, is_json_output=True))
            if isinstance(response, LLMResponse):
                return response, None
            return LLMResponse(content=response), None
        except Exception as exc:
            return LLMResponse(content=None, token_usage={}), str(exc)
