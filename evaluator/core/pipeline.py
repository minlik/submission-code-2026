from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Tuple

from ..judging.automation_conditions import AutomationConditionEvaluator
from ..judging.critic import CriticEvaluator
from ..judging.judges import ClarificationJudge, QueryResponseJudge
from ..llm.llm import run_async
from .types import EvaluationResult, LLMJudgeResult, Sample


@dataclass
class PendingLLMJudges:
    query_response: bool = False
    clarification_orders: List[int] = field(default_factory=list)

    def has_work(self) -> bool:
        return self.query_response or bool(self.clarification_orders)


class EvaluationPipeline:
    def __init__(
        self,
        critic_evaluator: Optional[CriticEvaluator] = None,
        automation_condition_evaluator: Optional[AutomationConditionEvaluator] = None,
        clarification_judge: Optional[ClarificationJudge] = None,
        query_response_judge: Optional[QueryResponseJudge] = None,
        evaluate_predictions: bool = True,
        strict_clarification_judge: bool = False,
    ) -> None:
        self.critic_evaluator = critic_evaluator or CriticEvaluator()
        self.automation_condition_evaluator = automation_condition_evaluator
        self.clarification_judge = clarification_judge
        self.query_response_judge = query_response_judge
        self.evaluate_predictions = evaluate_predictions
        self.strict_clarification_judge = strict_clarification_judge

    def evaluate_samples(self, samples: List[Sample]) -> List[EvaluationResult]:
        results: List[EvaluationResult] = []
        for sample in samples:
            results.append(self.evaluate_sample(sample))
        return results

    def evaluate_sample(self, sample: Sample) -> EvaluationResult:
        result, pending = self.evaluate_sample_local(sample)
        if not pending.has_work():
            return result
        return run_async(self.finalize_sample_evaluation(sample, result, pending))

    def evaluate_sample_local(self, sample: Sample) -> Tuple[EvaluationResult, PendingLLMJudges]:
        errors: List[str] = []
        try:
            ground_truth_critic_pass = self._evaluate_ground_truth(sample, errors)
            query_response_required = self._query_response_required(sample)
            if not self.evaluate_predictions:
                conditions_required = self._conditions_required(sample)
                clarifications_required = sample.has_clarification()
                return EvaluationResult(
                    uuid=sample.uuid,
                    query_idx=sample.query_idx,
                    critic_pass=None,
                    ground_truth_critic_pass=ground_truth_critic_pass,
                    query_response_pass=None,
                    conditions_pass=None,
                    clarification_passes=[],
                    query_response_required=query_response_required,
                    conditions_required=conditions_required,
                    clarifications_required=clarifications_required,
                    overall_pass=ground_truth_critic_pass,
                    category=sample.category,
                    errors=errors,
                    token_usage=self._prediction_token_usage(sample),
                ), PendingLLMJudges()
            critic_pass = self._evaluate_critic(sample, errors)
            conditions_required = self._conditions_required(sample)
            conditions_pass = self._evaluate_conditions(sample, errors, conditions_required)
            query_response_pass, pending_query_response = self._prepare_query_response(sample, errors, query_response_required)
            clarification_passes, pending_clarifications = self._prepare_clarifications(sample, errors)
            clarifications_required = sample.has_clarification()
            pending = PendingLLMJudges(
                query_response=pending_query_response,
                clarification_orders=pending_clarifications,
            )
            overall_pass = None
            if not pending.has_work():
                overall_pass = self._overall_pass(
                    critic_pass,
                    query_response_pass,
                    query_response_required,
                    conditions_pass,
                    conditions_required,
                    clarification_passes,
                    clarifications_required,
                )
            return EvaluationResult(
                uuid=sample.uuid,
                query_idx=sample.query_idx,
                critic_pass=critic_pass,
                ground_truth_critic_pass=ground_truth_critic_pass,
                query_response_pass=query_response_pass,
                conditions_pass=conditions_pass,
                clarification_passes=clarification_passes,
                query_response_required=query_response_required,
                conditions_required=conditions_required,
                clarifications_required=clarifications_required,
                overall_pass=overall_pass,
                category=sample.category,
                errors=errors,
                token_usage=self._prediction_token_usage(sample),
            ), pending
        except Exception as exc:
            errors.append(f"evaluation failed: {exc}")
            conditions_required = self._conditions_required(sample)
            clarifications_required = sample.has_clarification()
            return EvaluationResult(
                uuid=sample.uuid,
                query_idx=sample.query_idx,
                critic_pass=None,
                ground_truth_critic_pass=None,
                query_response_pass=None,
                conditions_pass=None,
                clarification_passes=[],
                query_response_required=self._query_response_required(sample),
                conditions_required=conditions_required,
                clarifications_required=clarifications_required,
                overall_pass=False,
                category=sample.category,
                errors=errors,
                token_usage=self._prediction_token_usage(sample),
            ), PendingLLMJudges()

    async def finalize_sample_evaluation(
        self,
        sample: Sample,
        result: EvaluationResult,
        pending: PendingLLMJudges,
    ) -> EvaluationResult:
        if pending.query_response and self.query_response_judge:
            query_response_result = await self.query_response_judge.aevaluate(sample)
            self._record_llm_error(query_response_result, "query_response", result.errors)
            result.query_response_pass = query_response_result.passed
        for order in pending.clarification_orders:
            if not self.clarification_judge:
                break
            clarifications = sample.predictions.clarifications if sample.predictions else []
            if order >= len(clarifications):
                continue
            history_until = json.dumps(sample.clarification_context(order), ensure_ascii=False)
            clarification_result = await self.clarification_judge.aevaluate(
                sample=sample,
                clarification=clarifications[order],
                history_until=history_until,
            )
            self._record_llm_error(clarification_result, f"clarification[{order}]", result.errors)
            result.clarification_passes[order] = clarification_result.passed
        result.overall_pass = self._overall_pass(
            result.critic_pass,
            result.query_response_pass,
            result.query_response_required,
            result.conditions_pass,
            result.conditions_required,
            result.clarification_passes,
            result.clarifications_required,
        )
        return result

    def _evaluate_ground_truth(self, sample: Sample, errors: List[str]) -> Optional[bool]:
        """Validate that ground-truth labels satisfy the critic expression.

        Useful for auditing dataset/critic correctness; does not affect overall pass.
        """

        labels = sample.ground_truth.get("labels") or []

        if not sample.critic:
            # Mirror _evaluate_critic(): if no critic, ensure labels are a no-op.
            if not labels:
                return True
            try:
                if self.critic_evaluator.labels_noop(sample.engine, labels):
                    return True
            except Exception as exc:
                errors.append(f"ground_truth labels noop check failed: {exc}")
                return False
            errors.append("ground_truth labels modify state but critic is empty")
            return False

        if not labels:
            errors.append("missing ground_truth.labels for critic evaluation")
            return False

        try:
            return self.critic_evaluator.evaluate(
                engine=sample.engine,
                labels=labels,
                critic=sample.critic,
            )
        except Exception as exc:
            errors.append(f"ground_truth critic evaluation failed: {exc}")
            return False

    def _evaluate_critic(self, sample: Sample, errors: List[str]) -> Optional[bool]:
        if sample.predictions is None:
            errors.append("missing predictions for critic evaluation")
            return False
        predicted_engine = sample.predictions.engine
        labels = sample.predictions.labels or []
        has_predicted_engine = predicted_engine is not None
        if not sample.critic:
            if has_predicted_engine:
                try:
                    if self._engines_equal(sample.engine, predicted_engine):
                        return True
                except Exception as exc:
                    errors.append(f"critic noop check failed: {exc}")
                    return False
                errors.append("unexpected state change: critic empty but engine modified state")
                return False
            if not labels:
                return True
            try:
                if self.critic_evaluator.labels_noop(sample.engine, labels):
                    return True
            except Exception as exc:
                errors.append(f"critic noop check failed: {exc}")
                return False
            errors.append("unexpected state change: critic empty but labels modify state")
            return False
        try:
            if has_predicted_engine:
                return self.critic_evaluator.evaluate_engine(
                    engine=predicted_engine,
                    critic=sample.critic,
                    baseline_engine=sample.engine,
                )
            if not labels:
                errors.append("missing predictions.labels for critic evaluation")
                return False
            return self.critic_evaluator.evaluate(
                engine=sample.engine,
                labels=labels,
                critic=sample.critic,
            )
        except Exception as exc:
            errors.append(f"critic evaluation failed: {exc}")
            return False

    def _evaluate_conditions(
        self, sample: Sample, errors: List[str], required: bool
    ) -> Optional[bool]:
        if sample.predictions is None:
            errors.append("missing predictions for conditions evaluation")
            return False if required else None
        if not sample.predictions.conditions:
            if required:
                errors.append("missing predictions.conditions for conditions evaluation")
                return False
            return None
        if not self.automation_condition_evaluator:
            errors.append("automation condition evaluator not configured")
            return False if required else None
        result = self.automation_condition_evaluator.evaluate(sample)
        self._record_llm_error(result, "conditions", errors)
        return result.passed

    def _prepare_query_response(
        self,
        sample: Sample,
        errors: List[str],
        required: bool,
    ) -> Tuple[Optional[bool], bool]:
        if not required:
            return None, False
        if sample.predictions is None:
            errors.append("missing predictions for query response evaluation")
            return False, False
        if sample.predictions.response is None or sample.predictions.response == "":
            errors.append("missing predictions.response for query response evaluation")
            return False, False
        if not self.query_response_judge:
            errors.append("query response judge not configured")
            return False, False
        return None, True

    def _prepare_clarifications(
        self,
        sample: Sample,
        errors: List[str],
    ) -> Tuple[List[Optional[bool]], List[int]]:
        if not sample.has_clarification():
            return [], []
        if not sample.predictions:
            errors.append("missing predictions for clarification evaluation")
            return [], []
        if self.strict_clarification_judge and not self.clarification_judge:
            errors.append("clarification judge not configured")
            return [], []
        clarifications = sample.predictions.clarifications or []
        clarification_mode_ok = sample.predictions.clarification_mode_ok or []
        indices = sample._clarification_indices()
        results: List[Optional[bool]] = []
        pending_orders: List[int] = []
        if len(clarifications) < len(indices):
            errors.append("insufficient predicted clarifications")
        if len(clarifications) > len(indices):
            errors.append("extra predicted clarifications")
        for order, _ in enumerate(indices):
            if order >= len(clarifications):
                results.append(None)
                continue
            if order < len(clarification_mode_ok) and clarification_mode_ok[order] is False:
                results.append(False)
                continue
            if not self.strict_clarification_judge:
                results.append(True)
                continue
            results.append(None)
            pending_orders.append(order)
        return results, pending_orders

    @staticmethod
    def _record_llm_error(result: LLMJudgeResult, scope: str, errors: List[str]) -> None:
        if result.error:
            errors.append(f"{scope} judge error: {result.error}")

    @staticmethod
    def _conditions_required(sample: Sample) -> bool:
        ground_truth_conditions = sample.ground_truth.get("conditions") or []
        predicted_conditions = []
        if sample.predictions is not None:
            predicted_conditions = sample.predictions.conditions or []
        return bool(ground_truth_conditions) or bool(predicted_conditions)

    @staticmethod
    def _query_response_required(sample: Sample) -> bool:
        ground_truth_response = sample.ground_truth.get("device_query_response")
        return ground_truth_response is not None and str(ground_truth_response).strip() != ""

    @staticmethod
    def _overall_pass(
        critic_pass: Optional[bool],
        query_response_pass: Optional[bool],
        query_response_required: bool,
        conditions_pass: Optional[bool],
        conditions_required: bool,
        clarification_passes: List[Optional[bool]],
        clarifications_required: bool,
    ) -> Optional[bool]:
        if critic_pass is not True:
            return False
        if query_response_required and query_response_pass is not True:
            return False
        if conditions_required and conditions_pass is not True:
            return False
        if clarifications_required:
            if not clarification_passes:
                return False
            if any(item is not True for item in clarification_passes):
                return False
        return True

    @staticmethod
    def _engines_equal(left: Dict[str, Any], right: Optional[Dict[str, Any]]) -> bool:
        if right is None:
            return False
        return left == right

    @staticmethod
    def _prediction_token_usage(sample: Sample) -> Optional[Dict[str, float]]:
        if sample.predictions is None:
            return {}
        return sample.predictions.token_usage or {}
