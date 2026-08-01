# DGX vLLM Runbook: Self-Hosted Inference for OCTO

This guide shows how to serve open-weight models on your DGX with vLLM so OCTO
coprocessors can query them instead of paying per-token to Claude/OpenAI.

## Why vLLM

- **No per-token API costs** after model download.
- **OpenAI-compatible API** — no code changes in OCTO evals.
- **128 GB GPU fits strong models**: Qwen2.5-32B FP16, Qwen2.5-72B-AWQ, Llama-3.1-70B-AWQ, Mixtral 8x7B.
- **Keeps data on-premise** — critical for legal, financial, and law-enforcement use cases.

## Hardware assumptions

- DGX with at least one 128 GB GPU (e.g., A100 80GB x2, H100 80GB x2).
- CUDA 12.x
- ~200 GB free disk space for model weights.
- Network access to HuggingFace or a local cache mirror.

## Step 1: Environment setup

SSH into the DGX and create an environment:

```bash
export OCTO_DGX_ROOT=/raid/your-user/octo-dgx
mkdir -p $OCTO_DGX_ROOT/{models,logs,scripts}
cd $OCTO_DGX_ROOT

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# Install PyTorch for your CUDA version (example: CUDA 12.1)
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121

# Install vLLM
pip install vllm==0.6.4.post1
```

Verify GPUs:

```bash
python - <<'PY'
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU count: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
PY
```

## Step 2: Download a model

Recommended models for 128 GB GPU:

| Model | Precision | VRAM | Command |
|---|---:|---:|---|
| Qwen2.5-32B-Instruct | FP16 | ~64 GB | default |
| Qwen2.5-72B-Instruct-AWQ | INT4 | ~40 GB | `--quantization awq` |
| Llama-3.1-70B-Instruct-AWQ | INT4 | ~40 GB | `--quantization awq` |
| Mixtral-8x7B-Instruct-v0.1 | FP16 | ~96 GB | default |

Example: download Qwen2.5-32B-Instruct.

```bash
export HF_HOME=$OCTO_DGX_ROOT/models/hf-cache
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen2.5-32B-Instruct", local_dir_use_symlinks=False)
PY
```

For AWQ models you will also need `autoawq`:

```bash
pip install autoawq
```

## Step 3: Start the vLLM server

Use the included helper script:

```bash
# FP16 Qwen2.5-32B on a single 128GB GPU
scripts/start_vllm_server.sh \
  --model Qwen/Qwen2.5-32B-Instruct \
  --port 8000 \
  --max-model-len 8192

# AWQ Qwen2.5-72B on a single 128GB GPU
scripts/start_vllm_server.sh \
  --model Qwen/Qwen2.5-72B-Instruct-AWQ \
  --port 8000 \
  --quantization awq \
  --max-model-len 8192
```

Or start manually:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-32B-Instruct \
  --tensor-parallel-size 1 \
  --max-model-len 8192 \
  --port 8000
```

Test the server:

```bash
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-32B-Instruct",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

## Step 4: Point OCTO at vLLM

From your local machine (or the DGX itself):

```bash
export OCTO_LLM_PROVIDER=vllm
export VLLM_BASE_URL=http://your-dgx-ip:8000/v1
export OCTO_LLM_MODEL=Qwen/Qwen2.5-32B-Instruct

# No API key needed for local vLLM, but the OpenAI client expects a non-empty string
export VLLM_API_KEY=not-needed

python examples/run_dea_eval.py
python examples/run_legal_eval.py
```

## Step 5: Optional — run vLLM as a persistent service

Use `systemd` or `tmux`/`screen` to keep the server alive.

```bash
tmux new-session -d -s vllm \
  "python -m vllm.entrypoints.openai.api_server \
     --model Qwen/Qwen2.5-32B-Instruct \
     --max-model-len 8192 \
     --port 8000"
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `CUDA out of memory` | Use AWQ/4-bit quantization or a smaller model. |
| `The model is too large for the GPU` | Enable tensor parallelism: `--tensor-parallel-size 2`. |
| Slow first request | vLLM is compiling CUDA graphs; subsequent requests are fast. |
| OpenAI client 401 | Set `VLLM_API_KEY=not-needed` (vLLM ignores it by default). |

## Cost comparison (rough)

| Approach | Upfront cost | Per 1M tokens | Notes |
|---|---:|---:|---|
| Claude Opus API | $0 | ~$15 | Pay per token; data leaves premises. |
| GPT-4o API | $0 | ~$2.50 | Pay per token; data leaves premises. |
| Qwen2.5-32B on DGX | GPU capital | ~$0 | One-time hardware; no usage meter. |
| Qwen2.5-72B-AWQ on DGX | GPU capital | ~$0 | Best quality on 128GB GPU. |

For high-volume evals and enterprise deployments, self-hosting breaks even quickly.
