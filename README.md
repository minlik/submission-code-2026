# Home Agent Evaluator

A lightweight inference and evaluation framework for home-agent datasets.

It supports two documented inference/evaluation workflows:

- `context`: the model receives the full home context and returns a JSON action chain.
- `tool`: the model uses tool calls to query and control devices.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file or pass the same values through CLI flags:

```bash
DEFAULT_API_KEY=...
DEFAULT_MODEL_URL=...
DEFAULT_MODEL_NAME=...
DEFAULT_AIGC_USER=...
```

Inference prefers explicit CLI values such as `--model-url`, `--model-name`, `--api-key`, and `--aigc-user`. If they are omitted, values are read from `.env`.

## Data

Input data is JSONL. Each sample contains a user query, optional history and memory, an initial home `engine`, expected `ground_truth`, and a `critic` expression.

Minimal shape:

```json
{
  "uuid": "sample-uuid",
  "query_idx": 0,
  "initial_query": "Turn on the living room light",
  "history": [],
  "memory_list": [],
  "entrance": "device-id",
  "engine": {"home": {"name": "home", "rooms": [], "devices": []}},
  "ground_truth": {
    "labels": [{"did": "light-1", "attribute": "power", "value": "on"}],
    "conditions": [],
    "device_query_response": ""
  },
  "critic": "device('light-1').power == 'on'"
}
```

Use `--default-engine-file` when samples do not include an inline `engine`.

## Inference Modes

### `context`

`context` mode uses the full home JSON context.

Defaults:

- context formatter: `full`
- assistant template: `template/assistant_context_detail.md`
- no tool profile

Example:

```bash
python -m evaluator.cli \
  --data-dir data/simple/atom/clear \
  --out-dir outputs/context_run \
  --inference \
  --inference-mode context \
  --default-engine-file data/complex/engine.json
```

### `tool`

`tool` mode uses the default tool-calling profile.

Defaults:

- context formatter: `brief`
- assistant template: `template/assistant_tool_detail.md`
- tools: `query_device`, `control_device`, `create_automation_actions`

Example:

```bash
python -m evaluator.cli \
  --data-dir data/simple/atom/clear \
  --out-dir outputs/tool_run \
  --inference \
  --inference-mode tool \
  --default-engine-file data/complex/engine.json \
  --max-tool-calls 10
```

You can override the assistant template for one run:

```bash
python -m evaluator.cli \
  --data-dir data/simple/atom/clear \
  --out-dir outputs/tool_run \
  --inference \
  --inference-mode tool \
  --assistant-template assistant_tool_detail.md
```

## Evaluation

Evaluation checks:

- `critic_pass`: predicted state changes satisfy the sample `critic`.
- `ground_truth_critic_pass`: ground truth labels satisfy the sample `critic`.
- `conditions_pass`: automation trigger conditions are equivalent when required.
- `clarification_passes`: required clarification turns are aligned.
- `query_response_pass`: predicted answers match the ground truth response when required.
- `overall_pass`: all required checks pass.

Run inference and evaluation together:

```bash
python -m evaluator.cli \
  --data-files data/simple/atom/clear/dataset.jsonl \
  --out-dir outputs/run1 \
  --inference \
  --inference-mode context
```

Evaluate existing predictions:

```bash
python -m evaluator.cli \
  --data-files data/simple/atom/clear/dataset.jsonl \
  --predictions-in outputs/run1/predictions.jsonl \
  --results-out outputs/run1/eval_results.jsonl \
  --summary-out outputs/run1/summary.json \
  --judge-traces-out outputs/run1/judge_traces.jsonl
```

Validate only ground truth and critic consistency:

```bash
python -m evaluator.cli \
  --data-files data/simple/atom/clear/dataset.jsonl \
  --results-out outputs/run1/gt_eval.jsonl \
  --summary-out outputs/run1/gt_summary.json \
  --ground-truth-only
```

## Outputs

Common output files:

- `predictions.jsonl`: model predictions from inference.
- `eval_results.jsonl`: per-sample evaluation details.
- `summary.json`: aggregate pass rates, category statistics, and average token usage.
- `judge_traces.jsonl`: LLM judge prompts, inputs, raw outputs, and parsed results.

`--out-dir` fills default output paths automatically. You can also set each output path explicitly.

## Useful CLI Flags

- `--data-files`: one or more JSONL files. Glob patterns are expanded by the CLI.
- `--data-dir`: recursively evaluate all JSONL files under a directory.
- `--default-engine-file`: fallback home engine for samples without `engine`.
- `--inference`: run model inference before evaluation.
- `--inference-mode context|tool`: choose the documented inference workflow.
- `--predictions-in`: evaluate an existing predictions file.
- `--predictions-out`: write inference predictions.
- `--out-dir`: shared output directory.
- `--max-samples`: limit samples for debugging.
- `--concurrency`: maximum concurrent LLM requests.
- `--max-tool-calls`: maximum tool-calling turns in `tool` mode.
- `--strict-clarification-judge`: use an LLM judge for clarification content instead of only checking turn alignment.
- `--enable-thinking`: enable model thinking mode when supported.
- `--reasoning-effort low|medium|high`: set reasoning effort for supported models.

## Helper Scripts

Two example scripts are included:

```bash
bash scripts/test_run_evaluator_end_to_end_context.sh
bash scripts/test_run_evaluator_end_to_end_tool.sh
```
