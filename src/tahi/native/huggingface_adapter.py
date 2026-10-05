"""
PyTorch HuggingFace Model Adapter for TAHI Native Integration.

Wraps pre-trained open-weight Transformer models (e.g. Qwen2.5, Llama 3) and interleaves
Gated Chunked Cross-Attention (GCCA) modules across Transformer layers using PyTorch forward hooks.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from .chunking import ChunkSpec
from .gcca_layer import DEFAULT_CHUNK_SIZE, GatedChunkedCrossAttention


class TahiNativeAdapter(nn.Module):
    """
    Wraps an open-weight Transformer model and attaches GCCA blocks every `interleave_step` layers.
    Freezes 100% of base model parameters (<2% trainable parameter overhead).
    """

    def __init__(
        self,
        base_model: nn.Module,
        d_retriever: int = 768,
        interleave_step: int = 4,
        num_heads: int = 8,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        super().__init__()
        self.base_model = base_model
        self.d_retriever = d_retriever
        self.interleave_step = interleave_step
        self.chunk_size = chunk_size

        # 1. Freeze base LLM parameters to prevent catastrophic forgetting
        for param in self.base_model.parameters():
            param.requires_grad = False

        # Extract hidden dimension from model config
        config = getattr(base_model, "config", None)
        d_model = getattr(config, "hidden_size", None) if config else 768

        self.gcca_layers = nn.ModuleDict()

        # Get Transformer layers list (handles common HuggingFace model structures)
        layers = self._get_model_layers(base_model)
        num_layers = len(layers)

        # 2. Attach GCCA modules to designated layers (e.g. layers 0, 4, 8, 12...)
        for layer_idx in range(0, num_layers, interleave_step):
            self.gcca_layers[str(layer_idx)] = GatedChunkedCrossAttention(
                d_model=d_model,
                d_retriever=d_retriever,
                num_heads=num_heads,
                chunk_size=chunk_size,
            )

        self._hooks: list[torch.utils.hooks.RemovableHandle] = []
        self._current_retrieved_memory: torch.Tensor | None = None
        self._current_plan: list[ChunkSpec] | None = None
        self._register_hooks()

    @staticmethod
    def _get_model_layers(base_model: nn.Module) -> nn.ModuleList:
        """Extract the module list of Transformer decoder layers from common architectures."""
        if hasattr(base_model, "model") and hasattr(base_model.model, "layers"):
            return base_model.model.layers
        if hasattr(base_model, "transformer") and hasattr(base_model.transformer, "h"):
            return base_model.transformer.h
        if hasattr(base_model, "layers"):
            return base_model.layers
        raise ValueError("Could not automatically locate Transformer layers list in base_model.")

    def _register_hooks(self) -> None:
        """Register forward hooks on target Transformer layers."""
        layers = self._get_model_layers(self.base_model)

        def make_hook(layer_idx_str: str):
            def hook(module: nn.Module, args: tuple, output: torch.Tensor | tuple) -> torch.Tensor | tuple:
                if self._current_retrieved_memory is None:
                    return output

                hidden_states = output[0] if isinstance(output, tuple) else output
                gcca = self.gcca_layers[layer_idx_str]

                # Match batch dimension and device if needed
                retrieved = self._current_retrieved_memory
                if retrieved.device != hidden_states.device:
                    retrieved = retrieved.to(hidden_states.device)
                if retrieved.dim() == 2:
                    # [K, d] -> one static bank
                    retrieved = retrieved.unsqueeze(0)
                if retrieved.size(0) != hidden_states.size(0):
                    # 3D static [B,K,d] or 4D chunked [B,L,K,d]; broadcast batch only.
                    retrieved = retrieved.expand(
                        hidden_states.size(0), *([-1] * (retrieved.dim() - 1)))

                modified_hidden = gcca(hidden_states, retrieved,
                                      plan=self._current_plan)

                if isinstance(output, tuple):
                    return (modified_hidden,) + output[1:]
                return modified_hidden

            return hook

        for layer_idx_str in self.gcca_layers.keys():
            idx = int(layer_idx_str)
            handle = layers[idx].register_forward_hook(make_hook(layer_idx_str))
            self._hooks.append(handle)

    def set_retrieved_memory(
        self,
        e_retrieved: torch.Tensor | None,
        plan: list[ChunkSpec] | None = None,
    ) -> None:
        """Install the bank(s) the hooks cross-attend, and the window plan for them.

        `plan` is required whenever `e_retrieved` is 4D and the hidden states do
        not start at absolute position 0 -- i.e. during incremental decode. Without
        it the layer derives a plan from the tensor length, which for a one-token
        forward describes position 0 rather than the real position, and every span
        falls outside the window: cross-attention silently does nothing. MAAILMA
        measured that exact bug at EM 0.250 against 1.000 for the same checkpoint.
        """
        self._current_retrieved_memory = e_retrieved
        self._current_plan = plan

    def clear_retrieved_memory(self) -> None:
        """Clear active memory signal."""
        self._current_retrieved_memory = None
        self._current_plan = None

    @property
    def active_memory_slots(self) -> int:
        """Slots resident right now. Must not grow with sequence length -- the O(1)
        claim is checked against this, not against a comment."""
        m = self._current_retrieved_memory
        return 0 if m is None else int(m.shape[-2])

    @property
    def active_memory_elements(self) -> int:
        m = self._current_retrieved_memory
        return 0 if m is None else int(m.numel())

    def contributions(self) -> dict[str, float | None]:
        """Per-block `||tanh(alpha) * CCA(H)|| / ||H||` from the last forward.

        The gate-collapse readout. `alpha` alone cannot distinguish a closed gate
        from an open gate attending useless memory; this can.
        """
        return {k: g.last_contribution for k, g in self.gcca_layers.items()}

    def alphas(self) -> dict[str, float]:
        return {k: float(g.alpha.detach().item()) for k, g in self.gcca_layers.items()}

    @torch.no_grad()
    def set_identity_mode(self, mode: str, alpha: float = 0.3) -> None:
        """Apply `GatedChunkedCrossAttention.set_identity_mode` to every block."""
        for g in self.gcca_layers.values():
            g.set_identity_mode(mode, alpha=alpha)

    def forward(self, *args, **kwargs):
        """Forward pass delegated directly to base_model (hooks apply automatically)."""
        return self.base_model(*args, **kwargs)

    def remove_hooks(self) -> None:
        """Clean up forward hooks."""
        for handle in self._hooks:
            handle.remove()
        self._hooks.clear()
