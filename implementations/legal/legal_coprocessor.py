"""
Legal world coprocessor.

Builds a structured world model from statutes, regulations, and cases, then
answers legal-reasoning questions by retrieving grounded evidence and
composing an LLM answer.

The coprocessor intentionally separates:
  1. World-model construction (graph + vector index)
  2. Grounded retrieval (vector + citation graph expansion)
  3. Answer generation (LLM with evidence packet)

This lets us compare OCTO against a plain RAG baseline that uses the same
chunks but no graph structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from octo.llm_client import LLMClient
from octo.world_state import WorldModel
from octo.retrieval import get_encoder


@dataclass
class LegalQuestion:
    """A single legal reasoning question with expected answer."""

    id: str
    text: str
    answer: str
    task: str = "statutory_reasoning"
    options: dict[str, str] | None = None


@dataclass
class LegalEvidencePacket:
    """Evidence collected by the coprocessor for a question."""

    question: LegalQuestion
    retrieval_chunks: list[dict[str, Any]] = field(default_factory=list)
    expanded_chunks: list[dict[str, Any]] = field(default_factory=list)
    prompt: str = ""
    answer: str = ""
    model: str = ""


class LegalWorldCoprocessor:
    """
    World-model coprocessor for legal reasoning.

    The world model contains:
      - Document nodes (statutes, cases, regulations)
      - Chunk nodes (paragraph-level text)
      - Citation/structural edges between chunks

    Retrieval is hybrid: dense vector search over chunks, followed by a
    shallow graph expansion along citation and statutory-structure edges.
    """

    def __init__(
        self,
        world_model: WorldModel | None = None,
        llm_client: LLMClient | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        top_k: int = 4,
        graph_expand: int = 3,
    ):
        self.world_model = world_model or WorldModel(domain="legal")
        self.llm_client = llm_client or LLMClient.from_env()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.graph_expand = graph_expand

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_statute(
        self,
        citation: str,
        title: str,
        text: str,
        tags: list[str] | None = None,
    ) -> list[str]:
        """Chunk a statute and add its chunks plus citation graph edges."""
        doc_id = f"statute::{citation}"
        self.world_model.upsert_node(
            doc_id,
            type="statute",
            label=citation,
            summary=title,
            text=text[:500],
            tags=tags or [],
        )
        chunks = self._chunk(text)
        chunk_ids: list[str] = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}::chunk::{i}"
            self.world_model.upsert_node(
                chunk_id,
                type="chunk",
                label=f"{citation} §{i+1}",
                text=chunk_text,
                source=citation,
                source_type="statute",
                chunk_index=i,
                tags=tags or [],
            )
            self.world_model.add_edge(doc_id, "contains", chunk_id)
            if i > 0:
                self.world_model.add_edge(
                    f"{doc_id}::chunk::{i-1}", "follows", chunk_id
                )
            chunk_ids.append(chunk_id)
        return chunk_ids

    def ingest_case(
        self,
        citation: str,
        title: str,
        text: str,
        tags: list[str] | None = None,
    ) -> list[str]:
        """Chunk a case and add its chunks plus citation edges."""
        doc_id = f"case::{citation}"
        self.world_model.upsert_node(
            doc_id,
            type="case",
            label=citation,
            summary=title,
            text=text[:500],
            tags=tags or [],
        )
        chunks = self._chunk(text)
        chunk_ids: list[str] = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}::chunk::{i}"
            self.world_model.upsert_node(
                chunk_id,
                type="chunk",
                label=f"{citation} p.{i+1}",
                text=chunk_text,
                source=citation,
                source_type="case",
                chunk_index=i,
                tags=tags or [],
            )
            self.world_model.add_edge(doc_id, "contains", chunk_id)
            chunk_ids.append(chunk_id)
        # Heuristic citation edges between cases and statutes.
        self._link_citations(chunk_ids, text)
        return chunk_ids

    def _chunk(self, text: str) -> list[str]:
        """Simple sentence-aware chunking."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            slen = len(sentence)
            if current and current_len + slen > self.chunk_size:
                chunks.append(" ".join(current))
                overlap = []
                overlap_len = 0
                for s in reversed(current):
                    if overlap_len + len(s) > self.chunk_overlap:
                        break
                    overlap.insert(0, s)
                    overlap_len += len(s)
                current = overlap
                current_len = overlap_len
            current.append(sentence)
            current_len += slen
        if current:
            chunks.append(" ".join(current))
        return chunks

    def _link_citations(self, chunk_ids: list[str], text: str) -> None:
        """Link chunks to statute nodes when citations are found in text."""
        statute_ids = [
            node_id
            for node_id, node in self.world_model.nodes.items()
            if node.get("type") == "statute"
        ]
        for chunk_id in chunk_ids:
            chunk_text = self.world_model.nodes[chunk_id].get("text", "")
            for statute_id in statute_ids:
                label = self.world_model.nodes[statute_id].get("label", "")
                if label and label in chunk_text:
                    self.world_model.add_edge(chunk_id, "cites", statute_id)

    def build_index(self) -> None:
        """Build dense vector index over chunks."""
        self.world_model.use_ann = True
        self.world_model.build_index()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_baseline(self, question: LegalQuestion, top_k: int | None = None) -> list[dict[str, Any]]:
        """Plain vector RAG baseline: return top-k chunks."""
        if self.world_model._dirty:
            self.build_index()
        top_k = top_k or self.top_k
        records = self.world_model.retrieve(question.text, top_k=top_k)
        return [
            {
                "node_id": r.node_id,
                "text": self.world_model.nodes[r.node_id].get("text", ""),
                "source": self.world_model.nodes[r.node_id].get("source", ""),
                "score": r.score,
            }
            for r in records
        ]

    def retrieve_octo(self, question: LegalQuestion) -> list[dict[str, Any]]:
        """
        OCTO retrieval: vector top-k + graph expansion along citations and
        statutory structure.
        """
        if self.world_model._dirty:
            self.build_index()

        # 1. Dense seed retrieval.
        seed_records = self.world_model.retrieve(question.text, top_k=self.top_k)
        seen = {r.node_id for r in seed_records}
        collected: list[dict[str, Any]] = [
            {
                "node_id": r.node_id,
                "text": self.world_model.nodes[r.node_id].get("text", ""),
                "source": self.world_model.nodes[r.node_id].get("source", ""),
                "score": float(r.score),
                "origin": "vector",
            }
            for r in seed_records
        ]

        # 2. Graph expansion along edges (cites, contains, follows).
        for r in seed_records:
            for src, rel, dst, _attrs in self.world_model.neighbors(r.node_id):
                neighbor = dst if src == r.node_id else src
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                node = self.world_model.nodes.get(neighbor, {})
                text = node.get("text", "")
                source = node.get("source", "") or node.get("label", "")
                if not text and node.get("summary"):
                    text = node.get("summary")
                collected.append(
                    {
                        "node_id": neighbor,
                        "text": text,
                        "source": source,
                        "score": float(r.score) * 0.85,
                        "origin": f"graph:{rel}",
                    }
                )
                if len(collected) >= self.top_k + self.graph_expand:
                    break
            if len(collected) >= self.top_k + self.graph_expand:
                break

        # Re-rank by lexical overlap with question as a lightweight signal.
        qterms = set(self._tokenize(question.text))
        for item in collected:
            tterms = set(self._tokenize(item["text"]))
            overlap = len(qterms & tterms) / max(len(qterms), 1)
            item["score"] = float(item["score"]) * (1.0 + overlap)
        collected.sort(key=lambda x: x["score"], reverse=True)
        return collected[: self.top_k + self.graph_expand]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z]{3,}", text.lower())

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def answer(
        self,
        question: LegalQuestion,
        *,
        use_graph: bool = True,
    ) -> LegalEvidencePacket:
        """Answer a legal question using the world model."""
        if use_graph:
            evidence = self.retrieve_octo(question)
            method = "OCTO (vector + graph)"
        else:
            evidence = self.retrieve_baseline(question)
            method = "RAG baseline"

        context = "\n\n".join(
            f"[{i+1}] {e['source'] or 'unknown'}\n{e['text']}"
            for i, e in enumerate(evidence)
        )

        options_text = ""
        if question.options:
            options_text = "\nOptions:\n" + "\n".join(
                f"{k}. {v}" for k, v in question.options.items()
            )

        prompt = f"""You are a careful legal research assistant. Answer the following legal question using ONLY the provided legal excerpts.

Question: {question.text}{options_text}

Legal excerpts:
{context}

Instructions:
- Base your answer only on the excerpts above.
- Cite the source numbers [1], [2], etc. that support your answer.
- Keep your answer concise.

Answer:"""

        resp = self.llm_client.complete(prompt, system="You answer legal questions from provided sources only.")
        return LegalEvidencePacket(
            question=question,
            retrieval_chunks=evidence if not use_graph else [],
            expanded_chunks=evidence if use_graph else [],
            prompt=prompt,
            answer=resp.text.strip(),
            model=resp.model,
        )

    def evaluate(
        self,
        questions: list[LegalQuestion],
        *,
        use_graph: bool = True,
    ) -> dict[str, Any]:
        """Run the coprocessor over a question set and report accuracy."""
        correct = 0
        retrieval_correct = 0
        total = 0
        results: list[dict[str, Any]] = []

        for q in questions:
            packet = self.answer(q, use_graph=use_graph)
            pred = self._normalize(packet.answer)
            gold = self._normalize(q.answer)
            is_correct = self._score(pred, gold, q)
            correct += int(is_correct)
            total += 1

            # Retrieval-only recall: does the retrieved evidence contain the answer?
            evidence = packet.expanded_chunks if use_graph else packet.retrieval_chunks
            evidence_text = " ".join(e.get("text", "") for e in evidence).lower()
            retrieval_correct += int(self._retrieval_recall(q, evidence_text))

            results.append(
                {
                    "id": q.id,
                    "question": q.text,
                    "predicted": packet.answer,
                    "expected": q.answer,
                    "correct": is_correct,
                    "retrieval_recall": retrieval_correct > 0,
                    "model": packet.model,
                }
            )

        return {
            "method": "OCTO" if use_graph else "RAG-baseline",
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else 0.0,
            "retrieval_correct": retrieval_correct,
            "retrieval_recall": retrieval_correct / total if total else 0.0,
            "results": results,
        }

    def _retrieval_recall(self, question: LegalQuestion, evidence_text: str) -> bool:
        """Return True if the expected answer is supported by the evidence text."""
        if question.options:
            expected_text = question.options.get(question.answer, "").lower()
            expected_terms = set(self._tokenize(expected_text))
        else:
            expected_terms = set(self._tokenize(question.answer))
        evidence_terms = set(self._tokenize(evidence_text))
        if not expected_terms:
            return False
        overlap = expected_terms & evidence_terms
        return len(overlap) / len(expected_terms) >= 0.5

    @staticmethod
    def _normalize(text: str) -> str:
        """Strip LLM prose to compare answers."""
        text = text.lower()
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return " ".join(text.split())

    def _score(self, predicted: str, expected: str, question: LegalQuestion) -> bool:
        """Score an answer. Supports exact, option-letter, and contains matching."""
        # Option-letter questions.
        if question.options:
            for opt in question.options:
                if re.search(r"\b" + re.escape(opt) + r"\b", predicted):
                    return opt == expected
        # Exact or contains.
        return expected in predicted or predicted in expected
