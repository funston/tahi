"""
Unit tests for PyTorch GCCA Native Residual Injection modules (src/tahi/native/).

Verifies:
1. Zero-disruption property (tanh(alpha) = 0 output logits are identical to base hidden states).
2. Tensor shape correctness during forward pass.
3. HuggingFace model hook adapter layer interleaving and residual modification.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from tahi.native import GatedChunkedCrossAttention, TahiNativeAdapter


def test_gcca_zero_disruption_at_initialization():
    """At step 0 (alpha=0.0), GCCA output must match input hidden states exactly."""
    b, s, d_model, d_retriever = 2, 8, 64, 32
    gcca = GatedChunkedCrossAttention(d_model=d_model, d_retriever=d_retriever)

    h = torch.randn(b, s, d_model)
    e_retrieved = torch.randn(b, 4, d_retriever)

    out = gcca(h, e_retrieved)

    # With alpha=0.0, output must be mathematically identical to h
    assert torch.allclose(out, h, atol=1e-6)


def test_gcca_gated_residual_injection():
    """When alpha != 0, GCCA modifies hidden states via cross-attention residual."""
    b, s, d_model, d_retriever = 2, 8, 64, 32
    gcca = GatedChunkedCrossAttention(d_model=d_model, d_retriever=d_retriever)

    # Set alpha to non-zero value
    with torch.no_grad():
        gcca.alpha.copy_(torch.tensor([1.0]))

    h = torch.randn(b, s, d_model)
    e_retrieved = torch.randn(b, 4, d_retriever)

    out = gcca(h, e_retrieved)

    # Output shape must be preserved
    assert out.shape == h.shape
    # Output should differ from input
    assert not torch.allclose(out, h)


class DummyTransformerLayer(nn.Module):
    def __init__(self, d_model: int):
        super().__init__()
        self.linear = nn.Linear(d_model, d_model)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor]:
        return (self.linear(x),)


class DummyModel(nn.Module):
    def __init__(self, num_layers: int = 8, d_model: int = 64):
        super().__init__()
        self.config = type("Config", (), {"hidden_size": d_model})()
        self.model = type("SubModel", (), {
            "layers": nn.ModuleList([DummyTransformerLayer(d_model) for _ in range(num_layers)])
        })()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = x
        for layer in self.model.layers:
            out = layer(out)[0]
        return out


def test_tahi_native_adapter_interleaving_and_hooks():
    """TahiNativeAdapter should freeze base model parameters and attach GCCA hooks."""
    base_model = DummyModel(num_layers=8, d_model=64)
    adapter = TahiNativeAdapter(base_model, d_retriever=32, interleave_step=4)

    # Check parameter freezing (<2% parameters trainable)
    trainable_params = [p for p in adapter.parameters() if p.requires_grad]
    base_params = [p for p in base_model.parameters()]

    assert all(not p.requires_grad for p in base_params)
    assert len(trainable_params) > 0  # GCCA parameters are trainable

    # Verify GCCA layers attached to layer 0 and layer 4
    assert "0" in adapter.gcca_layers
    assert "4" in adapter.gcca_layers
    assert "2" not in adapter.gcca_layers

    x = torch.randn(2, 4, 64)
    memory = torch.randn(2, 3, 32)

    # Verify that setting alpha > 0 makes memory injection modify the output tensor
    for gcca in adapter.gcca_layers.values():
        with torch.no_grad():
            gcca.alpha.copy_(torch.tensor([1.0]))

    adapter.set_retrieved_memory(memory)
    out_with_memory_active = adapter(x)

    adapter.clear_retrieved_memory()
    out_without_memory_active = adapter(x)

    assert out_with_memory_active.shape == x.shape
    assert out_without_memory_active.shape == x.shape
    assert not torch.allclose(out_with_memory_active, out_without_memory_active)

    # Test remove_hooks cleanup
    adapter.remove_hooks()
    assert len(adapter._hooks) == 0
