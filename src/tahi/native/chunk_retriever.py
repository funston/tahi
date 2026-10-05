"""
Per-chunk retrieval: the thing the 2026-08-04 Level 3 run did not have.

That run called `runtime.infer(query=question)` once, set the memory tensor, and
held it constant for every generated token. It therefore measured the "Once, at
step 0" column of the RETRO-v2 brief -- the baseline -- while reporting it as the
treatment. The mechanism under test is the other column: retrieval re-aimed every
`chunk_size` tokens, keyed on what the model has just written.

This module supplies the callable that a decode boundary invokes. It is
deliberately narrow: text in, `[1, K, d_retriever]` plus provenance out. What
sits behind it -- flat vector ANN, graph traversal, KiRAG-style iterative triple
retrieval -- is a swap of one object, because the discriminating experiment is
retrieval *schedule* versus retrieval *substrate* and those two must be varied
independently or neither result means anything.

`WorldModelChunkRetriever` is the graph/semantic arm: it goes through
`WorldModel.retrieve`, which does vector seeding plus typed edge expansion, so the
slots carry graph neighbourhood rather than raw nearest text. `FlatChunkRetriever`
is the RETRO-faithful control over the same corpus with expansion switched off.
Running both against the same schedule is what separates "continuous retrieval
helps" from "graph retrieval helps".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import torch

from tahi.world_state import WorldModel

from .memory import build_memory_from_retrievals


@dataclass
class ChunkRetrieval:
    """One boundary's retrieval result, carried alongside the tensor for audit."""

    memory: torch.Tensor | None          # [1, K, d_retriever], or None if nothing hit
    node_ids: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)

    @property
    def n_slots(self) -> int:
        return 0 if self.memory is None else int(self.memory.shape[-2])


class ChunkRetriever(Protocol):
    """Called at every chunk boundary with the text the model just produced."""

    def __call__(self, query_text: str) -> ChunkRetrieval: ...


class WorldModelChunkRetriever:
    """Graph-and-vector retrieval over an TAHI `WorldModel`, one call per boundary.

    `expand=True` is the point of the arm: vector search seeds entity nodes, typed
    edges pull in neighbours, and the slots the model cross-attends therefore encode
    graph adjacency rather than text similarity alone. That is the TAHI half of
    TahiRetro. Set `expand=False` for the ablation.
    """

    def __init__(
        self,
        world_model: WorldModel,
        *,
        top_k: int = 8,
        max_slots: int = 16,
        expand: bool = True,
        gnn_encoder: Any | None = None,
        device: str | torch.device = "cpu",
        dtype: torch.dtype = torch.float32,
    ):
        self.world_model = world_model
        self.top_k = top_k
        self.max_slots = max_slots
        self.expand = expand
        self.gnn_encoder = gnn_encoder
        self.device = device
        self.dtype = dtype
        # Boundary-keyed cache. Generation revisits near-identical trailing text
        # often enough that this materially changes decode latency, and it never
        # changes a result: same query string, same nodes.
        self._cache: dict[str, ChunkRetrieval] = {}
        self.calls = 0
        self.cache_hits = 0

    def __call__(self, query_text: str) -> ChunkRetrieval:
        self.calls += 1
        key = query_text.strip()
        if not key:
            return ChunkRetrieval(memory=None)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]

        retrievals: Sequence[Any] = self.world_model.retrieve(
            key, top_k=self.top_k, expand=self.expand,
        )
        memory = build_memory_from_retrievals(
            retrievals, self.world_model, max_slots=self.max_slots,
            gnn_encoder=self.gnn_encoder, device=self.device, dtype=self.dtype,
        )
        result = ChunkRetrieval(
            memory=memory,
            node_ids=[r.node_id for r in retrievals[: self.max_slots]],
            scores=[float(r.score) for r in retrievals[: self.max_slots]],
        )
        self._cache[key] = result
        return result


class FlatChunkRetriever(WorldModelChunkRetriever):
    """RETRO-faithful control: same corpus, same schedule, no graph expansion."""

    def __init__(self, world_model: WorldModel, **kwargs: Any):
        kwargs["expand"] = False
        super().__init__(world_model, **kwargs)


class StaticChunkRetriever:
    """Returns one fixed bank forever, whatever the boundary query says.

    This is the 2026-08-04 architecture expressed as a retriever, so the old
    result can be reproduced inside the new harness instead of being argued
    about. An arm using this must score the same as one-shot injection; if it
    does not, the decode loop is wrong.
    """

    def __init__(self, memory: torch.Tensor | None, node_ids: list[str] | None = None):
        self._result = ChunkRetrieval(memory=memory, node_ids=node_ids or [])
        self.calls = 0

    def __call__(self, query_text: str) -> ChunkRetrieval:  # noqa: ARG002 -- fixed by design
        self.calls += 1
        return self._result
