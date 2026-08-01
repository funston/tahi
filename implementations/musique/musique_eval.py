"""
MuSiQue multi-hop evaluation for OCTO.

MuSiQue is a harder multi-hop QA benchmark. Because the full dataset is not on
HuggingFace, this module ships with a small sample and supports loading a local
JSON file in MuSiQue format.

Comparison:
  - RAG baseline: vector retrieval over paragraphs
  - OCTO: vector retrieval + graph edges between paragraphs
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from octo.baseline_rag import RAGDocument, StandaloneRAG
from octo.llm_client import LLMClient
from octo.world_state import WorldModel


@dataclass
class MusiqueQuestion:
    id: str
    text: str
    answer: str


@dataclass
class MusiqueEvidencePacket:
    question: MusiqueQuestion
    evidence: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    model: str = ""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]{3,}", text.lower())


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return " ".join(text.split())


def _score(predicted: str, expected: str) -> bool:
    pred = _normalize(predicted)
    gold = _normalize(expected)
    return gold in pred or pred in gold


def _retrieval_recall(expected: str, evidence: list[dict[str, Any]]) -> bool:
    expected_terms = set(_tokenize(expected))
    if not expected_terms:
        return False
    evidence_text = " ".join(e.get("text", "") for e in evidence)
    evidence_terms = set(_tokenize(evidence_text))
    overlap = expected_terms & evidence_terms
    return len(overlap) / len(expected_terms) >= 0.5


class MusiqueCoprocessor:
    """World-model coprocessor for a single MuSiQue question's paragraphs."""

    def __init__(
        self,
        question: MusiqueQuestion,
        paragraphs: list[dict[str, str]],
        llm_client: LLMClient | None = None,
        top_k: int = 4,
        graph_expand: int = 3,
    ):
        self.question = question
        self.llm_client = llm_client or LLMClient.from_env()
        self.top_k = top_k
        self.graph_expand = graph_expand
        self.world_model = WorldModel(domain="musique")
        self._build_model(paragraphs)

    def _build_model(self, paragraphs: list[dict[str, str]]) -> None:
        for i, para in enumerate(paragraphs):
            title = para.get("title", f"para-{i}")
            text = para.get("paragraph", "")
            para_id = f"para::{title}"
            self.world_model.upsert_node(
                para_id,
                type="paragraph",
                label=title,
                text=text,
                source=title,
                index=i,
            )
            # Link sequential paragraphs with a weak "context" edge.
            if i > 0:
                prev_title = paragraphs[i - 1].get("title", f"para-{i-1}")
                self.world_model.add_edge(
                    f"para::{prev_title}", "context", para_id
                )
        self.world_model.use_ann = True
        self.world_model.build_index()

    def retrieve(self) -> list[dict[str, Any]]:
        seed_records = self.world_model.retrieve(self.question.text, top_k=self.top_k)
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

        for r in seed_records:
            for src, rel, dst, _attrs in self.world_model.neighbors(r.node_id):
                neighbor = dst if src == r.node_id else src
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                node = self.world_model.nodes.get(neighbor, {})
                collected.append(
                    {
                        "node_id": neighbor,
                        "text": node.get("text", ""),
                        "source": node.get("source", ""),
                        "score": float(r.score) * 0.85,
                        "origin": f"graph:{rel}",
                    }
                )
                if len(collected) >= self.top_k + self.graph_expand:
                    break
            if len(collected) >= self.top_k + self.graph_expand:
                break

        collected.sort(key=lambda x: x["score"], reverse=True)
        return collected[: self.top_k + self.graph_expand]

    def answer(self) -> MusiqueEvidencePacket:
        evidence = self.retrieve()
        context = "\n\n".join(
            f"[{i+1}] {e['source'] or 'unknown'}\n{e['text']}"
            for i, e in enumerate(evidence)
        )
        prompt = f"""Answer the question using only the provided paragraphs.

Question: {self.question.text}

Paragraphs:
{context}

Answer concisely. If the paragraphs do not contain the answer, say "I don't know".

Answer:"""
        resp = self.llm_client.complete(prompt)
        return MusiqueEvidencePacket(
            question=self.question,
            evidence=evidence,
            answer=resp.text.strip(),
            model=resp.model,
        )


