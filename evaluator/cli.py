import argparse
import asyncio
import copy
import glob
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .core.pipeline import EvaluationPipeline
from .core.report import ReportBuilder
from .core.templates import TemplateLoader
from .core.types import EvaluationResult, Prediction, PredictionRecord, Sample
from .data.aligner import PredictionAligner
from .data.dataset import DatasetFile, DatasetLoader
from .data.io import read_jsonl, write_jsonl, write_json
from .inference.assistant_prompt import AssistantPromptBuilder
from .inference.config import build_context_formatter, resolve_inference_config
from .inference.inference import AssistantInferenceRunner
from .inference.prompt_builder import ToolAwarePromptBuilder
from .inference.tool_calling_runner import ToolCallingRunner
from .judging.automation_conditions import AutomationConditionEvaluator
from .judging.judge_recorder import JudgeRecorder
from .judging.judges import ClarificationJudge, QueryResponseJudge
from .llm.llm import LLMClientRunner
from .tools import (
    advanced_tool_profile,
    build_default_tool_registry,
    code_profile,
    full_context_tool_profile,
    tool_profile,
)
from utils.env_util import load_dotenv


def load_predictions(path: Optional[str]) -> List[PredictionRecord]:
    if not path:
        return []
    return [PredictionRecord.from_dict(item) for item in read_jsonl(path)]


def apply_output_paths(args: argparse.Namespace) -> None:
    output_dir = args.out_dir
    if output_dir:
        args.results_out = _join_output_dir(output_dir, args.results_out, "eval_results.jsonl", "--results-out")
        args.predictions_out = _join_output_dir(
            output_dir, args.predictions_out, "predictions.jsonl", "--predictions-out"
        )
        args.summary_out = _join_output_dir(output_dir, args.summary_out, "summary.json", "--summary-out")
        args.judge_traces_out = _join_output_dir(
            output_dir, args.judge_traces_out, "judge_traces.jsonl", "--judge-traces-out"
        )
        return
    _validate_output_path(args.results_out, "--results-out")
    _validate_output_path(args.predictions_out, "--predictions-out")
    _validate_output_path(args.summary_out, "--summary-out")
    _validate_output_path(args.judge_traces_out, "--judge-traces-out")


def _join_output_dir(
    output_dir: str, path: Optional[str], default_name: str, flag_name: str
) -> Optional[str]:
    if not path:
        return os.path.join(output_dir, default_name)
    _validate_output_path(path, flag_name)
    if os.path.isabs(path):
        return path
    if os.path.dirname(path):
        return path
    return os.path.join(output_dir, path)


def _validate_output_path(path: Optional[str], flag_name: str) -> None:
    if not path:
        return
    if path.endswith(os.sep):
        raise RuntimeError(f"{flag_name} expects a file path, got directory-like path: {path}")
    if os.path.exists(path) and os.path.isdir(path):
        raise RuntimeError(f"{flag_name} expects a file path, got directory: {path}")


def collect_data_paths(data_dir: str) -> List[str]:
    jsonl_paths: List[str] = []
    for root, _, files in os.walk(data_dir):
        for name in files:
            if name.endswith(".jsonl"):
                jsonl_paths.append(os.path.join(root, name))
    return sorted(jsonl_paths)


def expand_data_files(paths: List[str]) -> List[str]:
    """Allow shell-like globs (e.g., data/v4_no_entrance/**/*.jsonl)."""

    expanded: List[str] = []
    for item in paths:
        if os.path.exists(item):
            expanded.append(item)
            continue
        matches = glob.glob(item, recursive=True)
        if matches:
            expanded.extend(sorted(matches))
            continue
        raise RuntimeError(f"data file pattern not found: {item}")
    # deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for path in expanded:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def limit_dataset_files(
    dataset_files: List[DatasetFile], max_samples: int
) -> Tuple[List[DatasetFile], List[Sample]]:
    if max_samples <= 0:
        samples = [sample for dataset in dataset_files for sample in dataset.samples]
        return dataset_files, samples
    remaining = max_samples
    limited_files: List[DatasetFile] = []
    limited_samples: List[Sample] = []
    for dataset in dataset_files:
        if remaining <= 0:
            break
        take = min(len(dataset.samples), remaining)
        if take <= 0:
            continue
        if take == len(dataset.samples):
            limited_files.append(dataset)
            limited_samples.extend(dataset.samples)
        else:
            limited = DatasetFile(
                path=dataset.path,
                records=dataset.records[:take],
                samples=dataset.samples[:take],
            )
            limited_files.append(limited)
            limited_samples.extend(limited.samples)
        remaining -= take
    return limited_files, limited_samples


