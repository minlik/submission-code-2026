#!/usr/bin/env bash

MODEL_URL=""
API_KEY=""
MODEL_NAME=""


AIGC_USER=""
TEMPERATURE="0.7"
REASONING_EFFORT="high"
INFERENCE_MODE="tool"

ENABLE_THINKING="false"

ENABLE_THINKING_ARG=""
if [[ "${ENABLE_THINKING}" == "true" ]]; then
  ENABLE_THINKING_ARG="--enable-thinking"
fi

DEFAULT_ENGINE_FILE_ARG=""
ENGINE_FILE="${ENGINE_FILE:-data/complex/engine.json}"
if [[ -n "${ENGINE_FILE}" ]]; then
  DEFAULT_ENGINE_FILE_ARG="--default-engine-file ${ENGINE_FILE}"
fi

DATA_DIR="data/simple/atom/clear"
OUT_DIR="outputs/test"
ENV_PATH=".env"
CONCURRENCY="20"
MAX_SAMPLES="0"
MAX_TOOL_CALLS="10"

python -m evaluator.cli \
  --data-dir "${DATA_DIR}" \
  --out-dir "${OUT_DIR}" \
  --inference \
  --inference-mode "${INFERENCE_MODE}" \
  --assistant-template assistant_tool_detail.md \
  --env-path "${ENV_PATH}" \
  --model-url "${MODEL_URL}" \
  --api-key "${API_KEY}" \
  --model-name "${MODEL_NAME}" \
  --aigc-user "${AIGC_USER}" \
  --temperature "${TEMPERATURE}" \
  --reasoning-effort "${REASONING_EFFORT}" \
  --concurrency "${CONCURRENCY}" \
  --max-samples "${MAX_SAMPLES}" \
  --max-tool-calls "${MAX_TOOL_CALLS}" \
  ${DEFAULT_ENGINE_FILE_ARG} \
  ${ENABLE_THINKING_ARG}