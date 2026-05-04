# Home Agent Evaluator

面向家庭智能体数据集的评测与推理框架，支持：

- 直接评测已有 `predictions.jsonl`
- 端到端跑模型推理，再进入统一评测
- 同时覆盖设备执行、自动化条件、澄清轮次、查询回答四类能力


## 推理路径

当前 inference 支持 5 条路径：

- `context`
  - 模型直接输出 JSON action chain。
  - 默认模板：`template/assistant_context.md`
  - 默认上下文：`full`

- `tool`
  - 使用 `query_device`、`control_device`、`create_automation_actions`
  - 默认模板：`template/assistant_tool_v3.md`
  - 默认上下文：`brief`

- `advanced_tool`
  - 使用 `select_device`、`query_device_spec`、`query_device_status`、`control_device_batch`、`create_automation_batch_actions`
  - 默认模板：`template/assistant_tool_advanced.md`
  - 默认上下文：`brief`

- `code`
  - 使用 `pyexec`、`create_automation_code`
  - 默认模板：`template/assistant_code_v3.md`
  - 默认上下文：`brief`

- `full_context_tool`
  - 使用 `control_device`、`create_automation_actions`
  - 默认模板：`template/assistant_tool_full_context.md`
  - 默认上下文：`full`

说明：

- `--tool-profile` 可以覆盖工具集合，但不能与 `inference_mode=context` 组合。
- `--context-mode` 可以覆盖上下文格式。
- `--assistant-template` 可以统一覆盖最终 assistant 模板。

## 上下文格式

- `full`
  - 由 [evaluator/inference/home_env.py](./evaluator/inference/home_env.py) 生成。
  - 输出完整家庭 JSON，包括 `rooms`、去重后的 `device_types`、设备实例状态、`entrance`、`current_time`。

- `brief`
  - 由 [evaluator/inference/code_home_env.py](./evaluator/inference/code_home_env.py) 生成。
  - 输出“房间列表 + 设备索引 + entrance + 时间”的结构化文本摘要，更适合 tool/code 模式。

## 评测逻辑

### 1. Critic

- 总是执行 `ground_truth_critic_pass` 校验，用于检查标注是否与 `critic` 自洽。
- 正常评测时还会计算 `critic_pass`。
- 如果预测中带 `predictions.engine`，则直接用最终环境评测，不再应用 `predictions.labels`。
- 否则将 `predictions.labels` 应用到初始 `engine` 上，再运行 `critic`。
- 如果 `critic` 为空，则要求预测不能引入状态变化。

### 2. Automation Conditions

- 只要 `ground_truth.conditions` 或 `predictions.conditions` 任一非空，就会进入 conditions 评测。
- `conditions` 必须是有序列表。
- 列表项必须且只能包含：
  - `time_cron`
  - `state_expr`
- 二者都允许为 `null`，但不能同时为 `null`。
- `time_cron` 通过固定锚点 + 固定采样窗口比较触发序列是否等价。
- `state_expr` 通过表达式等价性比较逻辑是否一致。

### 3. Clarification

- 只对数据中本来就存在 clarification 轮次的样本评测。
- 默认行为不是比较澄清内容，而是做轮次对齐检查：只要预测补齐了对应澄清轮，就可以通过。
- 打开 `--strict-clarification-judge` 后，才会使用 LLM judge 比较澄清内容。

### 4. Query Response

- 当 `ground_truth.device_query_response` 非空时启用。
- 使用 LLM judge 比较 `predictions.response` 与 GT 回答是否一致。

### 5. Overall Pass

单条样本最终通过条件为：

- `critic_pass` 通过
- 若需要 query response，则 `query_response_pass` 通过
- 若需要 conditions，则 `conditions_pass` 通过
- 若需要 clarification，则所有 `clarification_passes` 通过

## 数据格式

每个数据文件是 JSONL。最小样例如下：

```json
{
  "uuid": "optional; auto-filled if missing",
  "query_idx": 0,
  "initial_query": "打开客厅灯",
  "intended_query": "optional",
  "initial_chat_history": [{"role": "user", "content": "昨天那个自动化帮我关掉"}],
  "history": [
    {"role": "assistant", "content": {"mode": "clarification", "response": "你是指客厅主灯吗？"}},
    {"role": "user", "content": "对"}
  ],
  "memory_list": ["用户睡前会关灯"],
  "entrance": "device-id",
  "engine": {"home": {"name": "home", "rooms": [], "devices": []}},
  "ground_truth": {
    "labels": [{"did": "light-1", "attribute": "power", "value": "on"}],
    "conditions": [
      {
        "time_cron": "0 0 22 * * ? *",
        "state_expr": "device('light-1').power == 'off'"
      }
    ],
    "device_query_response": "客厅主灯已打开"
  },
  "critic": "device('light-1').power == 'on'"
}
```

补充说明：

- `initial_chat_history` 和 `memory_list` 只影响推理输入，不单独产出评测项。
- `history` 中的 `assistant` + `content.mode == "clarification"` 会决定 clarification 轮次数。
- `history` 中的 `assistant` + `content.mode == "execution"` 会在推理时被替换成模型预测结果。
- category 不是数据字段，而是由文件路径推导出来的，例如 `data/v5_no_entrance/simple/atom/clear/dataset.jsonl` 会映射为 `v5_no_entrance/simple/atom/clear`。

## Predictions 输出格式

`predictions.jsonl` 的单条记录当前长这样：

