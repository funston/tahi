import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import EntityRef, RelationRef, RetrievedMemory, Vector
from .retrieval import InMemoryGraphIndex, embed_text
from .retrieval.ann import FaissIndex, STEncoder, get_encoder

try:
    from .graph.kuzu_store import KuzuGraphStore
except ImportError:
    KuzuGraphStore = None


@dataclass
class WorldModel:
    domain: str = "general"
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[tuple[str, str, str, dict]] = field(default_factory=list)
    use_ann: bool = False
    use_kuzu: bool = False
    expansion_boost_weight: float = 0.5
    """How far structure may move a candidate, as a fraction of the spread of the
    direct scores. 0 disables the boost and leaves expansion as pure additive
    recall; 1 lets a fully-supported one-hop neighbour cross the entire observed
    range. See `_expand` for why this is a fraction rather than a constant."""
    expansion_support_cap: int = 5
    """Support beyond this many distinct seeds stops counting. A hub adjacent to
    everything would otherwise accumulate unbounded support and re-acquire the
    behaviour the bound exists to remove."""
    kuzu_db_path: str | None = None
    _index: InMemoryGraphIndex | None = field(default=None, init=False, repr=False)
    _ann_index: FaissIndex | None = field(default=None, init=False, repr=False)
    _encoder: STEncoder | None = field(default=None, init=False, repr=False)
    _kuzu_store: Any | None = field(default=None, init=False, repr=False)
    _dirty: bool = field(default=True, init=False, repr=False)

    def init_kuzu(self, db_path: str | None = None) -> None:
        """Initialize Kùzu graph store and sync current nodes/edges."""
        if KuzuGraphStore is None:
            raise ImportError("kuzu package is not available. Please install `kuzu`.")
        self.use_kuzu = True
        if db_path:
            self.kuzu_db_path = db_path
        if self._kuzu_store is None:
            self._kuzu_store = KuzuGraphStore(self.kuzu_db_path)

        # Sync existing nodes and edges into Kùzu
        if self.nodes:
            self._kuzu_store.add_nodes([(nid, attrs) for nid, attrs in self.nodes.items()])
        if self.edges:
            self._kuzu_store.add_edges(self.edges)

    def upsert_node(self, node_id: str, **attrs) -> None:
        node = self.nodes.setdefault(node_id, {})
        node.update(attrs)
        self._dirty = True
        if self.use_kuzu and self._kuzu_store is not None:
            self._kuzu_store.add_nodes([(node_id, node)])

    def add_edge(self, src: str, rel: str, dst: str, **attrs) -> None:
        edge = (src, rel, dst, attrs)
        self.edges.append(edge)
        self._dirty = True
        if self.use_kuzu and self._kuzu_store is not None:
            self._kuzu_store.add_edges([edge])

    def _build_adjacency(self) -> None:
        """Index edges by endpoint. O(1) lookup instead of O(E) scan.

        The unindexed version scanned the full edge list per lookup. At
        956,232 edges that is ~19M comparisons for a single query at 10 seeds
        and two hops -- slow enough that the fragment-verification experiment
        could not complete inside a 30-minute timeout. For persistence and
        Cypher traversal at corpus scale, see tahi.graph.KuzuGraphStore.
        """
        adj: dict[str, list[tuple[str, str, str, dict]]] = {}
        for edge in self.edges:
            adj.setdefault(edge[0], []).append(edge)
            if edge[2] != edge[0]:
                adj.setdefault(edge[2], []).append(edge)
        self._adjacency = adj
        self._adjacency_size = len(self.edges)

    def neighbors(self, node_id: str) -> list[tuple[str, str, str, dict]]:
        if self.use_kuzu:
            if self._kuzu_store is None:
                self.init_kuzu()
            k_res = self._kuzu_store.neighbors(node_id)
            return [(src, rel, dst, {}) for src, rel, dst in k_res]

        adj = getattr(self, "_adjacency", None)
        # Rebuild when edges were appended after the last index build.
        if adj is None or getattr(self, "_adjacency_size", -1) != len(self.edges):
            self._build_adjacency()
            adj = self._adjacency
        return adj.get(node_id, [])

    def embedding_text(self, node_id: str) -> str:
        """Text the ANN index embeds for this node.

        `text` is used only when `summary` is absent. Callers that set both --
        `implementations/enterprise_rag` sets `summary=text[:MAX_DOC_CHARS]` --
        keep their existing, truncated indexing behaviour unchanged.

        The fallback exists because a node carrying `text` and no `summary`
        previously indexed as its *label alone*, so a document store built the
        obvious way retrieved on identifiers rather than content -- silently, and
        with no error. `build_memory_from_retrievals` already reads
        `text or summary or label`; the index read a different field from the
        memory path, and nothing checked that they agreed.
        """
        node = self.nodes.get(node_id)
        if node is None:
            return node_id
        parts = [
            node.get("label", ""),
            node.get("summary", "") or node.get("text", ""),
            " ".join(node.get("keywords", [])),
            " ".join(node.get("aliases", [])),
        ]
        return " ".join(part for part in parts if part).strip()

    def build_index(self) -> None:
        if self.use_kuzu and self._kuzu_store is None:
            self.init_kuzu()

        if self.use_ann:
            if self._encoder is None:
                self._encoder = get_encoder()

            node_ids = []
            texts = []
            metadata = []
            for node_id, node in self.nodes.items():
                node_ids.append(node_id)
                texts.append(self.embedding_text(node_id))
                metadata.append(dict(node))

            embeddings = self._encoder.encode(texts)
            self._ann_index = FaissIndex(self._encoder.dimension)
            self._ann_index.add_records(node_ids, texts, embeddings, metadata)
        else:
            records = []
            for node_id, node in self.nodes.items():
                text = self.embedding_text(node_id)
                records.append((node_id, text, dict(node)))
            self._index = InMemoryGraphIndex.from_records(records)
        self._dirty = False

    def graph_signal(self, retrievals: Sequence[RetrievedMemory], width: int = 8) -> Vector:
        if not retrievals:
            return tuple(0.0 for _ in range(width))

        # Determine actual dimension to use
        if self.use_ann:
            if self._encoder is None:
                self._encoder = get_encoder()
            actual_width = self._encoder.dimension
        else:
            actual_width = width

        weighted = [0.0 for _ in range(actual_width)]
        normalizer = 0.0
        for item in retrievals:
            # Skip nodes not in this specific world model for signal calculation
            if item.node_id not in self.nodes:
                continue

            if self.use_ann:
                text = self.embedding_text(item.node_id)
                vector = self._encoder.encode([text])[0]
            else:
                text = self.embedding_text(item.node_id)
                vector = embed_text(text, width=actual_width)

            normalizer += item.score
            for index, value in enumerate(vector):
                weighted[index] += float(value) * item.score

        if normalizer == 0.0:
            return tuple(0.0 for _ in range(actual_width))
        return tuple(value / normalizer for value in weighted)

    # Node types that carry no evidence text. They are useful as traversal
    # SEEDS -- a query naming a project should reach that project's documents --
    # but returning one as a result wastes a retrieval slot and a slot in the
    # answer context, since there is nothing to read. Measured cost of not
    # excluding them: doc_recall 0.408 -> 0.331 against plain dense retrieval.
    # Declared per world model. Listing INDEX types rather than evidence types
    # keeps every existing domain working unchanged: a model that declares
    # nothing treats all nodes as evidence, exactly as before.
    def index_node_types(self) -> set:
        return set(getattr(self, "_index_node_types", ()) or ())

    def set_index_node_types(self, types) -> None:
        """Mark node types that exist only for traversal, not as evidence."""
        self._index_node_types = set(types)

    def _is_evidence(self, node_id: str) -> bool:
        node = self.nodes.get(node_id, {})
        return node.get("type") not in self.index_node_types()

    def _expand(
        self,
        seeds: list[tuple[str, float]],
        query_vec,
        exclude: set,
        decay: float,
        floor: float,
        limit: int,
        query_text: str = "",
    ) -> list[tuple[str, float]]:
        """Walk edges from seeds to evidence nodes, scoring candidates on the
        index's own scale with a *bounded* structural boost.

        Two bugs are fixed here, both measured.

        **Scale.** Candidates were scored with a bare cosine and then merged
        against direct hits carrying the index's blended `0.7 * semantic +
        0.3 * overlap` score. Those are different quantities; the ordering
        between them meant nothing. Both sides now come from
        `FaissIndex.score_nodes`.

        **Magnitude.** The boost was `0.15 * min(support, 5) / hops`, reaching
        `+0.75` against a score range of roughly 0.17 on the same fixture. Any
        node with several supporting seeds therefore outranked every direct hit
        regardless of relevance -- structure overwrote relevance instead of
        informing it. On `tests/test_graph_retrieval.py` this promoted
        `doc::noise` to 0.8788 against the top direct hit's 0.4435 and evicted
        `doc::answer`, which dense retrieval had already found. Measured on
        MetaQA the same defect scored 0.085 answer recall@1 where the identical
        retriever with `expand=False` scored 0.935.

        The boost is now expressed as a fraction of the observed spread of the
        direct scores, so it cannot outgrow the signal it modifies:

            boost = boost_weight * (min(support, cap) / cap) / hops * spread

        At the default `boost_weight = 0.5`, full support at one hop moves a
        candidate by at most half the range separating the best direct hit from
        the worst. That is enough to reorder within a cluster and not enough to
        jump the field. It is a bound, not a tuned constant: no value of
        `boost_weight` <= 1 can promote a candidate past a direct hit that leads
        it by more than the spread.
        """
        import numpy as np

        seed_ids = [s[0] for s in seeds]
        candidates_support: dict[str, tuple[int, int]] = {} # node_id -> (support_count, min_hops)

        if self.use_kuzu and self._kuzu_store is not None:
            # Query Kùzu Cypher engine for distinct seed support and shortest hop distance
            kuzu_expanded = self._kuzu_store.expand(seed_ids, hops=2, limit=limit * 4)
            for nid, supp, hops in kuzu_expanded:
                if nid not in exclude and self._is_evidence(nid):
                    candidates_support[nid] = (supp, hops)
        else:
            # Fallback Python adjacency path count
            for seed_id, _ in seeds:
                for src, _rel, dst, _attrs in self.neighbors(seed_id):
                    other = dst if src == seed_id else src
                    if other in exclude or other == seed_id:
                        continue
                    if not self._is_evidence(other):
                        for s2, _r2, d2, _a2 in self.neighbors(other):
                            nxt = d2 if s2 == other else s2
                            if nxt in exclude or not self._is_evidence(nxt):
                                continue
                            prev_supp, prev_hops = candidates_support.get(nxt, (0, 2))
                            candidates_support[nxt] = (prev_supp + 1, min(prev_hops, 2))
                        continue
                    prev_supp, prev_hops = candidates_support.get(other, (0, 1))
                    candidates_support[other] = (prev_supp + 1, min(prev_hops, 1))

        if not candidates_support:
            return []

        ids = list(candidates_support)
        sims = self._ann_index.score_nodes(query_vec, query_text or "", ids)
        if not sims:
            return []

        # The spread the boost is measured against. Taken from the direct hits,
        # not from the candidates: it has to describe the scale the merge happens
        # on, and the merge happens against those.
        direct_scores = [s for _n, s in seeds] or list(sims.values())
        spread = max(direct_scores) - min(direct_scores)
        if spread <= 0:
            spread = max(direct_scores) if direct_scores else 0.0

        scored: list[tuple[str, float]] = []
        for node_id in ids:
            sim = sims.get(node_id)
            if sim is None or sim < floor:
                continue
            supp, hops = candidates_support[node_id]
            support_fraction = min(supp, self.expansion_support_cap) / float(
                self.expansion_support_cap)
            structural_boost = (
                self.expansion_boost_weight * support_fraction
                / float(max(hops, 1)) * spread
            )
            scored.append((node_id, sim + structural_boost))

        scored.sort(key=lambda kv: -kv[1])
        return scored[:limit]

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        query_embedding: Sequence[float] | None = None,
        expand: bool = True,
        expansion_decay: float = 0.9,
        expansion_floor: float = 0.05,
        oversample: int = 4,
    ) -> list[RetrievedMemory]:
        """Retrieve evidence nodes by vector similarity plus edge traversal.

        Returns up to `top_k` EVIDENCE nodes. Entity nodes act as traversal
        seeds and are never returned, so `top_k` means the same thing here as it
        does for a document-only baseline -- previously it did not, and the two
        systems were being compared at different effective budgets.
        """
        if self._dirty:
            self.build_index()

        if self.use_ann:
            if self._encoder is None:
                self._encoder = get_encoder()

            import numpy as np
            q_emb = np.array(query_embedding) if query_embedding is not None else self._encoder.encode([query])[0]
            # Oversample: entity hits are seeds rather than results, so a bare
            # top_k search would return fewer than top_k documents.
            matches = self._ann_index.search(q_emb, query, top_k=max(top_k * oversample, top_k))

            direct = [(m["node_id"], float(m["score"])) for m in matches]
            evidence = [(n, s) for n, s in direct if self._is_evidence(n)]
            selected = dict(evidence[:top_k])

            if expand and len(self.edges) > 0:
                extra = self._expand(
                    seeds=direct[:top_k],
                    query_vec=q_emb,
                    exclude=set(selected),
                    decay=expansion_decay,
                    floor=expansion_floor,
                    limit=top_k,
                    query_text=query,
                )
                # Additive merge: everything dense retrieval found is kept, and
                # expanded candidates compete only for the remaining slots.
                pool = list(selected.items()) + extra
                pool.sort(key=lambda kv: -kv[1])
                seen, merged = set(), []
                for node_id, score in pool:
                    if node_id in seen:
                        continue
                    seen.add(node_id)
                    merged.append((node_id, score))
                    if len(merged) >= top_k:
                        break
                # Backfill from remaining direct hits if expansion came up short.
                if len(merged) < top_k:
                    for node_id, score in evidence:
                        if node_id not in seen:
                            merged.append((node_id, score))
                            seen.add(node_id)
                        if len(merged) >= top_k:
                            break
                chosen = merged
            else:
                chosen = list(selected.items())

            matches = [{"node_id": n, "score": s} for n, s in chosen]
            retrieval_records = []
            for match in matches:
                node_data = self.nodes[match["node_id"]]
                score = match["score"]
                # Apply Grounder penalty if present
                if "relevance_penalty" in node_data:
                    score *= node_data["relevance_penalty"]

                retrieval_records.append(RetrievedMemory(
                    node_id=match["node_id"],
                    label=node_data.get("label", match["node_id"]),
                    node_type=node_data.get("type", "concept"),
                    score=float(score),
                    attributes=dict(node_data),
                    relations=[]
                ))
        else:
            index = self._index
            matches = index.search(query=query, top_k=top_k, query_embedding=query_embedding)
            retrieval_records = []
            for match in matches:
                node = self.nodes[match.node_id]
                retrieval_records.append(
                    RetrievedMemory(
                        node_id=match.node_id,
                        label=node.get("label", match.node_id),
                        node_type=node.get("type", "concept"),
                        score=match.score,
                        attributes=dict(node),
                        relations=[],
                    )
                )

        # Hydrate relations for all matches
        for item in retrieval_records:
            item.relations = [
                RelationRef(
                    source=src,
                    relation=rel,
                    target=dst,
                    score=float(attrs.get("score", 1.0)),
                    attributes=dict(attrs),
                )
                for src, rel, dst, attrs in self.neighbors(item.node_id)
            ]

        return retrieval_records

    def entity_ref(self, node_id: str, score: float = 1.0) -> EntityRef:
        node = self.nodes[node_id]
        return EntityRef(
            id=node_id,
            label=node.get("label", node_id),
            type=node.get("type", "concept"),
            score=score,
            attributes=dict(node),
        )

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "nodes": self.nodes,
            "edges": self.edges,
            "use_ann": self.use_ann,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldModel":
        return cls(
            domain=data.get("domain", "general"),
            nodes=data.get("nodes", {}),
            edges=[tuple(edge) if isinstance(edge, list) else edge for edge in data.get("edges", [])],
            use_ann=data.get("use_ann", False),
        )

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "WorldModel":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
