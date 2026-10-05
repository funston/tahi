import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from tahi.models import Vector, coerce_vector

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def embed_text(text: str, width: int = 8) -> Vector:
    buckets = [0.0 for _ in range(width)]
    tokens = tokenize(text)
    if not tokens:
        return tuple(buckets)
    for token in tokens:
        index = sum(ord(char) for char in token) % width
        buckets[index] += 1.0
    length = math.sqrt(sum(value * value for value in buckets))
    if length == 0.0:
        return tuple(buckets)
    return tuple(value / length for value in buckets)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    left_vec = coerce_vector(left, width=max(len(left), len(right), 1))
    right_vec = coerce_vector(right, width=max(len(left), len(right), 1))
    denom = math.sqrt(sum(v * v for v in left_vec)) * math.sqrt(sum(v * v for v in right_vec))
    if denom == 0.0:
        return 0.0
    return sum(ln * r for ln, r in zip(left_vec, right_vec, strict=False)) / denom


def token_overlap_score(left_text: str, right_text: str) -> float:
    left_tokens = set(tokenize(left_text))
    right_tokens = set(tokenize(right_text))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


@dataclass
class RetrievalMatch:
    node_id: str
    score: float
    metadata: dict[str, object]


class InMemoryGraphIndex:
    def __init__(
        self,
        vectors: dict[str, Vector],
        metadata: dict[str, dict[str, object]],
        texts: dict[str, str],
    ):
        self.vectors = vectors
        self.metadata = metadata
        self.texts = texts

    @classmethod
    def from_records(
        cls,
        records: Iterable[tuple[str, str, dict[str, object]]],
        width: int = 8,
    ) -> "InMemoryGraphIndex":
        vectors: dict[str, Vector] = {}
        metadata: dict[str, dict[str, object]] = {}
        texts: dict[str, str] = {}
        for node_id, text, attrs in records:
            vectors[node_id] = embed_text(text, width=width)
            metadata[node_id] = attrs
            texts[node_id] = text
        return cls(vectors=vectors, metadata=metadata, texts=texts)

    def search(
        self,
        query: str,
        top_k: int = 3,
        query_embedding: Sequence[float] | None = None,
    ) -> list[RetrievalMatch]:
        search_vector = coerce_vector(query_embedding, width=8) if query_embedding is not None else embed_text(query, width=8)
        scored: list[RetrievalMatch] = []
        for node_id, vector in self.vectors.items():
            semantic_score = cosine_similarity(search_vector, vector)
            overlap_score = token_overlap_score(query, self.texts.get(node_id, ""))
            score = 0.65 * semantic_score + 0.35 * overlap_score
            if score <= 0.0:
                continue
            scored.append(
                RetrievalMatch(
                    node_id=node_id,
                    score=score,
                    metadata=self.metadata.get(node_id, {}),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
