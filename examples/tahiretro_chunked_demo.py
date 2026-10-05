#!/usr/bin/env python
"""
TahiRetro end-to-end wiring check: graph retrieval re-aimed every N generated tokens.

Prints the boundary trace -- what the model had just written at each boundary, and
which graph nodes that text pulled back. The trace is the point: it is the artefact
that distinguishes this from one-shot injection, and it is what the 2026-08-04 run
could not have produced because it never re-queried.

The multi-hop shape is built in deliberately. Chunk 1's query cannot mention Chile,
because the model has not yet said "Neruda". Only after it writes the bridge entity
can retrieval reach the hop-2 node. That is the mechanism, visible in one run.

    PYTHONPATH=src .venv/bin/python examples/tahiretro_chunked_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import torch  # noqa: E402

from tahi.native.chunk_retriever import WorldModelChunkRetriever  # noqa: E402
from tahi.world_state import WorldModel  # noqa: E402

CHUNK = 8   # tiny so boundaries fire inside a short demo; 64 in production


def build_world_model() -> WorldModel:
    """A three-hop chain: book -> author -> country -> capital."""
    wm = WorldModel(use_ann=True)
    docs = {
        "doc::book": "Twenty Love Poems and a Song of Despair is a poetry "
                     "collection written by the author Pablo Neruda.",
        "doc::author": "Pablo Neruda was a poet who was born in Parral, "
                       "a town in Chile.",
        "doc::country": "Chile is a country in South America. Its capital "
                        "city is Santiago.",
        "doc::distractor_a": "Gabriel Garcia Marquez was born in Colombia, "
                             "whose capital is Bogota.",
        "doc::distractor_b": "Octavio Paz was a Mexican poet; the capital "
                             "of Mexico is Mexico City.",
    }
    for node_id, text in docs.items():
        wm.upsert_node(node_id, node_type="document", text=text, label=node_id)

    for ent, label in [("ent::neruda", "Pablo Neruda"), ("ent::chile", "Chile"),
                       ("ent::santiago", "Santiago")]:
        wm.upsert_node(ent, node_type="entity", label=label, text=label)

    wm.add_edge("doc::book", "mentions", "ent::neruda")
    wm.add_edge("ent::neruda", "has_doc", "doc::author")
    wm.add_edge("doc::author", "mentions", "ent::chile")
    wm.add_edge("ent::chile", "has_doc", "doc::country")
    wm.add_edge("doc::country", "mentions", "ent::santiago")
    wm.build_index()
    return wm


def main() -> int:
    wm = build_world_model()
    retriever = WorldModelChunkRetriever(wm, top_k=3, max_slots=8, expand=True)

    # What the model would have written, chunk by chunk. Standing in for decode so
    # the wiring is checked without pulling a 1.5B model into a demo.
    written = [
        "The collection was written by",
        "Pablo Neruda, who was born in",
        "Chile, and the capital of that country is",
    ]

    print(f"TahiRetro boundary trace  (chunk_size={CHUNK}, expand=True)")
    print("=" * 74)
    banks: list[torch.Tensor | None] = []
    hits: list[list[str]] = []
    for i, text in enumerate(written):
        r = retriever(text)
        banks.append(r.memory)
        hits.append(r.node_ids)
        print(f"\nboundary {i}  query = {text!r}")
        if r.memory is None:
            print("  -> no hit")
            continue
        print(f"  -> {r.n_slots} slots, tensor {tuple(r.memory.shape)}")
        for nid, score in zip(r.node_ids, r.scores, strict=False):
            print(f"     {score:6.3f}  {nid}")

    print("\n" + "=" * 74)
    resident = {tuple(b.shape) for b in banks if b is not None}
    print(f"resident bank shapes across all boundaries: {resident}")
    print("O(1): the bank does not grow with generated length; "
          "only the number of queries does.")

    hop2 = "doc::country"
    first = next((i for i, h in enumerate(hits) if hop2 in h), None)
    print(f"\nhop-2 node {hop2!r} first retrieved at boundary: {first}")
    print("A one-shot arm queries only boundary 0, so it never reaches it.")
    print(f"retriever calls={retriever.calls} cache_hits={retriever.cache_hits}")
    return 0


if __name__ == "__main__":
    torch.manual_seed(0)
    raise SystemExit(main())
