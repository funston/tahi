"""
Entity linking: messy text -> canonical graph node.

This is the slot-filling layer, and it is a standard component rather than a
research question. Siri does not hard-code every phrasing of "what's the
weather"; its NLU resolves them all to one intent with filled slots. Our
equivalent resolves "pyrilamine", "Mepyrimine" (typo), and "Mepyramine" to
`Compound::DB00152`, after which the graph query is exact.

Absent this layer, a graph lookup is exact-match only and returns nothing for
any query that does not already contain the database's own primary key. That is
a missing integration, not evidence that graph retrieval fails -- a distinction
this repository previously got wrong.

Implementation is deliberately unclever: embed every node name once with the
same sentence-transformer used elsewhere, then nearest-neighbour the query span.
Embeddings absorb typos for free because subword pieces overlap, and absorb
paraphrase to the extent the encoder learned it.

What matters more than the method is that **failure is explicit**. A resolution
below `threshold` returns None rather than the closest wrong node, and callers
are expected to report the unresolved rate. An entity linker with an unmeasured
error rate silently caps every downstream number.
"""

from __future__ import annotations

import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np


@dataclass
class Resolution:
    """One attempt to map a text span onto a node."""

    query: str
    node_id: Optional[str]
    node_name: Optional[str]
    score: float
    resolved: bool

    def to_dict(self) -> dict:
        return {"query": self.query, "node_id": self.node_id,
                "node_name": self.node_name, "score": round(self.score, 4),
                "resolved": self.resolved}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


class EntityLinker:
    """Nearest-neighbour over node names, with an explicit unresolved outcome."""

    def __init__(self, id_to_name: dict[str, str], *,
                 encoder=None, threshold: float = 0.72,
                 kinds: Optional[dict[str, str]] = None,
                 cache: str | Path | None = None):
        self.id_to_name = id_to_name
        self.kinds = kinds or {}
        self.threshold = threshold
        self.node_ids = sorted(id_to_name)
        self.names = [id_to_name[n] for n in self.node_ids]

        # Exact normalised match short-circuits the embedding path: it is both
        # faster and unambiguous when the query already names the entity.
        self._exact: dict[str, str] = {}
        for nid in self.node_ids:
            self._exact.setdefault(_norm(id_to_name[nid]), nid)

        self.encoder = encoder
        self._matrix: Optional[np.ndarray] = None
        self._cache = Path(cache) if cache else None
        if self._cache and self._cache.exists():
            with open(self._cache, "rb") as fh:
                blob = pickle.load(fh)
            if blob.get("node_ids") == self.node_ids:
                self._matrix = blob["matrix"]

    def build(self, batch: int = 2048) -> None:
        """Embed every node name once. Cached to disk keyed by the node set."""
        if self._matrix is not None:
            return
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        vecs = []
        for i in range(0, len(self.names), batch):
            v = self.encoder.encode(self.names[i:i + batch],
                                    convert_to_numpy=True,
                                    show_progress_bar=False)
            vecs.append(np.asarray(v, dtype=np.float32))
        m = np.vstack(vecs)
        m /= np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-8, None)
        self._matrix = m
        if self._cache:
            self._cache.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache, "wb") as fh:
                pickle.dump({"node_ids": self.node_ids, "matrix": m}, fh)

    def resolve(self, text: str, *, kind: Optional[str] = None) -> Resolution:
        """Map `text` to a node, or return unresolved."""
        if not text.strip():
            return Resolution(text, None, None, 0.0, False)

        key = _norm(text)
        if key in self._exact:
            nid = self._exact[key]
            if kind is None or self.kinds.get(nid) == kind:
                return Resolution(text, nid, self.id_to_name[nid], 1.0, True)

        self.build()
        q = self.encoder.encode([text], convert_to_numpy=True,
                                show_progress_bar=False)
        q = np.asarray(q, dtype=np.float32)
        q /= np.clip(np.linalg.norm(q, axis=1, keepdims=True), 1e-8, None)
        sims = (self._matrix @ q[0])

        if kind is not None and self.kinds:
            mask = np.array([self.kinds.get(n) == kind for n in self.node_ids])
            sims = np.where(mask, sims, -1.0)

        idx = int(np.argmax(sims))
        score = float(sims[idx])
        nid = self.node_ids[idx]
        ok = score >= self.threshold
        return Resolution(text, nid if ok else None,
                          self.id_to_name[nid] if ok else None, score, ok)

    def resolve_many(self, texts: Iterable[str], *,
                     kind: Optional[str] = None) -> list[Resolution]:
        return [self.resolve(t, kind=kind) for t in texts]

    def unresolved_rate(self, resolutions: Sequence[Resolution]) -> float:
        """The number that caps every downstream result. Report it."""
        if not resolutions:
            return 0.0
        return sum(1 for r in resolutions if not r.resolved) / len(resolutions)
