"""
Drug enforcement world coprocessor.

Builds a structured world model for controlled-substance law enforcement:
  - DEA schedules and controlled substances
  - Chemical/structural classes
  - Federal Register scheduling actions
  - Analogue relationships

The coprocessor answers questions such as:
  - "Is substance X a controlled substance analogue of Y?"
  - "What schedule is substance Z?"
  - "What scheduling action did the DEA take on substance W?"

It compares OCTO (graph + vector grounding) against a plain RAG baseline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from octo.llm_client import LLMClient
from octo.world_state import WorldModel


@dataclass
class DrugEnforcementQuestion:
    """A drug-enforcement reasoning question."""

    id: str
    text: str
    answer: str
    task: str = "analogue_classification"


@dataclass
class DrugEvidencePacket:
    """Evidence collected by the drug-enforcement coprocessor."""

    question: DrugEnforcementQuestion
    evidence: list[dict[str, Any]] = field(default_factory=list)
    prompt: str = ""
    answer: str = ""
    model: str = ""


class DrugEnforcementCoprocessor:
    """
    World-model coprocessor for drug-enforcement / controlled-substance queries.

    Nodes:
      - schedule (e.g., Schedule I)
      - substance (chemical name, common names, schedule, pharmacology, structure)
      - structural_class (e.g., fentanyl analogues, synthetic cannabinoids)
      - scheduling_action (Federal Register notice)

    Edges:
      - substance -> schedule (scheduled_as)
      - substance -> structural_class (belongs_to)
      - substance -> substance (analogue_of)
      - scheduling_action -> substance (schedules)
      - structural_class -> substance (prototypical)
    """

    def __init__(
        self,
        world_model: WorldModel | None = None,
        llm_client: LLMClient | None = None,
        top_k: int = 5,
        graph_expand: int = 4,
    ):
        self.world_model = world_model or WorldModel(domain="drug_enforcement")
        self.llm_client = llm_client or LLMClient.from_env()
        self.top_k = top_k
        self.graph_expand = graph_expand

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_schedule(self, name: str, description: str) -> str:
        node_id = f"schedule::{name}"
        self.world_model.upsert_node(
            node_id,
            type="schedule",
            label=name,
            summary=description,
            text=description,
        )
        return node_id

    def add_substance(
        self,
        name: str,
        common_names: list[str] | None = None,
        schedule: str | None = None,
        structural_class: str | None = None,
        chemical_features: list[str] | None = None,
        pharmacology: str = "",
        description: str = "",
    ) -> str:
        node_id = f"substance::{name}"
        text_parts = [
            description,
            pharmacology,
            "Common names: " + ", ".join(common_names or []),
            "Chemical features: " + ", ".join(chemical_features or []),
        ]
        self.world_model.upsert_node(
            node_id,
            type="substance",
            label=name,
            summary=description,
            text=" ".join(p for p in text_parts if p),
            common_names=common_names or [],
            schedule=schedule,
            structural_class=structural_class,
            chemical_features=chemical_features or [],
            pharmacology=pharmacology,
        )
        if schedule:
            self.world_model.add_edge(node_id, "scheduled_as", f"schedule::{schedule}")
        if structural_class:
            class_id = f"class::{structural_class}"
            self.world_model.upsert_node(
                class_id,
                type="structural_class",
                label=structural_class,
                summary=f"Structural class: {structural_class}",
                text=f"Structural class: {structural_class}",
            )
            self.world_model.add_edge(node_id, "belongs_to", class_id)
        return node_id

    def add_analogue_relationship(self, substance: str, prototype: str) -> None:
        self.world_model.add_edge(
            f"substance::{substance}", "analogue_of", f"substance::{prototype}"
        )

    def add_scheduling_action(
        self,
        action_id: str,
        title: str,
        date: str,
        substance: str,
        action: str,
        legal_basis: str,
        summary: str,
    ) -> str:
        node_id = f"action::{action_id}"
        text = (
            f"Federal Register action: {title}\n"
            f"Date: {date}\n"
            f"Substance: {substance}\n"
            f"Action: {action}\n"
            f"Legal basis: {legal_basis}\n"
            f"Summary: {summary}"
        )
        self.world_model.upsert_node(
            node_id,
            type="scheduling_action",
            label=title,
            summary=summary,
            text=text,
            date=date,
            substance=substance,
            action=action,
            legal_basis=legal_basis,
        )
        self.world_model.add_edge(node_id, "schedules", f"substance::{substance}")
        return node_id

    def build_index(self) -> None:
        self.world_model.use_ann = True
        self.world_model.build_index()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z]{3,}", text.lower())

    def _query_terms(self, text: str) -> set[str]:
        return set(self._tokenize(text))

    def retrieve_baseline(self, question: DrugEnforcementQuestion) -> list[dict[str, Any]]:
        """Plain vector RAG baseline."""
        if self.world_model._dirty:
            self.build_index()
        records = self.world_model.retrieve(question.text, top_k=self.top_k)
        return [
            {
                "node_id": r.node_id,
                "type": self.world_model.nodes[r.node_id].get("type", ""),
                "text": self.world_model.nodes[r.node_id].get("text", ""),
                "score": float(r.score),
                "origin": "vector",
            }
            for r in records
        ]

    def retrieve_octo(self, question: DrugEnforcementQuestion) -> list[dict[str, Any]]:
        """Vector + graph expansion over analogue and scheduling relationships."""
        if self.world_model._dirty:
            self.build_index()

        seed_records = self.world_model.retrieve(question.text, top_k=self.top_k)
        seen = {r.node_id for r in seed_records}
        collected: list[dict[str, Any]] = [
            {
                "node_id": r.node_id,
                "type": self.world_model.nodes[r.node_id].get("type", ""),
                "text": self.world_model.nodes[r.node_id].get("text", ""),
                "score": float(r.score),
                "origin": "vector",
            }
            for r in seed_records
        ]

        # Graph expansion: follow analogue, scheduling, and class edges.
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
                        "type": node.get("type", ""),
                        "text": node.get("text", ""),
                        "score": float(r.score) * 0.9,
                        "origin": f"graph:{rel}",
                    }
                )
                if len(collected) >= self.top_k + self.graph_expand:
                    break
            if len(collected) >= self.top_k + self.graph_expand:
                break

        # Boost substances whose name matches query tokens.
        qterms = self._query_terms(question.text)
        for item in collected:
            node = self.world_model.nodes.get(item["node_id"], {})
            label = node.get("label", "").lower()
            common = " ".join(node.get("common_names", [])).lower()
            name_score = sum(1 for t in qterms if t in label or t in common)
            item["score"] = float(item["score"]) * (1.0 + 0.2 * name_score)

        collected.sort(key=lambda x: x["score"], reverse=True)
        return collected[: self.top_k + self.graph_expand]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def answer(
        self,
        question: DrugEnforcementQuestion,
        *,
        use_graph: bool = True,
    ) -> DrugEvidencePacket:
        """Answer a drug-enforcement question."""
        evidence = self.retrieve_octo(question) if use_graph else self.retrieve_baseline(question)

        context = "\n\n".join(
            f"[{i+1}] {e['type']} {e['node_id']}\n{e['text']}"
            for i, e in enumerate(evidence)
        )

        prompt = f"""You are a DEA legal analyst. Answer the following controlled-substance question using ONLY the provided sources.

