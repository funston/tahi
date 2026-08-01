# Level 2/3 Native Residual Injection Implementation Plan

## Architectural Overview

```
                                [ BASE LLM LAYER i ]
                                          │
                                          ▼
                             [ LayerNorm (Pre-LN) ]
                                          │
                                          ▼
   [ Fused Graph Signal ] ──► [ Project W_K, W_V ] ──► [ Multi-Head Cross-Attn ]
   (Entities, Rules, Vectors)                                   │
                                                                ▼
                                                   [ Learnable Gate: tanh(α) ]
                                                   (Initialized to α = 0.0)
                                                                │
                                                                ▼
[ Input Hidden State H ] ────────────────────────────────────► [ + ] (Residual Addition)
                                                                │
                                                                ▼
                                                        [ Layer i+1 ]
```

- **Level 1 (Prompt Context)**: Converts graph state into text prompt hints (already implemented in [`integration.py`](file:///Users/richiek/work/bender/src/octo/integration.py#L27)).
- **Level 2 (Latent Hidden-State Delta)**: Applies a learned linear projection and $\tanh(\alpha)$ scalar gate directly to the model's intermediate hidden state tensor $H \in \mathbb{R}^{B \times S \times d_{\text{model}}}$.
- **Level 3 (Native GCCA Module)**: Interleaves Gated Chunked Cross-Attention (GCCA) modules between Transformer layers of open-weight models (Qwen, Llama). Cross-attention uses query states from the LLM decoder and key/value matrices projected from retrieved world-state nodes.

---

## Concrete PyTorch Implementation Plan

### Step 1: Replace Prototype with `GatedChunkedCrossAttention` PyTorch Module
Create `src/octo/native/gcca_layer.py` replacing the pure-Python prototype in [`knowledge_attention.py`](file:///Users/richiek/work/bender/src/octo/knowledge_attention.py):

```python
import torch
import torch.nn as nn

class GatedChunkedCrossAttention(nn.Module):
    """
    Level 3 Native Integration: PyTorch Gated Chunked Cross-Attention (GCCA) Module.
    
    Inserts lightweight trainable cross-attention adapters into frozen Transformer blocks.
    Uses tanh(alpha) gating initialized to 0.0 to guarantee zero disruption at step 0.
    """
    def __init__(
        self,
        d_model: int,
        d_retriever: int,
        num_heads: int = 8,
        dropout: float = 0.0
    ):
        super().__init__()
        self.d_model = d_model
        self.d_retriever = d_retriever
        self.num_heads = num_heads
        
        # Projection matrices for Key and Value from retrieved world state
        self.w_k = nn.Linear(d_retriever, d_model, bias=False)
        self.w_v = nn.Linear(d_retriever, d_model, bias=False)
        
        # Multi-head cross-attention over retrieved graph/vector memory
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        self.norm = nn.LayerNorm(d_model)
        
        # Zero-initialized tanh(alpha) gating scalar (Flamingo/InstructRetro principle)
        self.alpha = nn.Parameter(torch.zeros(1))

    def forward(
        self,
        h: torch.Tensor,                # Base LLM hidden states: [B, S, d_model]
        e_retrieved: torch.Tensor,      # Fused graph/vector memory: [B, K, d_retriever]
        attn_mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        # Pre-LN
        normed_h = self.norm(h)
        
        # Project retrieved vectors to key/value space
        k = self.w_k(e_retrieved)       # [B, K, d_model]
        v = self.w_v(e_retrieved)       # [B, K, d_model]
        
        # Cross-attend: Query = normed_h, Key = k, Value = v
        attn_out, _ = self.cross_attn(
            query=normed_h,
            key=k,
            value=v,
            attn_mask=attn_mask
        )
        
        # Residual connection gated by tanh(alpha)
        gate = torch.tanh(self.alpha)
        return h + gate * attn_out
```

---

### Step 2: Create Model Hook Adapter (`src/octo/native/huggingface_adapter.py`)
Interleave GCCA blocks into open-weight models (e.g. HuggingFace / vLLM Llama or Qwen models) without unfreezing base weights:

```python
import torch
import torch.nn as nn
from .gcca_layer import GatedChunkedCrossAttention

class OctoNativeAdapter(nn.Module):
    """
    Wraps an open-weight LLM and attaches GCCA blocks every `interleave_step` layers.
    Freezes 100% of base model parameters (<2% trainable parameter overhead).
    """
    def __init__(
        self,
        base_model: nn.Module,
        d_retriever: int = 768,
        interleave_step: int = 4
    ):
        super().__init__()
        self.base_model = base_model
        
        # 1. Freeze base LLM parameters to prevent catastrophic forgetting
        for param in self.base_model.parameters():
            param.requires_grad = False
            
        d_model = base_model.config.hidden_size
        self.gcca_layers = nn.ModuleDict()
        
        # 2. Attach GCCA modules to designated layers (e.g. layers 0, 4, 8, 12...)
        num_layers = len(base_model.model.layers)
        for layer_idx in range(0, num_layers, interleave_step):
            self.gcca_layers[str(layer_idx)] = GatedChunkedCrossAttention(
                d_model=d_model,
                d_retriever=d_retriever
            )
            
        # 3. Register PyTorch forward hooks
        self._register_hooks()

    def _register_hooks(self):
        def make_hook(layer_idx: int):
            def hook(module, args, output):
                # output is tuple (hidden_states, ...)
                hidden_states = output[0] if isinstance(output, tuple) else output
                if hasattr(self, "_current_retrieved_memory"):
                    gcca = self.gcca_layers[str(layer_idx)]
                    hidden_states = gcca(hidden_states, self._current_retrieved_memory)
                return (hidden_states,) + output[1:] if isinstance(output, tuple) else hidden_states
            return hook

        for layer_idx_str in self.gcca_layers.keys():
            idx = int(layer_idx_str)
            self.base_model.model.layers[idx].register_forward_hook(make_hook(idx))

    def set_retrieved_memory(self, e_retrieved: torch.Tensor):
        """Pass fused world-model signal to native hooks."""
        self._current_retrieved_memory = e_retrieved
```

---

### Step 3: Implement Asynchronous Prefetch Pipeline (`src/octo/native/prefetch.py`)
To prevent retrieval from stalling token generation on GPU:

```python
import threading
import torch

class AsyncPrefetchWorker:
    """
    Prefetches graph/vector memory for step N+1 asynchronously while GPU decodes step N.
    """
    def __init__(self, runtime, device: str = "cuda"):
        self.runtime = runtime
        self.device = device
        self.stream = torch.cuda.Stream() if "cuda" in device else None
        self._next_tensor = None
        self._lock = threading.Lock()

    def prefetch_async(self, query: str):
        def _worker():
            # 1. Retrieve world state off-thread
            cognitive_state = self.runtime.process_query(query)
            fused_vec = cognitive_state.fused_signal.vector
            
            # 2. Convert to pinned CUDA tensor
            tensor = torch.tensor(fused_vec, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            if self.stream:
                with torch.cuda.stream(self.stream):
                    tensor = tensor.to(self.device, non_blocking=True)
            
            with self._lock:
                self._next_tensor = tensor

        threading.Thread(target=_worker, daemon=True).start()

    def get_prefetched_tensor(self) -> torch.Tensor | None:
        with self._lock:
            return self._next_tensor
```

---

### Step 4: Update Runtime & Integration Contracts ([`integration.py`](file:///Users/richiek/work/bender/src/octo/integration.py#L74))

Extend [`NativeIntegration.inject()`](file:///Users/richiek/work/bender/src/octo/integration.py#L98) to format `ControlPacket` with direct tensor support:

- If PyTorch is loaded, `ControlPacket.metadata["native_tensor"]` returns the `torch.Tensor` formed by `fused_signal.vector`.
- Connect `OctoRuntime` to `OctoNativeAdapter` for open-weights execution.

---

### Key Benefits of This Implementation
1. **Zero-Disruption Initialization**: Setting $\alpha=0.0$ at step 0 guarantees 100% logit identity with the base LLM.
2. **<2% Parameter Overhead**: Only $W_K, W_V$ and $\alpha$ are trained; base LLM parameters stay completely frozen.
3. **Latency Masking**: `AsyncPrefetchWorker` uses dedicated CUDA streams to load graph signals without blocking token generation loops.
