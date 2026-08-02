"""
vLLM Native Worker & Asynchronous Prefetch Integration for OCTO Level 3 Residual Injection.

Provides:
- AsyncPrefetchWorker: Off-thread memory prefetching via CUDA Streams to prevent decoding stalls.
- OctoVLLMAdapter: Connects vLLM's intermediate model forward passes to OctoNativeAdapter & GCCA blocks.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, Sequence

import torch
import torch.nn as nn

from .gcca_layer import GatedChunkedCrossAttention
from .huggingface_adapter import OctoNativeAdapter

logger = logging.getLogger(__name__)


class AsyncPrefetchWorker:
    """
    Prefetches graph/vector world-state memory for step N+1 asynchronously while GPU decodes step N.
    Uses dedicated CUDA stream for asynchronous H2D memory transfer.
    """

    def __init__(self, device: str | torch.device = "cuda"):
        self.device = torch.device(device) if isinstance(device, str) else device
        self.use_cuda = self.device.type == "cuda" and torch.cuda.is_available()
        self.stream = torch.cuda.Stream(device=self.device) if self.use_cuda else None
        self._next_tensor: torch.Tensor | None = None
        self._lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None

    def prefetch_async(
        self,
        query: str,
        runtime: Any,
        callback: Optional[Callable[[torch.Tensor], None]] = None,
    ) -> None:
        """
        Asynchronously processes query via runtime and stages memory tensor on GPU stream.
        """
        def _worker():
            try:
                # 1. Retrieve world state off-thread
                cognitive_state = runtime.process_query(query)
                fused_vec = getattr(cognitive_state.fused_signal, "vector", None)
                if fused_vec is None:
                    if hasattr(cognitive_state, "fused_vector"):
                        fused_vec = cognitive_state.fused_vector
                    else:
                        fused_vec = [0.0] * 768

                # 2. Convert to PyTorch tensor [1, 1, d_retriever]
                tensor = torch.tensor(fused_vec, dtype=torch.float32).unsqueeze(0)
                if tensor.dim() == 2:
                    tensor = tensor.unsqueeze(1)  # [1, 1, d_retriever]

                # 3. Asynchronous non-blocking transfer to target GPU device
                if self.use_cuda and self.stream:
                    with torch.cuda.stream(self.stream):
                        tensor = tensor.to(self.device, non_blocking=True)
                    torch.cuda.current_stream(self.device).wait_stream(self.stream)

                with self._lock:
                    self._next_tensor = tensor

                if callback is not None:
                    callback(tensor)

            except Exception as e:
                logger.error(f"Error in AsyncPrefetchWorker: {e}", exc_info=True)

        self._worker_thread = threading.Thread(target=_worker, daemon=True)
        self._worker_thread.start()

    def get_prefetched_tensor(self, wait: bool = False) -> torch.Tensor | None:
        """Retrieve pre-fetched memory tensor."""
        if wait and self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        with self._lock:
            return self._next_tensor

    def clear(self) -> None:
        """Clear active prefetched tensor."""
        with self._lock:
            self._next_tensor = None


class OctoVLLMAdapter(nn.Module):
    """
    Adapter interfacing vLLM ModelExecutor / HuggingFace model with OCTO Native GCCA modules.
    Wraps base PyTorch / vLLM execution graphs and orchestrates AsyncPrefetchWorker memory streaming.
    """

    def __init__(
        self,
        base_model: nn.Module,
        d_retriever: int = 768,
        interleave_step: int = 4,
        num_heads: int = 8,
        device: str | torch.device = "cuda",
    ):
        super().__init__()
        self.device = torch.device(device) if isinstance(device, str) else device
        self.adapter = OctoNativeAdapter(
            base_model=base_model,
            d_retriever=d_retriever,
            interleave_step=interleave_step,
            num_heads=num_heads,
        )
        if self.device.type == "cuda" and torch.cuda.is_available():
            self.adapter.to(self.device)
            self.to(self.device)
        self.prefetch_worker = AsyncPrefetchWorker(device=self.device)


    def prefetch_next(self, query: str, runtime: Any) -> None:
        """Trigger async memory prefetching for upcoming query."""
        def _on_prefetched(tensor: torch.Tensor):
            self.adapter.set_retrieved_memory(tensor)

        self.prefetch_worker.prefetch_async(query, runtime, callback=_on_prefetched)

    def set_retrieved_memory(self, memory_tensor: torch.Tensor | Sequence[float] | None) -> None:
        """Directly set active memory tensor for forward pass GCCA hooks."""
        if memory_tensor is None:
            self.adapter.clear_retrieved_memory()
            return

        if not isinstance(memory_tensor, torch.Tensor):
            tensor = torch.tensor(memory_tensor, dtype=torch.float32)
        else:
            tensor = memory_tensor

        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0).unsqueeze(0)  # [1, 1, d_retriever]
        elif tensor.dim() == 2:
            tensor = tensor.unsqueeze(1)  # [B, 1, d_retriever]

        self.adapter.set_retrieved_memory(tensor)

    def forward(self, *args, **kwargs):
        """Execute forward pass through adapter."""
        # If prefetched tensor ready and not yet set, update adapter
        prefetched = self.prefetch_worker.get_prefetched_tensor()
        if prefetched is not None and self.adapter._current_retrieved_memory is None:
            self.adapter.set_retrieved_memory(prefetched)

        return self.adapter(*args, **kwargs)

    def clear(self) -> None:
        """Clear memory and reset hooks state."""
        self.adapter.clear_retrieved_memory()
        self.prefetch_worker.clear()