Question: {question.text}

Sources:
{context}

Instructions:
- Base your answer only on the sources above.
- Cite the source numbers [1], [2], etc. that support your answer.
- Be concise and state the legal conclusion clearly.

Answer:"""

        resp = self.llm_client.complete(
            prompt,
            system="You answer controlled-substance questions from provided DEA sources only.",
        )
        return DrugEvidencePacket(
            question=question,
            evidence=evidence,
            prompt=prompt,
            answer=resp.text.strip(),
            model=resp.model,
        )

    def evaluate(
        self,
        questions: list[DrugEnforcementQuestion],
        *,
        use_graph: bool = True,
    ) -> dict[str, Any]:
        correct = 0
        retrieval_correct = 0
        total = 0
        results: list[dict[str, Any]] = []

        for q in questions:
            packet = self.answer(q, use_graph=use_graph)
            pred = self._normalize(packet.answer)
            gold = self._normalize(q.answer)
            is_correct = gold in pred or pred in gold
            correct += int(is_correct)
            total += 1

            evidence_text = " ".join(e.get("text", "") for e in packet.evidence).lower()
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

    def _retrieval_recall(self, question: DrugEnforcementQuestion, evidence_text: str) -> bool:
        """Return True if the expected answer is supported by the evidence text."""
        expected_terms = set(self._tokenize(question.answer))
        evidence_terms = set(self._tokenize(evidence_text))
        if not expected_terms:
            return False
        overlap = expected_terms & evidence_terms
        return len(overlap) / len(expected_terms) >= 0.5

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return " ".join(text.split())
