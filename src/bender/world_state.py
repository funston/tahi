import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .models import EntityRef, RelationRef, RetrievedMemory, Vector
from .retrieval import InMemoryGraphIndex, embed_text
from .retrieval.ann import FaissIndex, STEncoder, get_encoder


@dataclass
class WorldModel:
    domain: str = "general"
    nodes: Dict[str, dict] = field(default_factory=dict)
    edges: List[Tuple[str, str, str, dict]] = field(default_factory=list)
    use_ann: bool = False
    _index: Optional[InMemoryGraphIndex] = field(default=None, init=False, repr=False)
    _ann_index: Optional[FaissIndex] = field(default=None, init=False, repr=False)
    _encoder: Optional[STEncoder] = field(default=None, init=False, repr=False)
    _dirty: bool = field(default=True, init=False, repr=False)

    def upsert_node(self, node_id: str, **attrs) -> None:
        node = self.nodes.setdefault(node_id, {})
        node.update(attrs)
        self._dirty = True

    def add_edge(self, src: str, rel: str, dst: str, **attrs) -> None:
        self.edges.append((src, rel, dst, attrs))
        self._dirty = True

    def neighbors(self, node_id: str) -> List[Tuple[str, str, str, dict]]:
        return [edge for edge in self.edges if edge[0] == node_id or edge[2] == node_id]

    def embedding_text(self, node_id: str) -> str:
        node = self.nodes.get(node_id)
        if node is None:
            return node_id
        parts = [
            node.get("label", ""),
            node.get("summary", ""),
            " ".join(node.get("keywords", [])),
            " ".join(node.get("aliases", [])),
        ]
        return " ".join(part for part in parts if part).strip()

    def build_index(self) -> None:
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

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        query_embedding: Optional[Sequence[float]] = None,
    ) -> List[RetrievedMemory]:
        if self._dirty:
            self.build_index()
            
        if self.use_ann:
            if self._encoder is None:
                self._encoder = get_encoder()
            
            import numpy as np
            q_emb = np.array(query_embedding) if query_embedding is not None else self._encoder.encode([query])[0]
            matches = self._ann_index.search(q_emb, query, top_k=top_k)
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