def progress_step(total: int) -> int:
    if total <= 20:
        return 1
    if total <= 200:
        return 10
    if total <= 1000:
        return 50
    return 100


def should_log_progress(index: int, total: int, step: int) -> bool:
    if index == 1 or index == total:
        return True
    return step > 0 and index % step == 0

def build_pipeline(args: argparse.Namespace, judge_llm_runner: Optional[LLMClientRunner]) -> EvaluationPipeline:
    evaluate_predictions = not getattr(args, "ground_truth_only", False)
    strict_clarification_judge = getattr(args, "strict_clarification_judge", False)
    automation_condition_evaluator = None
    clarification_judge = None
    query_response_judge = None
    if evaluate_predictions:
        automation_condition_evaluator = AutomationConditionEvaluator()
    if evaluate_predictions and judge_llm_runner:
        template_loader = TemplateLoader(args.template_dir)
        recorder = JudgeRecorder(args.judge_traces_out) if args.judge_traces_out else None
        if strict_clarification_judge:
            clarification_judge = ClarificationJudge(
                llm_runner=judge_llm_runner,
                template_loader=template_loader,
                recorder=recorder,
            )
        query_response_judge = QueryResponseJudge(
            llm_runner=judge_llm_runner,
            template_loader=template_loader,
            recorder=recorder,
        )
    return EvaluationPipeline(
        automation_condition_evaluator=automation_condition_evaluator,
        clarification_judge=clarification_judge,
        query_response_judge=query_response_judge,
        evaluate_predictions=evaluate_predictions,
        strict_clarification_judge=strict_clarification_judge,
    )


def build_llm_runner(args: argparse.Namespace) -> Optional[LLMClientRunner]:
    if not args.model_url or not args.model_name:
        return None
    return LLMClientRunner(
        model_url=args.model_url,
        api_key=args.api_key,
        model_name=args.model_name,
        temperature=args.temperature,
        user=args.aigc_user,
        enable_thinking=args.enable_thinking,
        reasoning_effort=args.reasoning_effort,
    )


def build_judge_llm_runner(
    env_defaults: Dict[str, str],
    temperature: float,
    enable_thinking: bool,
    reasoning_effort: str,
) -> Optional[LLMClientRunner]:
    model_url = env_defaults.get("DEFAULT_MODEL_URL", "")
    model_name = env_defaults.get("DEFAULT_MODEL_NAME", "")
    api_key = env_defaults.get("DEFAULT_API_KEY", "")
    if not model_url or not model_name or not api_key:
        return None
    return LLMClientRunner(
        model_url=model_url,
        api_key=api_key,
        model_name=model_name,
        temperature=temperature,
        user=env_defaults.get("DEFAULT_AIGC_USER", ""),
        enable_thinking=enable_thinking,
        reasoning_effort=reasoning_effort,
    )


def apply_env_defaults(args: argparse.Namespace) -> Dict[str, str]:
    defaults = load_dotenv(args.env_path)
    args.api_key = args.api_key or defaults.get("DEFAULT_API_KEY", "")
    args.model_url = args.model_url or defaults.get("DEFAULT_MODEL_URL", "")
    args.model_name = args.model_name or defaults.get("DEFAULT_MODEL_NAME", "")
    args.aigc_user = args.aigc_user or defaults.get("DEFAULT_AIGC_USER", "")
    return defaults


def load_default_engine(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"--default-engine-file must contain a JSON object: {path}")
    return payload


def apply_default_engine(dataset_files: List[DatasetFile], default_engine: Optional[Dict[str, Any]]) -> None:
    if not default_engine:
        return
    for dataset in dataset_files:
        for sample in dataset.samples:
            if sample.engine:
                continue
            sample.engine = copy.deepcopy(default_engine)


