# AGY Antigravity Agent Handover Notes (DGX Workstation Transition)

**Date**: 2026-08-01  
**Target Environment**: DGX Workstation CLI (`/raid/...`)  
**Objective**: Transition from local Mac PyTorch development (Phase 1 & 2) to DGX multi-GPU vLLM native integration and 4-arm benchmark evaluation (Phase 3 & 4).

---

## 1. Work Completed on Local Mac (Phase 1 & Phase 2)

- **Architecture Review & Level 2/3 Roadmap**:
  - Saved [`AGY_ARCH_REVIEW.md`](file://AGY_ARCH_REVIEW.md) comparing OCTO to out-of-core RETRO-v2 (`RAG with ANN.txt`).
  - Saved [`AGY_LEVEL_2_IMPLEMENTATION.md`](file://AGY_LEVEL_2_IMPLEMENTATION.md) detailing the PyTorch GCCA module design.

- **Native PyTorch Modules Implemented (`src/octo/native/`)**:
  - [`src/octo/native/gcca_layer.py`](file://src/octo/native/gcca_layer.py): `GatedChunkedCrossAttention` PyTorch `nn.Module` with zero-initialized $\tanh(\alpha)$ scalar gating ($O(1)$ memory bound, Flamingo/InstructRetro principle).
  - [`src/octo/native/huggingface_adapter.py`](file://src/octo/native/huggingface_adapter.py): `OctoNativeAdapter` wrapping Transformer models (Qwen, Llama), freezing 100% of base model parameters (<2% parameter overhead), and registering forward hooks every $N$ layers.

- **Unit Test Verification**:
  - [`tests/test_native_gcca.py`](file://tests/test_native_gcca.py): Unit test suite verifying zero-disruption at initialization ($\alpha=0.0$), gated residual injection ($\alpha=1.0$), shape preservation, parameter freezing, and hook handle cleanup.
  - **Full PyTorch Test Suite Status**: **169 / 169 tests passed** (`python -m pytest tests/`).

---

## 2. Immediate Directives for the DGX AGY Agent (Phase 3 & Phase 4)

When starting the new AGY session in the CLI on your DGX workstation, instruct the agent to execute the following steps:

### Step 1: Environment & GPU Verification
```bash
source .venv/bin/activate  # or activate your virtual environment
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPUs: {torch.cuda.device_count()}')"
python -m pytest tests/test_native_gcca.py -s -v
```

### Step 2: Serve Open-Weight Model via vLLM
Following [`docs/DGX_VLLM_RUNBOOK.md`](file://docs/DGX_VLLM_RUNBOOK.md):
```bash
# Recommended: Qwen2.5-72B-Instruct-AWQ on 128GB GPU
scripts/start_vllm_server.sh \
  --model Qwen/Qwen2.5-72B-Instruct-AWQ \
  --port 8000 \
  --quantization awq \
  --max-model-len 8192
```

### Step 3: Implement vLLM Native Worker Integration (`src/octo/native/vllm_integration.py`)
- Implement `vllm_integration.py` to connect vLLM's `ModelExecutor` layer forward passes to `OctoNativeAdapter`.
- Wire `AsyncPrefetchWorker` using `torch.cuda.Stream` to load memory tensors off-thread without stalling token decoding.

### Step 4: Run 4-Arm Benchmark Protocol
Execute evaluations across all 4 arms:
1. **Base LLM** (Zero-retrieval)
2. **Standard RAG Baseline** (Dense vector similarity search, no graph)
3. **OCTO Level 1** (Black-box prompt context hints)
4. **OCTO Level 3 Native GCCA** (Latent cross-attention residual injection)

Evaluate across:
- **Constraint Violation Rate**: Schema invariants and rule compliance.
- **Distractor Rejection**: RGB benchmark protocol with 20%–50% hard-negative noise.
- **Performance**: Time-To-First-Token (TTFT), Tokens-Per-Second (TPS), and peak VRAM memory.

---

## 3. Reference Files
- [`AGY_ARCH_REVIEW.md`](file://AGY_ARCH_REVIEW.md)
- [`AGY_LEVEL_2_IMPLEMENTATION.md`](file://AGY_LEVEL_2_IMPLEMENTATION.md)
- [`docs/DGX_VLLM_RUNBOOK.md`](file://docs/DGX_VLLM_RUNBOOK.md)
- [`docs/EVAL_RESULTS.md`](file://docs/EVAL_RESULTS.md)
- [`src/octo/native/gcca_layer.py`](file://src/octo/native/gcca_layer.py)
- [`src/octo/native/huggingface_adapter.py`](file://src/octo/native/huggingface_adapter.py)
- [`tests/test_native_gcca.py`](file://tests/test_native_gcca.py)
