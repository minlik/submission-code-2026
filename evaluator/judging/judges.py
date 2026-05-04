import json
from typing import Any, Dict, Optional

from ..core.templates import TemplateLoader, TemplateRenderer
from ..core.types import LLMJudgeResult, Sample
from ..inference.env_summary import EnvironmentSummarizer
from ..llm.llm import JsonResponseParser, LLMRunner, run_async
from .judge_recorder import JudgeRecorder, build_record


class LLMJudge:
    def __init__(
        self,
        template_path: str,
        llm_runner: LLMRunner,
        template_loader: TemplateLoader,
        template_renderer: Optional[TemplateRenderer] = None,
        parser: Optional[JsonResponseParser] = None,
        recorder: Optional[JudgeRecorder] = None,
        judge_type: Optional[str] = None,
    ) -> None:
        self.template_path = template_path
        self.llm_runner = llm_runner
        self.template_loader = template_loader
        self.template_renderer = template_renderer or TemplateRenderer()
        self.parser = parser or JsonResponseParser()
        self.recorder = recorder
        self.judge_type = judge_type or template_path

    def build_prompt(self, sample: Sample, payload: Dict[str, Any]) -> str:
        template = self.template_loader.load(self.template_path)
        values = {key: self._stringify(value) for key, value in payload.items()}
        return self.template_renderer.render(template, values)

    def evaluate(self, sample: Sample, payload: Dict[str, Any]) -> LLMJudgeResult:
        return run_async(self.aevaluate(sample, payload))

    async def aevaluate(self, sample: Sample, payload: Dict[str, Any]) -> LLMJudgeResult:
        prompt = self.build_prompt(sample, payload)
        try:
            response = await self.llm_runner.generate(prompt, is_json_output=False)
        except Exception as exc:
            self._record(sample, prompt, payload, None, None, None, None, str(exc))
            return LLMJudgeResult(passed=None, reason=None, error=str(exc))
        try:
            parsed = self.parser.parse(response.content)
            validated = self.parser.validate(parsed)
            self._record(
                sample,
                prompt,
                payload,
                response.content,
                parsed,
                validated.get("passed"),
                validated.get("reason"),
                None,
            )
            return LLMJudgeResult(
                passed=validated.get("passed"),
                reason=validated.get("reason"),
                raw=parsed,
            )
        except Exception as exc:
            self._record(sample, prompt, payload, response.content, None, None, None, str(exc))
            return LLMJudgeResult(
                passed=None,
                reason=None,
                error=str(exc),
                raw=response.content,
            )

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def _record(
        self,
        sample: Sample,
        prompt: str,
        payload: Dict[str, Any],
        response_raw: Any,
        parsed: Any,
        passed: Optional[bool],
        reason: Optional[str],
        error: Optional[str],
    ) -> None:
        if not self.recorder:
            return
        record = build_record(
            judge_type=self.judge_type,
            uuid=sample.uuid,
            query_idx=sample.query_idx,
            prompt=prompt,
            input_payload=payload,
            response_raw=response_raw,
            parsed=parsed,
            passed=passed,
            reason=reason,
            error=error,
        )
        self.recorder.record(record)


class ClarificationJudge:
    def __init__(
        self,
        llm_runner: LLMRunner,
        template_loader: TemplateLoader,
        summarizer: Optional[EnvironmentSummarizer] = None,
        recorder: Optional[JudgeRecorder] = None,
    ) -> None:
        self.summarizer = summarizer or EnvironmentSummarizer()
        self.judge = LLMJudge(
            template_path="clarification_judge.md",
            llm_runner=llm_runner,
            template_loader=template_loader,
            recorder=recorder,
            judge_type="clarification",
        )

    def evaluate(self, sample: Sample, clarification: str, history_until: Any) -> LLMJudgeResult:
        return run_async(self.aevaluate(sample, clarification, history_until))

    async def aevaluate(self, sample: Sample, clarification: str, history_until: Any) -> LLMJudgeResult:
        env_summary = self.summarizer.summarize(sample.engine)
        payload = {
            "initial_query": sample.initial_query,
            "env_summary": env_summary,
            "history_until_now": history_until,
            "clarification": clarification,
        }
        return await self.judge.aevaluate(sample, payload)


class QueryResponseJudge:
    def __init__(
        self,
        llm_runner: LLMRunner,
        template_loader: TemplateLoader,
        recorder: Optional[JudgeRecorder] = None,
    ) -> None:
        self.judge = LLMJudge(
            template_path="query_response_judge.md",
            llm_runner=llm_runner,
            template_loader=template_loader,
            recorder=recorder,
            judge_type="query_response",
        )

    def evaluate(self, sample: Sample) -> LLMJudgeResult:
        return run_async(self.aevaluate(sample))

    async def aevaluate(self, sample: Sample) -> LLMJudgeResult:
        payload = {
            "initial_query": sample.initial_query,
            "ground_truth_response": sample.ground_truth.get("device_query_response"),
            "predicted_response": sample.predictions.response if sample.predictions else None,
        }
        return await self.judge.aevaluate(sample, payload)
