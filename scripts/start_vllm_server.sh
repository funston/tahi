#!/usr/bin/env bash
# Start a vLLM OpenAI-compatible server for OCTO coprocessors.
#
# Usage:
#   scripts/start_vllm_server.sh --model Qwen/Qwen2.5-32B-Instruct --port 8000
#   scripts/start_vllm_server.sh --model Qwen/Qwen2.5-72B-Instruct-AWQ --quantization awq --port 8000

set -euo pipefail

MODEL=""
PORT=8000
QUANTIZATION=""
MAX_MODEL_LEN=8192
TP_SIZE=1
ATTN_BACKEND=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --model)
      MODEL="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --quantization)
      QUANTIZATION="$2"
      shift 2
      ;;
    --max-model-len)
      MAX_MODEL_LEN="$2"
      shift 2
      ;;
    --tensor-parallel-size)
      TP_SIZE="$2"
      shift 2
      ;;
    --attention-backend)
      ATTN_BACKEND="$2"
      shift 2
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$MODEL" ]]; then
  echo "Error: --model is required" >&2
  echo "Example: scripts/start_vllm_server.sh --model Qwen/Qwen2.5-32B-Instruct" >&2
  exit 1
fi

if [[ -n "$QUANTIZATION" ]]; then
  EXTRA_ARGS+=("--quantization" "$QUANTIZATION")
fi

# Common workarounds for vLLM v1 engine / flashinfer / attention backend issues.
# vLLM v1 (default in 0.6.4+) is fast but crashy on many DGX configs; force v0.
export VLLM_USE_V1=${VLLM_USE_V1:-0}
export FLASHINFER_DISABLE_VERSION_CHECK=${FLASHINFER_DISABLE_VERSION_CHECK:-1}
if [[ -n "$ATTN_BACKEND" ]]; then
  export VLLM_ATTENTION_BACKEND="$ATTN_BACKEND"
fi

set -x
python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --tensor-parallel-size "$TP_SIZE" \
  --max-model-len "$MAX_MODEL_LEN" \
  --port "$PORT" \
  "${EXTRA_ARGS[@]}"
