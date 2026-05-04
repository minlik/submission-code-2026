from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Prediction:
    labels: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    clarifications: List[str] = field(default_factory=list)
    clarification_mode_ok: List[Optional[bool]] = field(default_factory=list)
    response: Optional[str] = None
    engine: Optional[Dict[str, Any]] = None
    token_usage: Optional[Dict[str, int]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prediction":
        if data is None:
            return cls()
        engine_data = data.get("engine")
        engine: Optional[Dict[str, Any]] = None
        if isinstance(engine_data, dict):
            engine = dict(engine_data)
        return cls(
            labels=list(data.get("labels") or []),
            conditions=list(data.get("conditions") or []),
            clarifications=list(data.get("clarifications") or []),
            clarification_mode_ok=list(data.get("clarification_mode_ok") or []),
            response=data.get("response"),
            token_usage=data.get("token_usage") or {},
            engine=engine,
        )

    def is_empty(self) -> bool:
        return not (
            self.engine
            or self.labels
            or self.conditions
            or self.clarifications
            or self.clarification_mode_ok
            or self.response
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "labels": list(self.labels),
            "conditions": list(self.conditions),
            "clarifications": list(self.clarifications),
        }
        if self.clarification_mode_ok:
            payload["clarification_mode_ok"] = list(self.clarification_mode_ok)
        if self.response is not None:
            payload["response"] = self.response
        if self.engine is not None:
            payload["engine"] = self.engine
        if self.token_usage:
            payload["token_usage"] = self.token_usage
        return payload


@dataclass
class Sample:
    uuid: Optional[str]
    query_idx: Optional[int]
    initial_query: str
    intended_query: Optional[str]
    initial_chat_history: List[Dict[str, Any]]
    history: List[Dict[str, Any]]
    memory_list: Optional[List[str]]
    entrance: Optional[str]
    engine: Dict[str, Any]
    ground_truth: Dict[str, Any]
    critic: Optional[str]
    predictions: Optional[Prediction] = None
    source_path: Optional[str] = None
    category: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sample":
        predictions_data = data.get("predictions")
        return cls(
            uuid=data.get("uuid"),
            query_idx=data.get("query_idx"),
            initial_query=data.get("initial_query") or "",
            intended_query=data.get("intended_query"),
            initial_chat_history=list(data.get("initial_chat_history") or []),
            history=list(data.get("history") or []),
            memory_list=list(data.get("memory_list") or []) if data.get("memory_list") is not None else None,
            entrance=data.get("entrance"),
            engine=dict(data.get("engine") or {}),
            ground_truth=dict(data.get("ground_truth") or {}),
            critic=data.get("critic"),
            predictions=Prediction.from_dict(predictions_data)
            if predictions_data is not None
            else None,
        )

    def has_clarification(self) -> bool:
        return bool(self._clarification_indices())

    def _clarification_indices(self) -> List[int]:
        indices: List[int] = []
        for idx, turn in enumerate(self.history):
            if turn.get("role") != "assistant":
                continue
            content = turn.get("content")
            if isinstance(content, dict) and content.get("mode") == "clarification":
                indices.append(idx)
        return indices

    def clarification_context(self, clarification_order: int) -> List[Dict[str, Any]]:
        indices = self._clarification_indices()
        if clarification_order < 0 or clarification_order >= len(indices):
            return []
        cutoff = indices[clarification_order]
        return self.history[:cutoff]


@dataclass
class PredictionRecord:
    uuid: Optional[str]
    query_idx: Optional[int]
    predictions: Prediction
    initial_query: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    action_errors: Optional[List[str]] = None
    inference_errors: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionRecord":
        return cls(
            uuid=data.get("uuid"),
            query_idx=data.get("query_idx"),
            predictions=Prediction.from_dict(data.get("predictions") or {}),
            initial_query=data.get("initial_query"),
            history=data.get("history"),
            messages=data.get("messages"),
            action_errors=data.get("action_errors"),
            inference_errors=data.get("inference_errors"),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "uuid": self.uuid,
            "query_idx": self.query_idx,
            "predictions": self.predictions.to_dict(),
        }
        if self.initial_query is not None:
            payload["initial_query"] = self.initial_query
        if self.history is not None:
            payload["history"] = self.history
        if self.messages is not None:
            payload["messages"] = self.messages
        if self.action_errors is not None:
            payload["action_errors"] = self.action_errors
        if self.inference_errors is not None:
            payload["inference_errors"] = self.inference_errors
        return payload


@dataclass
class LLMJudgeResult:
    passed: Optional[bool]
    reason: Optional[str]
    error: Optional[str] = None
    raw: Optional[Any] = None


@dataclass
class EvaluationResult:
    uuid: Optional[str]
    query_idx: Optional[int]
    critic_pass: Optional[bool]
    ground_truth_critic_pass: Optional[bool]
    query_response_pass: Optional[bool]
    conditions_pass: Optional[bool]
    clarification_passes: List[Optional[bool]]
    query_response_required: bool = False
    conditions_required: bool = False
    clarifications_required: bool = False
    overall_pass: Optional[bool] = None
    category: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    token_usage: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "query_idx": self.query_idx,
            "critic_pass": self.critic_pass,
            "ground_truth_critic_pass": self.ground_truth_critic_pass,
            "query_response_pass": self.query_response_pass,
            "query_response_required": self.query_response_required,
            "conditions_pass": self.conditions_pass,
            "clarification_passes": self.clarification_passes,
            "conditions_required": self.conditions_required,
            "clarifications_required": self.clarifications_required,
            "overall_pass": self.overall_pass,
            "category": self.category,
            "errors": list(self.errors),
            "token_usage": self.token_usage or {}
        }
