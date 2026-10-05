"""
HotpotQA multi-hop evaluation for TAHI.

Uses the HotpotQA dev set (or a bundled sample) and compares:
  - RAG baseline: vector retrieval over supporting facts
  - TAHI: vector retrieval + graph edges between facts and articles

The world model is built from the provided supporting facts for each question,
so the comparison isolates the value of graph structure over plain retrieval.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tahi.baseline_rag import RAGDocument, StandaloneRAG
from tahi.llm_client import LLMClient
from tahi.world_state import WorldModel


@dataclass
class HotpotQuestion:
    id: str
    text: str
    answer: str
    level: str = ""
    type: str = ""


@dataclass
class HotpotEvidencePacket:
    question: HotpotQuestion
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


class HotpotQACoprocessor:
    """World-model coprocessor for a single HotpotQA question's supporting facts."""

    def __init__(
        self,
        question: HotpotQuestion,
        supporting_facts: list[tuple[str, int, str]],
        llm_client: LLMClient | None = None,
        top_k: int = 5,
        graph_expand: int = 4,
    ):
        self.question = question
        self.llm_client = llm_client or LLMClient.from_env()
        self.top_k = top_k
        self.graph_expand = graph_expand
        self.world_model = WorldModel(domain="hotpotqa")
        self._build_model(supporting_facts)

    def _build_model(self, supporting_facts: list[tuple[str, int, str]]) -> None:
        """
        supporting_facts is a list of (title, sent_id, sentence).
        Builds article nodes and fact-chunk nodes with edges.
        """
        for title, sent_id, sentence in supporting_facts:
            article_id = f"article::{title}"
            self.world_model.upsert_node(
                article_id,
                type="article",
                label=title,
                summary=f"Article: {title}",
                text=title,
            )
            fact_id = f"fact::{title}::{sent_id}"
            self.world_model.upsert_node(
                fact_id,
                type="fact",
                label=f"{title} fact {sent_id}",
                text=sentence,
                source=title,
                sent_id=sent_id,
            )
            self.world_model.add_edge(article_id, "contains", fact_id)

        # Link sequential facts within the same article.
        facts_by_article: dict[str, list[tuple[int, str]]] = {}
        for title, sent_id, sentence in supporting_facts:
            facts_by_article.setdefault(title, []).append((sent_id, sentence))
        for title, facts in facts_by_article.items():
            facts.sort(key=lambda x: x[0])
            for i in range(1, len(facts)):
                prev_id = f"fact::{title}::{facts[i-1][0]}"
                curr_id = f"fact::{title}::{facts[i][0]}"
                self.world_model.add_edge(prev_id, "follows", curr_id)

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
                text = node.get("text", "") or node.get("summary", "")
                collected.append(
                    {
                        "node_id": neighbor,
                        "text": text,
                        "source": node.get("source", "") or node.get("label", ""),
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

    def answer(self) -> HotpotEvidencePacket:
        evidence = self.retrieve()
        context = "\n\n".join(
            f"[{i+1}] {e['source'] or 'unknown'}\n{e['text']}"
            for i, e in enumerate(evidence)
        )
        prompt = f"""Answer the question using only the provided facts.

Question: {self.question.text}

Facts:
{context}

Answer concisely. If the facts do not contain the answer, say "I don't know".

Answer:"""
        resp = self.llm_client.complete(prompt)
        return HotpotEvidencePacket(
            question=self.question,
            evidence=evidence,
            answer=resp.text.strip(),
            model=resp.model,
        )


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


def _coprocessor_documents(coprocessor: HotpotQACoprocessor) -> list[RAGDocument]:
    """Extract raw text documents from the TAHI world model for the RAG baseline."""
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
                    "source": node.get("source", "") or node.get("label", ""),
                },
            )
        )
    return documents


def _resolve_sentences(
    supporting_facts: dict[str, list],
    context: dict[str, list] | None = None,
) -> list[tuple[str, int, str]]:
    """
    Resolve supporting_facts (title + sent_id) to actual sentences.
    Uses provided context if available, otherwise trusts bundled text.
    """
    titles = supporting_facts["title"]
    sent_ids = supporting_facts["sent_id"]

    if context is not None:
        title_to_sents = {
            title: sents for title, sents in zip(context["title"], context["sentences"])
        }
        return [
            (titles[i], int(sent_ids[i]), title_to_sents[titles[i]][int(sent_ids[i])])
            for i in range(len(titles))
        ]

    # Bundled format includes sentence text directly.
    texts = supporting_facts.get("text", [""] * len(titles))
    return [(titles[i], int(sent_ids[i]), texts[i]) for i in range(len(titles))]


