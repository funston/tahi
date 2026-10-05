"""
Native integration modules for TAHI (Level 2/3 latent & cross-attention residual injection).

`chunked_decode` + `chunk_retriever` are the TahiRetro mechanism: retrieval re-aimed
every 64 generated tokens, keyed on what the model just wrote, injected into the
residual stream. See docs/TAHIRETRO_SPEC.md for what is being built and why the
earlier Level 3 arm did not test it.
"""

from .chunk_retriever import (
    ChunkRetrieval,
    ChunkRetriever,
    FlatChunkRetriever,
    StaticChunkRetriever,
    WorldModelChunkRetriever,
)
from .chunked_decode import (
    BoundaryEvent,
    ChunkedGeneration,
    build_chunk_banks,
    chunked_generate,
)
from .gcca_layer import DEFAULT_CHUNK_SIZE, GatedChunkedCrossAttention
from .huggingface_adapter import TahiNativeAdapter
from .vllm_integration import AsyncPrefetchWorker, TahiVLLMAdapter

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "GatedChunkedCrossAttention",
    "TahiNativeAdapter",
    "AsyncPrefetchWorker",
    "TahiVLLMAdapter",
    "ChunkRetrieval",
    "ChunkRetriever",
    "WorldModelChunkRetriever",
    "FlatChunkRetriever",
    "StaticChunkRetriever",
    "BoundaryEvent",
    "ChunkedGeneration",
    "chunked_generate",
    "build_chunk_banks",
]
