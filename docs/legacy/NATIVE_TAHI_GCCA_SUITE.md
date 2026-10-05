# Native TAHI GCCA Suite & Trained Checkpoint Inventory

**Document Version:** 1.0.0  
**Date:** 2026-08-05  
**Location:** `src/tahi/native/` & `checkpoints/gcca/`

---

## 1. Executive Summary

TAHI contains its own complete, native, end-to-end **Gated Chunked Cross-Attention (GCCA)** suite in `src/tahi/native/`, complete with:
- **PyTorch GCCA Layer**: `src/tahi/native/gcca_layer.py`
- **HuggingFace Adapter Hooks**: `src/tahi/native/huggingface_adapter.py`
- **vLLM Integration**: `src/tahi/native/vllm_integration.py`
- **Graph Memory Tensor Builder**: `src/tahi/native/memory.py`
- **Training Pipeline**: `scripts/train_gcca.py`
- **Native Benchmark Suite**: `benchmarks/run_l3_native.py`
- **15 Trained Checkpoints**: `checkpoints/gcca/` (4.3 GB, Epochs 0 through 14)

No external imports from `maailma` are required.

---

## 2. Native GCCA Subsystem Inventory

### 2.1 `src/tahi/native/gcca_layer.py` (86 lines)
Implements `GatedChunkedCrossAttention`, applying:

$$\mathbf{H}_{\text{out}} = \mathbf{H} + \tanh(\alpha) \cdot \text{CrossAttention}(\text{LayerNorm}(\mathbf{H}), \mathbf{E}_{\text{memory}})$$

- **Zero-Disruption Init**: $\alpha = 0.0$ at step 0 guarantees bit-exact output logits compared to stock foundation LLM.
- **Param Overhead**: Borrowed $W_Q, W_O$ projections ensure $<2\%$ trainable parameter overhead.

### 2.2 `src/tahi/native/huggingface_adapter.py` (122 lines)
Implements `TahiNativeAdapter`, which:
- Freezes 100% of base model weights (`Qwen2.5`, `Llama-3.2`).
- Registers PyTorch forward hooks (`_register_hooks()`) on decoder layers (e.g. layers 0, 4, 8, 12...).
- Exposes `set_retrieved_memory(e_retrieved)` to update active graph memory tensors during generation.

### 2.3 `src/tahi/native/memory.py` (130 lines)
Implements `build_memory_tensor()`:
- Converts TAHI Property Graph nodes and edge tuples (`src`, `rel`, `dst`) into $[1, K, d_{\text{retriever}}]$ memory slot tensors.
- Includes `SubgraphRGATEncoder` for graph neural message passing over edge relations.

### 2.4 `checkpoints/gcca/` (15 Trained Checkpoints, 4.3 GB)
Located on disk in `checkpoints/gcca/`:
- `gcca_epoch0.pt` through `gcca_epoch14.pt` (297.5 MB per checkpoint).
- Trained using `scripts/train_gcca.py` with base model weights frozen.

### 2.5 `benchmarks/run_l3_native.py` (482 lines)
Full 4-arm native benchmark evaluating Level 3 native GCCA cross-attention against prompt RAG and base LLM floor.

---

## 3. How to Run Native TAHI GCCA

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from tahi.native.huggingface_adapter import TahiNativeAdapter
from tahi.native.memory import build_memory_from_vectors

# 1. Load frozen base model & tokenizer
base_model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")

# 2. Attach native TAHI GCCA adapter (interleave step = 4)
adapter = TahiNativeAdapter(base_model, d_retriever=768, interleave_step=4)

# 3. Load trained GCCA checkpoint from disk
checkpoint = torch.load("checkpoints/gcca/gcca_epoch14.pt", map_location="cpu")
adapter.gcca_layers.load_state_dict(checkpoint["gcca_state_dict"])

# 4. Set retrieved graph memory tensor [1, K, d_retriever]
graph_vectors = [[0.1] * 768, [0.2] * 768]  # Encoded graph nodes
memory_tensor = build_memory_from_vectors(graph_vectors)
adapter.set_retrieved_memory(memory_tensor)

# 5. Generate with native GCCA cross-attention (zero prompt window bloat!)
inputs = tokenizer("Question: What is the most common type of skin cancer?", return_tensors="pt")
outputs = adapter(**inputs, max_new_tokens=50)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```