def _load_hotpotqa_from_hf(split: str = "validation", max_samples: int | None = None) -> list[dict[str, Any]]:
    from datasets import load_dataset

    ds = load_dataset("hotpot_qa", "distractor", split=split)
    records = []
    for i, item in enumerate(ds):
        if max_samples is not None and i >= max_samples:
            break
        records.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answer": item["answer"],
                "level": item.get("level", ""),
                "type": item.get("type", ""),
                "supporting_facts": dict(item["supporting_facts"]),
                "context": dict(item["context"]),
            }
        )
    return records


def load_hotpotqa_sample(
    path: Path | str | None = None,
    max_samples: int = 50,
) -> list[tuple[HotpotQuestion, list[tuple[str, int, str]]]]:
    """Load a HotpotQA sample. Tries HF first, falls back to bundled JSON."""
    if path is not None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        try:
            data = _load_hotpotqa_from_hf(max_samples=max_samples)
        except Exception:
            bundled = Path(__file__).with_name("data") / "sample_hotpotqa.json"
            if not bundled.exists():
                raise RuntimeError(
                    "Could not load HotpotQA from HuggingFace and no bundled sample exists. "
                    "Install datasets or provide a path."
                )
            data = json.loads(bundled.read_text(encoding="utf-8"))[:max_samples]

    out: list[tuple[HotpotQuestion, list[tuple[str, int, str]]]] = []
    for item in data:
        q = HotpotQuestion(
            id=item["id"],
            text=item["question"],
            answer=item["answer"],
            level=item.get("level", ""),
            type=item.get("type", ""),
        )
        facts = _resolve_sentences(item["supporting_facts"], item.get("context"))
        out.append((q, facts))
    return out


def evaluate_hotpotqa(
    max_samples: int = 50,
    *,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Compare TAHI vs a standalone RAG baseline on HotpotQA supporting facts."""
    samples = load_hotpotqa_sample(max_samples=max_samples)
    llm_client = llm_client or LLMClient.from_env()

    rag_correct = 0
    tahi_correct = 0
    rag_recall = 0
    tahi_recall = 0
    total = 0
    results: list[dict[str, Any]] = []

    for question, facts in samples:
        coprocessor = HotpotQACoprocessor(
            question=question,
            supporting_facts=facts,
            llm_client=llm_client,
        )

        # Standalone RAG baseline over the same raw documents, no graph access.
        rag = StandaloneRAG(top_k=coprocessor.top_k, llm_client=llm_client)
        rag.add_documents(_coprocessor_documents(coprocessor))
        rag.build_index()

        rag_answer_text, rag_model_name, rag_retrievals = rag.answer(
            question.text,
            system='Answer the question using only the provided facts. '
                  'If the facts do not contain the answer, say "I don\'t know".',
        )
        tahi_packet = coprocessor.answer()

        rag_evidence = [
            {"text": r.text, "source": r.metadata.get("source", r.doc_id) if r.metadata else r.doc_id}
            for r in rag_retrievals
        ]

        rag_ok = _score(rag_answer_text, question.answer)
        tahi_ok = _score(tahi_packet.answer, question.answer)
        rag_rec = _retrieval_recall(question.answer, rag_evidence)
        tahi_rec = _retrieval_recall(question.answer, tahi_packet.evidence)

        rag_correct += int(rag_ok)
        tahi_correct += int(tahi_ok)
        rag_recall += int(rag_rec)
        tahi_recall += int(tahi_rec)
        total += 1

        results.append(
            {
                "id": question.id,
                "question": question.text,
                "expected": question.answer,
                "rag_answer": rag_answer_text,
                "tahi_answer": tahi_packet.answer,
                "rag_correct": rag_ok,
                "tahi_correct": tahi_ok,
                "rag_retrieval_recall": rag_rec,
                "tahi_retrieval_recall": tahi_rec,
                "rag_model": rag_model_name,
                "tahi_model": tahi_packet.model,
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
        "tahi": {
            "correct": tahi_correct,
            "total": total,
            "accuracy": tahi_correct / total if total else 0.0,
            "retrieval_correct": tahi_recall,
            "retrieval_recall": tahi_recall / total if total else 0.0,
        },
        "delta": (tahi_correct / total if total else 0.0) - (rag_correct / total if total else 0.0),
        "results": results,
    }
