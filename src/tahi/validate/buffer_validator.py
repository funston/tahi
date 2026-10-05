"""
Validate a generation buffer against the graph.

Takes what the model has produced so far and answers three questions the model
cannot answer about itself:

    SUPPORTED     this entity is connected to the subject as claimed
    NOT_IN_GRAPH  this entity resolves to a real node, but no such edge exists
    UNLINKED      this text does not name anything the graph knows

plus the one no retrieval system can answer without a graph:

    OMITTED       facts the graph holds that the buffer never mentioned

That last one is the point. An embedding index has no denominator -- it returns
its best k matches and cannot tell you it withheld 17 more. A graph knows the
subject has 22 edges, so it can say the buffer covered 3.

**No language model is used here.** An earlier design asked an LLM to extract
structured claims from the buffer; a probe showed it scored 9/9 on real entities
and 3/9 on invented ones, meaning it was recalling knowledge rather than parsing
grammar -- which makes it circular as a fact-checker. This module uses entity
linking (a standard, measurable component) plus exact edge lookup instead.

Known limit, stated rather than hidden: **polarity is not interpreted.** "X binds
Y" and "X does not bind Y" both mention Y, so both resolve to the same edge and
both report SUPPORTED. Detecting negation scope reliably is a separate problem
with its own error rate; until it is built and measured, callers must treat
SUPPORTED as "the graph contains this edge", not "the sentence is true".
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tahi.validate.linker import EntityLinker, Resolution


class Status(StrEnum):
    SUPPORTED = "supported"
    NOT_IN_GRAPH = "not_in_graph"
    UNLINKED = "unlinked"


@dataclass
class MentionCheck:
    span: str
    status: Status
    resolution: Resolution | None = None
    edge: tuple[str, str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"span": self.span, "status": self.status.value,
                "resolution": self.resolution.to_dict() if self.resolution else None,
                "edge": list(self.edge) if self.edge else None}


@dataclass
class BufferReport:
    """What the graph says about a generation buffer."""

    subject: str | None
    relation: str | None
    mentions: list[MentionCheck] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    graph_facts: list[str] = field(default_factory=list)

    @property
    def supported(self) -> list[MentionCheck]:
        return [m for m in self.mentions if m.status is Status.SUPPORTED]

    @property
    def not_in_graph(self) -> list[MentionCheck]:
        return [m for m in self.mentions if m.status is Status.NOT_IN_GRAPH]

    @property
    def coverage(self) -> float:
        """Share of the graph's facts the buffer actually stated."""
        if not self.graph_facts:
            return 0.0
        return len(self.supported) / len(self.graph_facts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject, "relation": self.relation,
            "n_graph_facts": len(self.graph_facts),
            "n_supported": len(self.supported),
            "n_not_in_graph": len(self.not_in_graph),
            "n_unlinked": sum(1 for m in self.mentions
                              if m.status is Status.UNLINKED),
            "coverage": round(self.coverage, 4),
            "omitted": list(self.omitted),
            "mentions": [m.to_dict() for m in self.mentions],
        }


def candidate_spans(text: str, max_words: int = 4) -> list[str]:
    """Split a buffer into things that might name an entity.

    Comma/semicolon/newline separated items first, since that is how models
    answer list questions. Falls back to short word n-grams for prose.
    """
    parts = [p.strip(" .;:") for p in re.split(r"[,\n;]+", text)]
    parts = [re.sub(r"^\s*[-*\d.)\]]+\s*", "", p).strip() for p in parts]
    out = [p for p in parts if p and len(p.split()) <= max_words]
    if out:
        return out
    words = text.split()
    return [" ".join(words[i:i + 2]) for i in range(len(words) - 1)]


class BufferValidator:
    """Checks a generation buffer against a subject's edges in the graph."""

    def __init__(self, linker: EntityLinker, by_subject: dict, id_to_name: dict):
        self.linker = linker
        self.by_subject = by_subject
        self.id_to_name = id_to_name

    def graph_answer(self, subject_text: str, metaedge: str
                     ) -> tuple[list[str], Resolution | None]:
        """What the graph holds for this subject and relation.

        Resolution runs through the linker, so a paraphrased or misspelled
        subject still finds its node. If it does not resolve, that is returned
        explicitly rather than silently producing an empty answer.
        """
        res = self.linker.resolve(subject_text)
        if not res.resolved:
            return [], res
        targets = self.by_subject.get((res.node_id, metaedge), [])
        return sorted({self.id_to_name[t] for t in targets
                       if t in self.id_to_name}), res

    def validate(self, buffer: str, subject_text: str, metaedge: str
                 ) -> BufferReport:
        facts, subj_res = self.graph_answer(subject_text, metaedge)
        report = BufferReport(
            subject=subj_res.node_id if subj_res and subj_res.resolved else None,
            relation=metaedge, graph_facts=facts,
        )
        if not facts:
            # Nothing to check against. Every mention is UNLINKED by default
            # rather than being reported as wrong.
            for span in candidate_spans(buffer):
                report.mentions.append(MentionCheck(span, Status.UNLINKED))
            return report

        fact_norm = {re.sub(r"[^a-z0-9]+", "", f.lower()): f for f in facts}
        stated: set[str] = set()

        for span in candidate_spans(buffer):
            key = re.sub(r"[^a-z0-9]+", "", span.lower())
            if key in fact_norm:
                name = fact_norm[key]
                stated.add(name)
                report.mentions.append(MentionCheck(
                    span, Status.SUPPORTED,
                    edge=(report.subject or subject_text, metaedge, name)))
                continue
            res = self.linker.resolve(span)
            if res.resolved:
                report.mentions.append(MentionCheck(
                    span, Status.NOT_IN_GRAPH, resolution=res))
            else:
                report.mentions.append(MentionCheck(
                    span, Status.UNLINKED, resolution=res))

        report.omitted = [f for f in facts if f not in stated]
        return report


def summarise(reports: Sequence[BufferReport]) -> dict[str, Any]:
    """Raw counts. No composite score -- a single number is how a broken
    metric hid here for months."""
    tot_facts = sum(len(r.graph_facts) for r in reports)
    tot_sup = sum(len(r.supported) for r in reports)
    return {
        "buffers": len(reports),
        "graph_facts": tot_facts,
        "supported": tot_sup,
        "not_in_graph": sum(len(r.not_in_graph) for r in reports),
        "unlinked": sum(sum(1 for m in r.mentions
                            if m.status is Status.UNLINKED) for r in reports),
        "omitted": sum(len(r.omitted) for r in reports),
        "subject_unresolved": sum(1 for r in reports if r.subject is None),
        "coverage": round(tot_sup / tot_facts, 4) if tot_facts else 0.0,
    }
