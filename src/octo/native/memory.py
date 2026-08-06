"""
Build the retrieved-memory tensor that GCCA cross-attends over.

This replaces the placeholder that made Level 3 inert. The previous packet
carried `tuple([0.1] * 768)` -- a constant, identical for every query, pooled to
a single slot. Cross-attention over one constant vector has nothing to attend
to and carries zero bits about the query, so even a fully trained adapter could
not have beaten Level 1.

What GCCA actually needs is `[B, K, d_retriever]`: one slot per retrieved node,
each slot the real embedding of that node's text. That gives the attention
something to select between -- which is the entire mechanism.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional, Sequence

import numpy as np
import torch

from octo.models import CognitiveState
from octo.world_state import WorldModel

def node_texts(state: CognitiveState, world_model: WorldModel,
               max_slots: int = 16) -> list[str]:
    """Text for each retrieved node, best-ranked first, capped at `max_slots`."""
    texts: list[str] = []
    for r in state.retrievals[:max_slots]:
        node = world_model.nodes.get(r.node_id, {})
        text = node.get("text") or node.get("summary") or node.get("label") or ""
        if text:
            texts.append(str(text))
    return texts


GLOBAL_RELATION_MAP: dict[str, int] = {
    "mentions": 0, "has_mentions": 0,
    "has_doc": 1, "in_project": 1,
    "covers": 2, "in_thread": 2,
    "related_to": 3, "references": 3,
    "participant": 4, "authored_by": 4,
    "in_repo": 5, "about": 5,
}


def _get_relation_index(rel: str) -> int:
    rel_clean = str(rel).lower().strip()
    if rel_clean in GLOBAL_RELATION_MAP:
        return GLOBAL_RELATION_MAP[rel_clean]
    return int(hashlib.md5(rel_clean.encode("utf-8")).hexdigest(), 16) % 16


def build_memory_tensor(
    state: CognitiveState,
    world_model: WorldModel,
    *,
    max_slots: int = 16,
    gnn_encoder: Optional[Any] = None,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor | None:
    """Encode retrieved nodes into `[1, K, d_retriever]` topological memory tensor.

    When `gnn_encoder` (SubgraphRGATEncoder) is provided, node embeddings and relational
    subgraph edges undergo PyTorch RGAT message passing to encode graph topology directly.
    """
    texts = node_texts(state, world_model, max_slots=max_slots)
    if not texts:
        return None

    if world_model._encoder is None:  # noqa: SLF001 -- the model owns its encoder
        world_model.build_index()
    encoder = world_model._encoder  # noqa: SLF001

    vectors = np.asarray(encoder.encode(texts), dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors[None, :]

    # L2-normalise each slot.
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.clip(norms, 1e-8, None)
    base_tensor = torch.from_numpy(vectors).to(device=device, dtype=dtype)

    if gnn_encoder is not None:
        # Extract edge tuples among the retrieved node slots for GNN message passing
        retrieved_ids = [r.node_id for r in state.retrievals[:max_slots]]
        id2idx = {nid: idx for idx, nid in enumerate(retrieved_ids)}
        edge_tuples: list[tuple[int, int, int]] = []
        
        for nid in retrieved_ids:
            for src, rel, dst, _attrs in world_model.neighbors(nid):
                if src in id2idx and dst in id2idx:
                    rel_idx = _get_relation_index(rel)
                    edge_tuples.append((id2idx[src], rel_idx, id2idx[dst]))
        
        return gnn_encoder(base_tensor, edge_tuples)

    return base_tensor.unsqueeze(0)


def build_memory_from_vectors(
    vectors: Sequence[Sequence[float]],
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Pack pre-computed per-slot vectors into `[1, K, d]`. For training loops
    that cache embeddings rather than re-encoding every step."""
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    return torch.from_numpy(arr).to(device=device, dtype=dtype).unsqueeze(0)


def memory_is_informative(memory: torch.Tensor, tol: float = 1e-6) -> bool:
    """True when slots actually differ from one another.

    Guard against silently regressing to the constant-vector state: if every
    slot is identical, cross-attention is a no-op regardless of training, and a
    Level 3 run would measure nothing. Benchmarks assert this before spending
    GPU hours.
    """
    if memory is None or memory.numel() == 0:
        return False
    slots = memory.reshape(-1, memory.shape[-1])
    if slots.shape[0] < 2:
        return bool(slots.abs().max() > tol)
    return bool((slots - slots[0:1]).abs().max() > tol)