def _coprocessor_documents(coprocessor: MusiqueCoprocessor) -> list[RAGDocument]:
    """Extract raw text documents from the OCTO world model for the RAG baseline."""
    documents: list[RAGDocument] = []
    for node_id, node in coprocessor.world_model.nodes.items():
        text = node.get("text", "")
        if not text:
            continue
        documents.append(
            RAGDocument(
                doc_id=node_id,
                text=text,
                metadata={
                    "type": node.get("type", ""),
                    "source": node.get("source", ""),
                },
            )
        )
    return documents


def load_musique_sample(path: Path | str | None = None) -> list[tuple[MusiqueQuestion, list[dict[str, str]]]]:
    if path is None:
        path = Path(__file__).with_name("data") / "sample_musique.json"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"MuSiQue sample not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[MusiqueQuestion, list[dict[str, str]]]] = []
    for item in data:
        q = MusiqueQuestion(
            id=item["id"],
            text=item["question"],
            answer=item["answer"],
        )
        out.append((q, item.get("paragraphs", [])))
    return out


def evaluate_musique(
    max_samples: int = 50,
    path: Path | str | None = None,
    *,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    samples = load_musique_sample(path)[:max_samples]
    llm_client = llm_client or LLMClient.from_env()

    rag_correct = 0
    octo_correct = 0
    rag_recall = 0
    octo_recall = 0
    total = 0
    results: list[dict[str, Any]] = []

    for question, paragraphs in samples:
        coprocessor = MusiqueCoprocessor(
            question=question,
            paragraphs=paragraphs,
            llm_client=llm_client,
        )

        # Standalone RAG baseline over the same raw documents, no graph access.
        rag = StandaloneRAG(top_k=coprocessor.top_k, llm_client=llm_client)
        rag.add_documents(_coprocessor_documents(coprocessor))
        rag.build_index()

        rag_answer, _rag_model, rag_retrievals = rag.answer(question.text)
        octo_packet = coprocessor.answer()

        rag_evidence = [
            {
                "text": r.text,
                "source": r.metadata.get("source", "") if r.metadata else "",
            }
            for r in rag_retrievals
        ]

        rag_ok = _score(rag_answer, question.answer)
        octo_ok = _score(octo_packet.answer, question.answer)
        rag_rec = _retrieval_recall(question.answer, rag_evidence)
        octo_rec = _retrieval_recall(question.answer, octo_packet.evidence)

        rag_correct += int(rag_ok)
        octo_correct += int(octo_ok)
        rag_recall += int(rag_rec)
        octo_recall += int(octo_rec)
        total += 1

        results.append(
            {
                "id": question.id,
                "question": question.text,
                "expected": question.answer,
                "rag_answer": rag_answer,
                "octo_answer": octo_packet.answer,
                "rag_correct": rag_ok,
                "octo_correct": octo_ok,
                "rag_retrieval_recall": rag_rec,
                "octo_retrieval_recall": octo_rec,
            }
        )

    return {
        "rag": {
            "correct": rag_correct,
            "total": total,
            "accuracy": rag_correct / total if total else 0.0,
            "retrieval_correct": rag_recall,
            "retrieval_recall": rag_recall / total if total else 0.0,
        },
        "octo": {
            "correct": octo_correct,
            "total": total,
            "accuracy": octo_correct / total if total else 0.0,
            "retrieval_correct": octo_recall,
            "retrieval_recall": octo_recall / total if total else 0.0,
        },
        "delta": (octo_correct / total if total else 0.0) - (rag_correct / total if total else 0.0),
        "results": results,
    }