def build_inference_runner(args: argparse.Namespace) -> Any:
    template_loader = TemplateLoader(args.template_dir)
    resolved = resolve_inference_config(args)
    if resolved.tool_profile_name is None:
        prompt_builder = AssistantPromptBuilder(
            template_loader=template_loader,
            template_name=resolved.template_name,
        )
        return AssistantInferenceRunner(prompt_builder)
    profile = _build_tool_profile(resolved.tool_profile_name)
    registry = build_default_tool_registry()
    prompt_builder = ToolAwarePromptBuilder(
        template_loader=template_loader,
        template_name=resolved.template_name,
        formatter=build_context_formatter(resolved.context_mode),
    )
    return ToolCallingRunner(
        prompt_builder=prompt_builder,
        registry=registry,
        profile=profile,
        max_tool_calls=args.max_tool_calls,
    )


def _build_tool_profile(profile_name: str | None) -> Any:
    if profile_name == "tool":
        return tool_profile()
    if profile_name == "advanced_tool":
        return advanced_tool_profile()
    if profile_name == "code":
        return code_profile()
    if profile_name == "full_context_tool":
        return full_context_tool_profile()
    raise ValueError(f"unsupported tool profile: {profile_name}")


def infer_predictions(
    dataset_files: List[DatasetFile],
    args: argparse.Namespace,
    llm_runner: LLMClientRunner,
) -> Tuple[List[PredictionRecord], Dict[Tuple[Optional[str], Optional[int]], List[str]]]:
    if args.concurrency and args.concurrency > 1:
        return asyncio.run(infer_predictions_async(dataset_files, args, llm_runner))
    inference_runner = build_inference_runner(args)
    prediction_records: List[PredictionRecord] = []
    infer_errors: Dict[Tuple[Optional[str], Optional[int]], List[str]] = {}
    file_total = len(dataset_files)
    for file_idx, dataset in enumerate(dataset_files, start=1):
        total = len(dataset.samples)
        step = progress_step(total)
        print(f"[infer] file {file_idx}/{file_total}: {dataset.path} ({total} samples)")
        for idx, sample in enumerate(dataset.samples, start=1):
            prediction, predicted_history, errors, action_errors, messages = _safe_infer_sample(
                inference_runner, sample, llm_runner
            )
            sample.predictions = prediction
            prediction_records.append(
                PredictionRecord(
                    uuid=sample.uuid,
                    query_idx=sample.query_idx,
                    predictions=prediction,
                    initial_query=sample.initial_query,
                    history=predicted_history,
                    messages=messages or None,
                    action_errors=action_errors or None,
                    inference_errors=errors or None,
                )
            )
            if errors:
                infer_errors[(sample.uuid, sample.query_idx)] = errors
            if should_log_progress(idx, total, step):
                print(f"[infer] {dataset.path}: {idx}/{total}")
    return prediction_records, infer_errors


def evaluate_with_progress(
    pipeline: EvaluationPipeline,
    dataset_files: List[DatasetFile],
    concurrency: int,
) -> List[Any]:
    if (
        concurrency
        and concurrency > 1
        and hasattr(pipeline, "evaluate_sample_local")
        and hasattr(pipeline, "finalize_sample_evaluation")
    ):
        return asyncio.run(evaluate_with_progress_async(pipeline, dataset_files, concurrency))
    results: List[Any] = []
    file_total = len(dataset_files)
    for file_idx, dataset in enumerate(dataset_files, start=1):
        total = len(dataset.samples)
        step = progress_step(total)
        print(f"[eval] file {file_idx}/{file_total}: {dataset.path} ({total} samples)")
        for idx, sample in enumerate(dataset.samples, start=1):
            results.append(_safe_evaluate(pipeline, sample))
            if should_log_progress(idx, total, step):
                print(f"[eval] {dataset.path}: {idx}/{total}")
    return results


