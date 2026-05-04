from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import cronexpr

from ..core.types import LLMJudgeResult, Sample
from .automation_state_expr import StateExprEquivalence


TIME_CRON_ANCHOR = datetime(2000, 1, 1, tzinfo=timezone.utc)
TIME_CRON_EQUIVALENCE_SAMPLES = 64


@dataclass
class ConditionComparisonResult:
    passed: bool
    reason: str
    error: Optional[str] = None
    raw: Optional[Any] = None

    def to_judge_result(self) -> LLMJudgeResult:
        return LLMJudgeResult(
            passed=self.passed,
            reason=self.reason,
            error=self.error,
            raw=self.raw,
        )


def compare_time_cron(
    ground_truth: Optional[str],
    prediction: Optional[str],
    *,
    anchor: datetime = TIME_CRON_ANCHOR,
    sample_count: int = TIME_CRON_EQUIVALENCE_SAMPLES,
) -> ConditionComparisonResult:
    if ground_truth is None and prediction is None:
        return ConditionComparisonResult(True, "both time_cron are null")
    if ground_truth is None or prediction is None:
        return ConditionComparisonResult(False, "time_cron null mismatch")
    try:
        gt_fires = _fire_sequence(ground_truth, anchor=anchor, sample_count=sample_count)
        pred_fires = _fire_sequence(prediction, anchor=anchor, sample_count=sample_count)
    except Exception as exc:
        return ConditionComparisonResult(False, f"time_cron comparison failed: {exc}", error=str(exc))
    if gt_fires != pred_fires:
        return ConditionComparisonResult(
            False,
            "time_cron trigger sequence mismatch",
            raw={"ground_truth": gt_fires, "prediction": pred_fires},
        )
    return ConditionComparisonResult(True, "time_cron trigger sequences match", raw=gt_fires)


def compare_state_expr(
    engine: Dict[str, Any],
    ground_truth: Optional[str],
    prediction: Optional[str],
) -> ConditionComparisonResult:
    result = StateExprEquivalence(engine).compare(ground_truth, prediction)
    return ConditionComparisonResult(
        passed=result.passed,
        reason=result.reason,
        error=result.error,
    )


class AutomationConditionEvaluator:
    def evaluate(self, sample: Sample) -> LLMJudgeResult:
        ground_truth_conditions = sample.ground_truth.get("conditions") or []
        predicted_conditions = sample.predictions.conditions if sample.predictions else []
        try:
            gt_items = self._validate_condition_list(ground_truth_conditions, scope="ground_truth")
            pred_items = self._validate_condition_list(predicted_conditions, scope="prediction")
        except Exception as exc:
            return LLMJudgeResult(
                passed=False,
                reason=f"invalid conditions payload: {exc}",
                error=str(exc),
            )

        if len(gt_items) != len(pred_items):
            return LLMJudgeResult(
                passed=False,
                reason="condition count mismatch",
                raw={"ground_truth_count": len(gt_items), "prediction_count": len(pred_items)},
            )

        for gt_item, pred_item in zip(gt_items, pred_items):
            time_result = compare_time_cron(gt_item["time_cron"], pred_item["time_cron"])
            if not time_result.passed:
                return time_result.to_judge_result()
            state_result = compare_state_expr(sample.engine, gt_item["state_expr"], pred_item["state_expr"])
            if not state_result.passed:
                return state_result.to_judge_result()

        return LLMJudgeResult(passed=True, reason="all automation conditions match")

    @staticmethod
    def _validate_condition_list(raw_conditions: Any, *, scope: str) -> List[Dict[str, Optional[str]]]:
        if raw_conditions is None:
            return []
        if not isinstance(raw_conditions, list):
            raise ValueError(f"{scope}.conditions must be a list")
        normalized: List[Dict[str, Optional[str]]] = []
        for index, item in enumerate(raw_conditions):
            if not isinstance(item, dict):
                raise ValueError(f"{scope}.conditions[{index}] must be an object")
            if set(item.keys()) != {"time_cron", "state_expr"}:
                raise ValueError(f"{scope}.conditions[{index}] must contain exactly time_cron and state_expr")
            time_cron = item.get("time_cron")
            state_expr = item.get("state_expr")
            if time_cron is not None and not isinstance(time_cron, str):
                raise ValueError(f"{scope}.conditions[{index}].time_cron must be string or null")
            if state_expr is not None and not isinstance(state_expr, str):
                raise ValueError(f"{scope}.conditions[{index}].state_expr must be string or null")
            if time_cron is None and state_expr is None:
                raise ValueError(f"{scope}.conditions[{index}] cannot be all null")
            normalized.append({"time_cron": time_cron, "state_expr": state_expr})
        return normalized


def _fire_sequence(cron: str, *, anchor: datetime, sample_count: int) -> List[str]:
    current = anchor
    fires: List[str] = []
    for _ in range(sample_count):
        next_fire = cronexpr.next_fire(cron, current)
        if not isinstance(next_fire, datetime):
            raise ValueError(f"invalid next_fire result for cron: {cron}")
        if next_fire <= current:
            break
        fires.append(next_fire.astimezone(timezone.utc).isoformat())
        current = next_fire + timedelta(seconds=1)
    return fires
