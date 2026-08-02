"""
Native integration modules for OCTO (Level 2/3 latent & cross-attention residual injection).
"""

from .gcca_layer import GatedChunkedCrossAttention
from .huggingface_adapter import OctoNativeAdapter
from .vllm_integration import AsyncPrefetchWorker, OctoVLLMAdapter

__all__ = [
    "GatedChunkedCrossAttention",
    "OctoNativeAdapter",
    "AsyncPrefetchWorker",
    "OctoVLLMAdapter",
]

