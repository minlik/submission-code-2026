from typing import Any, Dict, List, Optional

from .types import EvaluationResult, Sample


class ReportBuilder:

    def _token_stats(self, results: List[EvaluationResult]):
        tokens = dict()
        if not results:
            return tokens
        for result in results:
            usage = result.token_usage or {}
            for k, v in usage.items():
                tokens[k] = tokens.get(k, 0) + v
        for k, v in tokens.items():
            tokens[k] = v / len(results)
        return tokens

    def build(
        self,
        results: List[EvaluationResult],
        metadata: Optional[Dict[str, Any]] = None,
        samples: Optional[List[Sample]] = None,
    ) -> Dict[str, Any]:
        ground_truth_critic_vals = [
            r.ground_truth_critic_pass for r in results if r.ground_truth_critic_pass is not None
        ]
        critic_vals = [r.critic_pass for r in results if r.critic_pass is not None]
        query_response_vals = [r.query_response_pass for r in results if r.query_response_pass is not None]
        conditions_vals = [r.conditions_pass for r in results if r.conditions_pass is not None]
        clarification_vals: List[bool] = []
        for result in results:
            for item in result.clarification_passes:
                if item is not None:
                    clarification_vals.append(item)

        overall_vals = [r.overall_pass for r in results if r.overall_pass is not None]
        report: Dict[str, Any] = {
            "total_samples": len(results),
            "ground_truth_critic_pass_rate": self._rate(ground_truth_critic_vals),
            "critic_pass_rate": self._rate(critic_vals),
            "query_response_pass_rate": self._rate(query_response_vals),
            "conditions_pass_rate": self._rate(conditions_vals),
            "clarification_pass_rate": self._rate(clarification_vals),
            "final_pass_rate": self._rate(overall_vals),
            "ground_truth_critic_evaluated": len(ground_truth_critic_vals),
            "critic_evaluated": len(critic_vals),
            "query_response_evaluated": len(query_response_vals),
            "conditions_evaluated": len(conditions_vals),
            "clarifications_evaluated": len(clarification_vals),
            "final_evaluated": len(overall_vals),
            "token_usage": self._token_stats(results),
        }
        if metadata:
            report.update(metadata)
        if samples:
            report["categories"] = self._category_summaries(results, samples)
        return report

    def _rate(self, values: List[bool]) -> Optional[float]:
        if not values:
            return None
        return sum(1 for v in values if v) / len(values)

    def _category_summaries(
        self, results: List[EvaluationResult], samples: List[Sample]
    ) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, List[EvaluationResult]] = {}
        for result, sample in zip(results, samples):
            category = sample.category or "unknown"
            for key in self._category_keys(category):
                groups.setdefault(key, []).append(result)
        summaries: Dict[str, Dict[str, Any]] = {}
        for key, group_results in groups.items():
            summaries[key] = self._group_stats(group_results)
        return summaries

    def _category_keys(self, category: str) -> List[str]:
        parts = [p for p in category.split("/") if p]
        keys: List[str] = []
        for idx in range(len(parts)):
            keys.append("/".join(parts[: idx + 1]))
        return keys or [category]

    def _group_stats(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        ground_truth_critic_vals = [
            r.ground_truth_critic_pass for r in results if r.ground_truth_critic_pass is not None
        ]
        critic_vals = [r.critic_pass for r in results if r.critic_pass is not None]
        query_response_vals = [r.query_response_pass for r in results if r.query_response_pass is not None]
        conditions_vals = [r.conditions_pass for r in results if r.conditions_pass is not None]
        clarification_vals: List[bool] = []
        for result in results:
            for item in result.clarification_passes:
                if item is not None:
                    clarification_vals.append(item)
        overall_vals = [r.overall_pass for r in results if r.overall_pass is not None]
        return {
            "total_samples": len(results),
            "ground_truth_critic_pass_rate": self._rate(ground_truth_critic_vals),
            "critic_pass_rate": self._rate(critic_vals),
            "query_response_pass_rate": self._rate(query_response_vals),
            "conditions_pass_rate": self._rate(conditions_vals),
            "clarification_pass_rate": self._rate(clarification_vals),
            "final_pass_rate": self._rate(overall_vals),
            "ground_truth_critic_evaluated": len(ground_truth_critic_vals),
            "critic_evaluated": len(critic_vals),
            "query_response_evaluated": len(query_response_vals),
            "conditions_evaluated": len(conditions_vals),
            "clarifications_evaluated": len(clarification_vals),
            "final_evaluated": len(overall_vals),
            "token_usage": self._token_stats(results),
        }
