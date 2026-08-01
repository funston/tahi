"""
Standalone RAG baseline.

This module is intentionally independent of the OCTO world-model coprocessors.
It uses off-the-shelf components (sentence-transformers + FAISS) over the same
raw text corpus so we can compare a plain retrieval pipeline against OCTO's
graph+vector grounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from octo.llm_client import LLMClient


@dataclass
class RAGDocument:
    """A document in the RAG corpus."""

    doc_id: str
    text: str
    metadata: dict[str, Any] | None = None


@dataclass
class RAGRetrieval:
    """A retrieved document with similarity score."""

    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] | None = None


class StandaloneRAG:
    """
    Plain dense-retrieval RAG using sentence-transformers and FAISS.

    No graph edges, no node types, no coprocessor logic. The only shared
    surface with OCTO is the raw document text and the LLM client.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        top_k: int = 5,
        llm_client: LLMClient | None = None,
    ):
        self.model_name = model_name
        self.top_k = top_k
        self.llm_client = llm_client or LLMClient.from_env()
        self.documents: dict[str, RAGDocument] = {}
        self._embeddings: np.ndarray | None = None
        self._index: Any = None
        self._embedding_model: Any = None

    def _embed(self, texts: list[str]) -> np.ndarray:
        # Lazy import so the dependency is only required when RAG is used.
        from sentence_transformers import SentenceTransformer

        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(self.model_name)
        return self._embedding_model.encode(texts, normalize_embeddings=True)

    def add_documents(self, documents: list[RAGDocument]) -> None:
        """Add documents to the RAG corpus."""
        for doc in documents:
            self.documents[doc.doc_id] = doc
        self._embeddings = None
        self._index = None

    def build_index(self) -> None:
        """Build the FAISS index over the current documents."""
        import faiss

        if not self.documents:
            raise ValueError("Cannot build RAG index with no documents")

        self._doc_ids = list(self.documents.keys())
        texts = [self.documents[did].text for did in self._doc_ids]
        self._embeddings = self._embed(texts).astype(np.float32)

        dim = self._embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(self._embeddings)

    def retrieve(self, query: str, top_k: int | None = None) -> list[RAGRetrieval]:
        """Retrieve the top-k documents for a query."""
        if self._index is None:
            self.build_index()

        k = top_k or self.top_k
        query_vec = self._embed([query]).astype(np.float32)
        scores, indices = self._index.search(query_vec, k)

        results: list[RAGRetrieval] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            doc_id = self._doc_ids[idx]
            doc = self.documents[doc_id]
            results.append(
                RAGRetrieval(
                    doc_id=doc_id,
                    text=doc.text,
                    score=float(score),
                    metadata=doc.metadata,
                )
            )
        return results

    def answer(
        self,
        query: str,
        system: str = "You answer questions from the provided sources only.",
    ) -> tuple[str, str, list[RAGRetrieval]]:
        """
        Answer a query using retrieved documents.

        Returns (answer_text, model_name, retrievals).
        """
        retrievals = self.retrieve(query)
        context = "\n\n".join(
            f"[{i + 1}] {r.doc_id}\n{r.text}" for i, r in enumerate(retrievals)
        )

        prompt = f"""Answer the following question using ONLY the provided sources.

Question: {query}

Sources:
{context}

Instructions:
- Base your answer only on the sources above.
- Cite the source numbers [1], [2], etc. that support your answer.
- Be concise.

Answer:"""

        resp = self.llm_client.complete(prompt, system=system)
        return resp.text.strip(), resp.model, retrievals