```json
{
  "uuid": "sample-uuid",
  "query_idx": 0,
  "predictions": {
    "labels": [{"did": "light-1", "attribute": "power", "value": "on"}],
    "conditions": [
      {
        "time_cron": "0 0 22 * * ? *",
        "state_expr": "device('light-1').power == 'off'"
      }
    ],
    "clarifications": ["你是指客厅主灯吗？"],
    "clarification_mode_ok": [true],
    "response": "客厅主灯已打开",
    "engine": {"home": {"name": "home", "rooms": [], "devices": []}},
    "token_usage": {
      "prompt_tokens": 2,
      "completion_tokens": 1,
      "total_tokens": 3,
      "reasoning_tokens": 0,
      "cached_tokens": 0,
      "llm_calls": 1
    }
  },
  "initial_query": "打开客厅灯",
  "history": [
    {"role": "assistant", "content": {"mode": "execution", "response": "客厅主灯已打开"}}
  ],
  "messages": [
    {
      "stage": "final",
      "order": 0,
      "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "打开客厅灯"}
      ]
    }
  ],
  "action_errors": []
}
```

说明：

- `messages` 是按 stage 记录的 prompt/transcript，便于排查推理问题。
- `action_errors` 记录动作仿真或工具执行失败。
- `clarification_mode_ok` 只在 `context` 模式下有意义，用于标记模型在 clarification 阶段是否正确输出了 `mode=clarification`。

## 结果文件

- `predictions.jsonl`
  - 推理输出，可用于之后离线评测。
- `eval_results.jsonl`
  - 每条样本的详细评测结果。
- `summary.json`
  - 汇总通过率、评测样本数、category 分层统计、平均 token usage。
- `judge_traces.jsonl`
  - LLM judge 的 prompt、输入、原始输出、解析结果，便于人工复核。

`eval_results.jsonl` 的核心字段：

```json
{
  "uuid": "sample-uuid",
  "query_idx": 0,
  "critic_pass": true,
  "ground_truth_critic_pass": true,
  "query_response_pass": true,
  "query_response_required": true,
  "conditions_pass": true,
  "conditions_required": true,
  "clarification_passes": [true],
  "clarifications_required": true,
  "overall_pass": true,
  "category": "v5_no_entrance/simple/atom/clear",
  "errors": [],
  "token_usage": {
    "prompt_tokens": 123.0,
    "completion_tokens": 45.0
  }
}
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 `.env`

```bash
DEFAULT_API_KEY=...
DEFAULT_MODEL_URL=...
DEFAULT_MODEL_NAME=...
DEFAULT_AIGC_USER=...
```

当前 CLI 的真实行为要注意两点：

- 推理阶段优先使用命令行参数 `--model-url`、`--model-name`、`--api-key`、`--aigc-user`，未显式传入时再回退到 `.env`。
- 只要不是 `--ground-truth-only`，当前实现都会要求 `.env` 中存在一套 judge LLM 配置；即使本次样本未必真的触发 query response / strict clarification judge，CLI 也会先做这层检查。

## 运行方式

### 1. 端到端推理 + 评测

```bash
python -m evaluator.cli \
  --data-files data/path/sample.jsonl \
  --inference \
  --predictions-out outputs/runX/predictions.jsonl \
  --results-out outputs/runX/eval_results.jsonl \
  --summary-out outputs/runX/summary.json \
  --judge-traces-out outputs/runX/judge_traces.jsonl
```

### 2. 用已有 predictions 直接评测

```bash
python -m evaluator.cli \
  --data-files data/path/sample.jsonl \
  --predictions-in outputs/runX/predictions.jsonl \
  --results-out outputs/runX/eval_results.jsonl \
  --summary-out outputs/runX/summary.json \
  --judge-traces-out outputs/runX/judge_traces.jsonl
```

### 3. 只校验 ground truth 与 critic 是否自洽

```bash
python -m evaluator.cli \
  --data-files data/path/sample.jsonl \
  --results-out outputs/runX/gt_eval.jsonl \
  --summary-out outputs/runX/gt_summary.json \
  --ground-truth-only
```

### 4. 使用共享输出目录

```bash
python -m evaluator.cli \
  --data-dir data/path\
  --out-dir outputs/runX \
  --inference
```

### 5. 使用 glob

`--data-files` 由程序内部展开 glob，不依赖 shell：

```bash
python -m evaluator.cli \
  --data-files "data/**/*.jsonl" \
  --results-out outputs/runX/eval_results.jsonl
```

## 常用 CLI 参数

- `--data-files`
  - 一个或多个 JSONL 文件，支持 glob。
- `--data-dir`
  - 递归扫描目录下所有 JSONL。
- `--default-engine-file`
  - 为缺失 `engine` 的样本补默认家庭环境。
- `--predictions-in`
  - 离线评测时读取已有预测。
- `--predictions-out`
  - 端到端推理时写出预测。
- `--out-dir`
  - 统一输出目录，自动拼出默认文件名。
- `--max-samples`
  - 调试时截断样本数。
- `--concurrency`
  - 推理和异步 judge 的并发数，默认 `20`。
- `--max-tool-calls`
  - tool-calling 最大轮数，默认 `10`。
- `--enable-thinking`
  - 打开模型 thinking。
- `--reasoning-effort low|medium|high`
  - GPT-5 系列 reasoning 等级。
- `--strict-clarification-judge`
  - 开启严格 clarification 内容评测。

## 模板文件

如果只想临时替换当前 run 的 assistant 模板，可以传：

```bash
--assistant-template path/to/custom_template.md
```

## 汇总到 CSV

```bash
python collect_to_csv.py run11 run12
```

行为：

- 会读取 `outputs/run11/summary.json`、`outputs/run12/summary.json`
- 输出到 `outputs/collected_summary.csv`
- 同时写 overall 和所有 category 行

也可以直接扫整个 `outputs`：

```bash
python collect_to_csv.py
```

指定输出路径：

```bash
python collect_to_csv.py run11 run12 -o outputs/custom_summary.csv
```