async def infer_predictions_async(
    dataset_files: List[DatasetFile],
    args: argparse.Namespace,
    llm_runner: LLMClientRunner,
) -> Tuple[List[PredictionRecord], Dict[Tuple[Optional[str], Optional[int]], List[str]]]:
    prediction_records: List[PredictionRecord] = []
    infer_errors: Dict[Tuple[Optional[str], Optional[int]], List[str]] = {}
    sem = asyncio.Semaphore(args.concurrency)
    file_total = len(dataset_files)
    for file_idx, dataset in enumerate(dataset_files, start=1):
        total = len(dataset.samples)
        step = progress_step(total)
        print(f"[infer] file {file_idx}/{file_total}: {dataset.path} ({total} samples)")
        tasks = [
            asyncio.create_task(_infer_one_sample(idx, sample, args, llm_runner, sem))
            for idx, sample in enumerate(dataset.samples)
        ]
        completed = 0
        results_by_index: List[Tuple[Prediction, List[Dict[str, Any]], List[str], List[str], List[Dict[str, Any]]]] = [
            (Prediction(), [], [], [], []) for _ in dataset.samples
        ]
        for task in asyncio.as_completed(tasks):
            idx, result = await task
            prediction, predicted_history, errors, action_errors, messages = result
            sample = dataset.samples[idx]
            sample.predictions = prediction
            results_by_index[idx] = result
            if errors:
                infer_errors[(sample.uuid, sample.query_idx)] = errors
            completed += 1
            if should_log_progress(completed, total, step):
                print(f"[infer] {dataset.path}: {completed}/{total}")
        for idx, sample in enumerate(dataset.samples):
            prediction, predicted_history, errors, action_errors, messages = results_by_index[idx]
            prediction_records.append(
                PredictionRecord(
                    uuid=sample.uuid,
                    query_idx=sample.query_idx,
                    predictions=prediction,
                    initial_query=sample.initial_query,
                    history=predicted_history,
                    messages=messages or None,
                    action_errors=action_errors or None,
                    inference_errors=errors or None,
                )
            )
    return prediction_records, infer_errors


async def _infer_one_sample(
    index: int,
    sample: Sample,
    args: argparse.Namespace,
    llm_runner: LLMClientRunner,
    sem: asyncio.Semaphore,
) -> Tuple[int, Tuple[Prediction, List[Dict[str, Any]], List[str], List[str], List[Dict[str, Any]]]]:
    async with sem:
        inference_runner = build_inference_runner(args)
        result = await asyncio.to_thread(_safe_infer_sample, inference_runner, sample, llm_runner)
        return index, result


def _safe_infer_sample(
    inference_runner: Any,
    sample: Sample,
    llm_runner: LLMClientRunner,
) -> Tuple[Prediction, List[Dict[str, Any]], List[str], List[str], List[Dict[str, Any]]]:
    try:
        return inference_runner.infer_sample(sample, llm_runner)
    except Exception as exc:
        error_message = f"uncaught inference exception: {type(exc).__name__}: {exc}"
        error_stage = [
            {
                "stage": "error",
                "order": 0,
                "messages": [
                    {
                        "role": "assistant",
                        "content": f"[inference exception] {type(exc).__name__}: {exc}",
                    }
                ],
            }
        ]
        return Prediction(), [], [error_message], [], error_stage


async def evaluate_with_progress_async(
    pipeline: EvaluationPipeline,
    dataset_files: List[DatasetFile],
    concurrency: int,
) -> List[Any]:
    results: List[Any] = []
    sem = asyncio.Semaphore(concurrency)
    file_total = len(dataset_files)
    for file_idx, dataset in enumerate(dataset_files, start=1):
        total = len(dataset.samples)
        step = progress_step(total)
        print(f"[eval] file {file_idx}/{file_total}: {dataset.path} ({total} samples)")
        completed = 0
        results_by_index: List[Any] = [None for _ in dataset.samples]
        tasks = []
        for idx, sample in enumerate(dataset.samples):
            result, pending = pipeline.evaluate_sample_local(sample)
            if pending.has_work():
                tasks.append(
                    asyncio.create_task(_finalize_one_sample(idx, sample, pipeline, result, pending, sem))
                )
                continue
            results_by_index[idx] = result
            completed += 1
            if should_log_progress(completed, total, step):
                print(f"[eval] {dataset.path}: {completed}/{total}")
        for task in asyncio.as_completed(tasks):
            idx, result = await task
            results_by_index[idx] = result
            completed += 1
            if should_log_progress(completed, total, step):
                print(f"[eval] {dataset.path}: {completed}/{total}")
        results.extend(results_by_index)
    return results


async def _finalize_one_sample(
    index: int,
    sample: Sample,
    pipeline: EvaluationPipeline,
    result: EvaluationResult,
    pending: Any,
    sem: asyncio.Semaphore,
) -> Tuple[int, Any]:
    async with sem:
        finalized = await pipeline.finalize_sample_evaluation(sample, result, pending)
        return index, finalized


