import hashlib
import math
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None

from bender.models import RelationRef, RetrievedMemory, Vector

_ENCODER_CACHE: Dict[str, "Encoder"] = {}

def get_encoder(model_name: str = "all-MiniLM-L6-v2") -> "Encoder":
    if model_name not in _ENCODER_CACHE:
        encoder_backend = os.environ.get("BENDER_ENCODER_BACKEND", "hashed").strip().lower()
        if encoder_backend != "sentence-transformer":
            _ENCODER_CACHE[model_name] = HashedTokenEncoder()
        else:
            try:
                _ENCODER_CACHE[model_name] = STEncoder(model_name)
            except Exception:
                _ENCODER_CACHE[model_name] = HashedTokenEncoder()
    return _ENCODER_CACHE[model_name]


class Encoder:
    dimension: int

    def encode(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError


class STEncoder:
    """Encoder using SentenceTransformers for high-quality semantic embeddings."""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not available")
        self.model = SentenceTransformer(model_name, local_files_only=True)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True)


class HashedTokenEncoder:
    """Deterministic offline encoder used when the sentence-transformer is unavailable."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def encode(self, texts: List[str]) -> np.ndarray:
        embeddings = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row_index, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9_]+", text.lower())
            if not tokens:
                continue
            for token in tokens:
                token_hash = hashlib.sha256(token.encode("utf-8")).digest()
                bucket = int.from_bytes(token_hash[:4], "little") % self.dimension
                sign = 1.0 if token_hash[4] % 2 == 0 else -1.0
                embeddings[row_index, bucket] += sign
            norm = np.linalg.norm(embeddings[row_index])
            if norm > 0:
                embeddings[row_index] /= norm
        return embeddings

class FaissIndex:
    """Fast Approximate Nearest Neighbor search using FAISS."""
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension) if faiss is not None else None
        self.node_ids: List[str] = []
        self.metadata: List[Dict] = []
        self.texts: List[str] = []
        self.embeddings: Optional[np.ndarray] = None

    def add_records(self, node_ids: List[str], texts: List[str], embeddings: np.ndarray, metadata: List[Dict]):
        normalized = embeddings.astype("float32")
        if self.index is not None:
            self.index.add(normalized)
        self.embeddings = normalized if self.embeddings is None else np.vstack([self.embeddings, normalized])
        self.node_ids.extend(node_ids)
        self.texts.extend(texts)
        self.metadata.extend(metadata)

    def search(self, query_embedding: np.ndarray, query_text: str, top_k: int = 5) -> List[dict]:
        query_embedding = query_embedding.reshape(1, -1).astype("float32")
        if self.index is not None:
            distances, indices = self.index.search(query_embedding, top_k)
        else:
            if self.embeddings is None or len(self.node_ids) == 0:
                return []
            deltas = self.embeddings - query_embedding
            flat_distances = np.sum(deltas * deltas, axis=1)
            order = np.argsort(flat_distances)[:top_k]
            distances = np.array([flat_distances[order]], dtype=np.float32)
            indices = np.array([order], dtype=np.int64)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1: continue
            
            node_id = self.node_ids[idx]
            # Combine L2 distance (converted to similarity) with token overlap
            semantic_sim = 1.0 / (1.0 + distances[0][i])
            overlap_sim = self._token_overlap(query_text, self.texts[idx])
            
            score = 0.7 * semantic_sim + 0.3 * overlap_sim
            results.append({
                "node_id": node_id,
                "score": float(score),
                "text": self.texts[idx],
                "metadata": self.metadata[idx]
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _token_overlap(self, text1: str, text2: str) -> float:
        tokens1 = set(re.findall(r"[a-z0-9]+", text1.lower()))
        tokens2 = set(re.findall(r"[a-z0-9]+", text2.lower()))
        if not tokens1: return 0.0
        return len(tokens1 & tokens2) / len(tokens1)
