"""
Unit tests for vLLM Native Worker Integration & AsyncPrefetchWorker (src/octo/native/vllm_integration.py).

Verifies:
1. AsyncPrefetchWorker off-thread retrieval and CUDA/CPU tensor staging.
2. OctoVLLMAdapter memory state setting and forward pass hook delegation.
"""

from __future__ import annotations

import time
import pytest
import torch
import torch.nn as nn

from octo.native import AsyncPrefetchWorker, OctoVLLMAdapter


class DummyCognitiveState:
    def __init__(self, vector: list[float]):
        self.fused_signal = type("Signal", (), {"vector": vector})()
        self.fused_vector = vector


class DummyRuntime:
    def __init__(self, vector_dim: int = 64):
        self.vector_dim = vector_dim

    def process_query(self, query: str) -> DummyCognitiveState:
        # Simulate slight processing delay
        time.sleep(0.01)
        return DummyCognitiveState([0.5] * self.vector_dim)


class DummyTransformerLayer(nn.Module):
    def __init__(self, d_model: int):
        super().__init__()
        self.linear = nn.Linear(d_model, d_model)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor]:
        return (self.linear(x),)


class SubModel(nn.Module):
    def __init__(self, num_layers: int, d_model: int):
        super().__init__()
        self.layers = nn.ModuleList([DummyTransformerLayer(d_model) for _ in range(num_layers)])


class DummyModel(nn.Module):
    def __init__(self, num_layers: int = 4, d_model: int = 64):
        super().__init__()
        self.config = type("Config", (), {"hidden_size": d_model})()
        self.model = SubModel(num_layers=num_layers, d_model=d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = x
        for layer in self.model.layers:
            out = layer(out)[0]
        return out



def test_async_prefetch_worker():
    """Verify AsyncPrefetchWorker prefetches tensor off-thread."""
    runtime = DummyRuntime(vector_dim=32)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    worker = AsyncPrefetchWorker(device=device)

    worker.prefetch_async("test query", runtime)

    # Retrieve prefetched tensor (wait=True)
    tensor = worker.get_prefetched_tensor(wait=True)

    assert tensor is not None
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (1, 1, 32)
    assert tensor[0, 0, 0].item() == pytest.approx(0.5)

    worker.clear()
    assert worker.get_prefetched_tensor() is None


def test_octo_vllm_adapter_memory_flow():
    """Verify OctoVLLMAdapter integrates prefetch worker and injects memory into GCCA layers."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base_model = DummyModel(num_layers=4, d_model=64)
    if device == "cuda":
        base_model = base_model.cuda()
    adapter = OctoVLLMAdapter(base_model, d_retriever=32, interleave_step=2, device=device)

    runtime = DummyRuntime(vector_dim=32)

    # Enable GCCA alpha for testing output change
    for gcca in adapter.adapter.gcca_layers.values():
        with torch.no_grad():
            gcca.alpha.copy_(torch.tensor([1.0]))

    x = torch.randn(1, 4, 64)
    if device == "cuda":
        x = x.cuda()


    # 1. Forward pass without memory active
    out_baseline = adapter(x)

    # 2. Prefetch next query and wait
    adapter.prefetch_next("query 1", runtime)
    time.sleep(0.05)

    out_with_prefetched = adapter(x)

    assert out_baseline.shape == x.shape
    assert out_with_prefetched.shape == x.shape
    assert not torch.allclose(out_baseline, out_with_prefetched)

    # Cleanup
    adapter.clear()