async def _evaluate_one_sample(
    index: int,
    sample: Sample,
    pipeline: EvaluationPipeline,
    sem: asyncio.Semaphore,
) -> Tuple[int, Any]:
    async with sem:
        result = await asyncio.to_thread(_safe_evaluate, pipeline, sample)
        return index, result


def _safe_evaluate(pipeline: EvaluationPipeline, sample: Sample) -> EvaluationResult:
    try:
        return pipeline.evaluate_sample(sample)
    except Exception as exc:  # pragma: no cover - defensive
        errors = [f"unhandled evaluation exception: {exc}"]
        conditions_required = pipeline._conditions_required(sample)
        clarifications_required = sample.has_clarification()
        return EvaluationResult(
            uuid=sample.uuid,
            query_idx=sample.query_idx,
            critic_pass=None,
            ground_truth_critic_pass=None,
            query_response_pass=None,
            conditions_pass=None,
            clarification_passes=[],
            conditions_required=conditions_required,
            clarifications_required=clarifications_required,
            overall_pass=False,
            category=sample.category,
            errors=errors,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Home Agent evaluator scaffold")
    parser.add_argument("--data-files", nargs="+", help="data JSONL paths")
    parser.add_argument("--data-dir", help="data directory containing JSONL files")
    parser.add_argument("--default-engine-file", help="fallback engine JSON file for samples missing inline engine")
    parser.add_argument("--predictions-in", help="predictions JSONL path")
    parser.add_argument("--results-out", help="eval output JSONL path")
    parser.add_argument("--out-dir", help="output directory for all outputs")
    parser.add_argument("--predictions-out", help="predictions output JSONL path")
    parser.add_argument("--summary-out", help="summary report JSON path")
    parser.add_argument(
        "--ground-truth-only",
        action="store_true",
        help="only validate ground_truth against critic; skip predictions/inference and prediction-based judges",
    )
    parser.add_argument(
        "--strict-clarification-judge",
        action="store_true",
        help="strictly judge clarification content with LLM; default only checks clarification turn alignment",
    )
    parser.add_argument("--inference", action="store_true", help="run inference")
    parser.add_argument(
        "--inference-mode",
        default="context",
        choices=["context", "code", "tool", "advanced_tool", "full_context_tool"],
        help=(
            "context: current JSON action chain; code: clarification text + pyexec tool chain; "
            "tool: legacy query/control tool chain; advanced_tool: structured selection/spec/status/batch-control chain; "
            "full_context_tool: control/create-automation tool chain with full home context"
        ),
    )
    parser.add_argument("--judge-traces-out", help="LLM judge trace JSONL path")
    parser.add_argument("--template-dir", default="template", help="template directory")
    parser.add_argument("--template-assistant-context", default="assistant_context.md", help="assistant inference template file")
    parser.add_argument(
        "--template-assistant-code",
        default="assistant_code_v3.md",
        help="code-mode assistant template file",
    )
    parser.add_argument(
        "--template-assistant-tool",
        default="assistant_tool_v3.md",
        help="tool-mode assistant template file",
    )
    parser.add_argument(
        "--template-assistant-advanced-tool",
        default="assistant_tool_advanced.md",
        help="advanced-tool-mode assistant template file",
    )
    parser.add_argument(
        "--template-assistant-full-context-tool",
        default="assistant_tool_full_context.md",
        help="full-context-tool-mode assistant template file",
    )
    parser.add_argument(
        "--assistant-template",
        default="",
        help="optional unified assistant template override",
    )
    parser.add_argument(
        "--tool-profile",
        choices=["tool", "advanced_tool", "code", "full_context_tool"],
        help="optional tool profile override for tool-calling inference",
    )
    parser.add_argument(
        "--context-mode",
        choices=["brief", "full"],
        help="optional home context formatting override",
    )
    parser.add_argument("--env-path", default=".env", help="dotenv file path")
    parser.add_argument("--model-url", default="", help="model URL")
    parser.add_argument("--api-key", default="", help="API key")
    parser.add_argument("--model-name", default="", help="model name")
    parser.add_argument("--temperature", type=float, default=0.0, help="model temperature")
    parser.add_argument(
        "--reasoning-effort",
        default="medium",
        choices=["low", "medium", "high"],
        help="reasoning effort for GPT-5 family models",
    )
    parser.add_argument("--enable-thinking", action="store_true", help="enable model thinking mode")
    parser.add_argument("--aigc-user", default="", help="AIGC user")
    parser.add_argument("--max-samples", type=int, default=0, help="limit samples for debugging")
    parser.add_argument("--concurrency", type=int, default=20, help="max concurrent LLM requests")
    parser.add_argument("--max-tool-calls", type=int, default=10, help="max tool calls in code inference mode")
    args = parser.parse_args()

    if args.ground_truth_only and args.inference:
        raise RuntimeError("--ground-truth-only cannot be combined with --inference")
    if args.ground_truth_only and args.predictions_in:
        raise RuntimeError("--ground-truth-only should not be used with --predictions-in")

    env_defaults = apply_env_defaults(args)
    apply_output_paths(args)
    if not args.results_out:
        raise RuntimeError("output path is required (use --results-out or --out-dir)")
    data_paths: List[str] = []
    if args.data_files:
        data_paths.extend(expand_data_files(args.data_files))
    if args.data_dir:
        data_paths.extend(collect_data_paths(args.data_dir))
    if not data_paths:
        raise RuntimeError("data path is required (use --data-files or --data-dir)")
    dataset_loader = DatasetLoader()
    dataset_files, samples = dataset_loader.load(data_paths)
    dataset_loader.ensure_uuids(dataset_files)
    if args.max_samples:
        dataset_files, samples = limit_dataset_files(dataset_files, args.max_samples)
    default_engine = load_default_engine(args.default_engine_file)
    apply_default_engine(dataset_files, default_engine)

    predictions: List[PredictionRecord] = []
    if not args.ground_truth_only:
        predictions = load_predictions(args.predictions_in)
        if predictions:
            PredictionAligner().align(samples, predictions)

    inference_llm_runner = build_llm_runner(args)
    judge_llm_runner = None
    if not args.ground_truth_only:
        judge_llm_runner = build_judge_llm_runner(
            env_defaults, args.temperature, args.enable_thinking, args.reasoning_effort
        )
        if judge_llm_runner is None:
            raise RuntimeError("LLM judge config missing in .env (DEFAULT_MODEL_URL/DEFAULT_MODEL_NAME/DEFAULT_API_KEY)")
    infer_errors: Dict[Tuple[Optional[str], Optional[int]], List[str]] = {}
    if args.inference:
        if inference_llm_runner is None:
            raise RuntimeError("LLM config missing for inference")
        predictions, infer_errors = infer_predictions(dataset_files, args, inference_llm_runner)
        if args.predictions_out:
            os.makedirs(os.path.dirname(args.predictions_out) or ".", exist_ok=True)
            write_jsonl(args.predictions_out, [record.to_dict() for record in predictions])

    pipeline = build_pipeline(args, judge_llm_runner)
    results = evaluate_with_progress(pipeline, dataset_files, args.concurrency)
    for result in results:
        key = (result.uuid, result.query_idx)
        if key in infer_errors:
            result.errors.extend(infer_errors[key])
    os.makedirs(os.path.dirname(args.results_out) or ".", exist_ok=True)
    write_jsonl(args.results_out, [result.to_dict() for result in results])

    if args.summary_out:
        metadata: Dict[str, str] = {}
        if args.inference:
            metadata["inference_model_name"] = args.model_name
            metadata["inference_model_url"] = args.model_url
            metadata["inference_reasoning_effort"] = args.reasoning_effort
            metadata["inference_mode"] = args.inference_mode
            if args.aigc_user:
                metadata["inference_aigc_user"] = args.aigc_user
        predictions_path = None
        if args.predictions_in:
            predictions_path = args.predictions_in
        elif args.predictions_out:
            predictions_path = args.predictions_out
        if predictions_path:
            metadata["predictions_path"] = predictions_path
        report = ReportBuilder().build(
            results,
            metadata if metadata else None,
            samples=samples,
        )
        os.makedirs(os.path.dirname(args.summary_out) or ".", exist_ok=True)
        write_json(args.summary_out, report)


if __name__ == "__main__":
    main()
