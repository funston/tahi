"""
PyTorch HuggingFace Model Adapter for OCTO Native Integration.

Wraps pre-trained open-weight Transformer models (e.g. Qwen2.5, Llama 3) and interleaves
Gated Chunked Cross-Attention (GCCA) modules across Transformer layers using PyTorch forward hooks.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from .gcca_layer import GatedChunkedCrossAttention


class OctoNativeAdapter(nn.Module):
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
    ):
        super().__init__()
        self.base_model = base_model
        self.d_retriever = d_retriever
        self.interleave_step = interleave_step

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
            )

        self._hooks: list[torch.utils.hooks.RemovableHandle] = []
        self._current_retrieved_memory: torch.Tensor | None = None
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

                # Match batch dimension if needed
                retrieved = self._current_retrieved_memory
                if retrieved.dim() == 2:
                    retrieved = retrieved.unsqueeze(0)
                if retrieved.size(0) != hidden_states.size(0):
                    retrieved = retrieved.expand(hidden_states.size(0), -1, -1)

                modified_hidden = gcca(hidden_states, retrieved)

                if isinstance(output, tuple):
                    return (modified_hidden,) + output[1:]
                return modified_hidden

            return hook

        for layer_idx_str in self.gcca_layers.keys():
            idx = int(layer_idx_str)
            handle = layers[idx].register_forward_hook(make_hook(layer_idx_str))
            self._hooks.append(handle)

    def set_retrieved_memory(self, e_retrieved: torch.Tensor | None) -> None:
        """Set the current active retrieved memory tensor for forward pass hooks."""
        self._current_retrieved_memory = e_retrieved

    def clear_retrieved_memory(self) -> None:
        """Clear active memory signal."""
        self._current_retrieved_memory = None

    def forward(self, *args, **kwargs):
        """Forward pass delegated directly to base_model (hooks apply automatically)."""
        return self.base_model(*args, **kwargs)

    def remove_hooks(self) -> None:
        """Clean up forward hooks."""
        for handle in self._hooks:
            handle.remove()
        self._hooks.clear()
