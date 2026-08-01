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
            keywords=(chemical_features or []) + ([pharmacology] if pharmacology else []),
            aliases=common_names or [],
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

    def retrieve(self, question: DrugEnforcementQuestion) -> list[dict[str, Any]]:
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

        collected.sort(key=lambda x: x["score"], reverse=True)
        return collected[: self.top_k + self.graph_expand]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def answer(self, question: DrugEnforcementQuestion) -> DrugEvidencePacket:
        """Answer a drug-enforcement question using the OCTO world model."""
        evidence = self.retrieve(question)

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

    def evaluate(self, questions: list[DrugEnforcementQuestion]) -> dict[str, Any]:
        """Evaluate the OCTO coprocessor on a list of questions."""
        correct = 0
        retrieval_correct = 0
        total = 0
        results: list[dict[str, Any]] = []

        for q in questions:
            packet = self.answer(q)
            pred = self._normalize(packet.answer)
            gold = self._normalize(q.answer)
            is_correct = self._score(pred, gold, q)
            correct += int(is_correct)
            total += 1

            evidence_text = " ".join(e.get("text", "") for e in packet.evidence).lower()
            rec_ok = self._retrieval_recall(q, evidence_text)
            retrieval_correct += int(rec_ok)

            results.append(
                {
                    "id": q.id,
                    "question": q.text,
                    "predicted": packet.answer,
                    "expected": q.answer,
                    "correct": is_correct,
                    "retrieval_recall": rec_ok,
                    "model": packet.model,
                }
            )

        return {
            "method": "OCTO",
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else 0.0,
            "retrieval_correct": retrieval_correct,
            "retrieval_recall": retrieval_correct / total if total else 0.0,
            "results": results,
        }

    def _retrieval_recall(self, question: DrugEnforcementQuestion, evidence_text: str) -> bool:
        """Return True if the expected answer is supported by the evidence text."""
        evidence = evidence_text.lower()

        # Yes/no analogue questions: evidence must mention both substances and an
        # analogue/similarity signal.
        if question.task == "analogue_classification":
            qtext = question.text.lower()
            m = re.search(r"is (.*) a controlled substance analogue of (.*)\?", qtext)
            if m:
                subj = m.group(1).strip()
                obj = m.group(2).strip()
                has_both = self._has_whole_word(subj, evidence) and self._has_whole_word(obj, evidence)
                has_signal = any(
                    s in evidence
                    for s in ("analogue", "analogous", "structurally similar", "similarity")
                )
                return has_both and has_signal
            return False

        # Schedule questions: the exact schedule must appear as a whole phrase.
        if question.task == "schedule_determination":
            return self._has_whole_word(question.answer.lower(), evidence)

        # Action questions: the substance and action type must appear.
        if question.task == "scheduling_action":
            substance = self._extract_substance_from_action_question(question.text)
            action_lower = question.answer.lower()
            has_substance = bool(substance) and self._has_whole_word(substance, evidence)
            # Extract schedule, e.g. "schedule i" from "Schedule I permanent placement".
            schedule_match = re.search(r"schedule\s+(i+|[iv]+)", action_lower)
            has_schedule = bool(schedule_match) and self._has_whole_word(schedule_match.group(0), evidence)
            has_action_type = any(
                t in evidence for t in ["permanent", "permanently", "temporary", "temporarily"]
            )
            return has_substance and has_schedule and has_action_type

        # Class questions: the class name must appear, allowing singular/plural.
        return self._phrase_match(question.answer.lower(), evidence)

    @staticmethod
    def _extract_substance_from_action_question(text: str) -> str | None:
        """Extract substance name from scheduling-action questions robustly."""
        lowered = text.lower()
        # "What DEA scheduling action was taken on X?"
        m = re.search(r"taken on (.+?)\?", lowered)
        if m:
            return m.group(1).strip()
        # Fallback: last noun phrase before '?'.
        m = re.search(r"\bon\s+(.+?)\?", lowered)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return " ".join(text.split())

    def _score(self, predicted: str, expected: str, question: DrugEnforcementQuestion) -> bool:
        """Score a DEA answer."""
        pred = self._normalize(predicted)
        gold = self._normalize(expected)

        # Yes/no questions: the predicted answer must start with or clearly state
        # the expected word. We extract the first yes/no token to avoid matching
        # "no" inside words like "cannabinoid" or quoted source text.
        if gold in ("yes", "no"):
            first_yes_no = self._extract_first_yes_no(pred)
            return first_yes_no == gold

        # Schedule questions: exact schedule phrase must appear.
        if question.task == "schedule_determination":
            return self._has_whole_word(gold, pred)

        # Action questions: the schedule and placement type must appear.
        if question.task == "scheduling_action":
            parts = gold.split()
            schedule = " ".join(parts[:2])  # e.g. "schedule i"
            placement = parts[2] if len(parts) > 2 else ""
            has_schedule = self._has_whole_word(schedule, pred)
            has_placement = placement in pred or self._adverb_form(placement) in pred
            return has_schedule and has_placement

        # Class / fallback: exact phrase or reasonable containment, with
        # singular/plural tolerance for class names.
        return self._phrase_match(gold, pred) or self._phrase_match(pred, gold)

    @staticmethod
    def _extract_first_yes_no(text: str) -> str | None:
        """Return the first 'yes' or 'no' word in the text, or None."""
        for token in text.split():
            if token in ("yes", "no"):
                return token
        return None

    @staticmethod
    def _adverb_form(word: str) -> str:
        """Return a likely adverb form of a placement noun, without typos."""
        if not word:
            return ""
        if word.endswith("ly"):
            return word
        if word.endswith("y"):
            return word[:-1] + "ily"
        return word + "ly"

    @staticmethod
    def _has_whole_word(needle: str, haystack: str) -> bool:
        """Check that needle appears as a whole-word/phrase in haystack."""
        needle = needle.strip()
        haystack = re.sub(r"[^a-z0-9\s]", " ", haystack.strip())
        if not needle:
            return False
        # Use word boundaries around the phrase.
        pattern = r"(?:^|\s)" + re.escape(needle) + r"(?:\s|$)"
        return bool(re.search(pattern, haystack))

    @classmethod
    def _phrase_match(cls, phrase: str, text: str) -> bool:
        """
        Match a phrase allowing singular/plural inflection.

        Handles cases like "synthetic cannabinoid" vs "synthetic cannabinoids".
        """
        phrase = phrase.strip()
        text = text.strip()
        if not phrase:
            return False
        if cls._has_whole_word(phrase, text):
            return True
        # Try singular form.
        singular = phrase[:-1] if phrase.endswith("s") else phrase
        if singular and cls._has_whole_word(singular, text):
            return True
        # Try plural form.
        plural = phrase + "s" if not phrase.endswith("s") else phrase
        if plural != phrase and cls._has_whole_word(plural, text):
            return True
        return False
