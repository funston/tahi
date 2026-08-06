"""
Generation-time fact validation against a knowledge graph.

This is the piece OCTO was always supposed to have and never did. GCCA is a
*cache*: it makes retrieved vectors available to attention and hopes the model
uses them. It has no concept of a claim being true or false, so it cannot
validate anything. This module does the other thing -- given a span of
generated text, it asks the graph whether that span is SUPPORTED, CONTRADICTED,
or NOT_COVERED.

The answer is a graph lookup, not a judgement. No NLI model, no entailment
score, no learned metric. An edge either exists or it does not. That property
is what makes this measurable without the instruments that produced every
retracted number in this project: `fact_coverage` moved 0.0000 under negation,
and the NLI evaluator scored +0.826 with and without supporting evidence.

What this deliberately does NOT do:

  - It does not judge fluent prose. It resolves entity mentions and checks
    edges. A span with no recognised entity is NOT_COVERED, never SUPPORTED.
  - CONTRADICTED means "the graph asserts a different value for a relation it
    does cover", not "this sentence is false". Open-world absence is
    NOT_COVERED, which is the honest verdict for a graph that is incomplete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional, Sequence


class Verdict(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NOT_COVERED = "not_covered"


@dataclass
class Validation:
    """The result of checking one span against the graph."""

    verdict: Verdict
    span: str
    subject: Optional[str] = None
    relation: Optional[str] = None
    matched_entities: list[str] = field(default_factory=list)
    supporting_edges: list[tuple[str, str, str]] = field(default_factory=list)
    expected_values: list[str] = field(default_factory=list)
    hops: Optional[int] = None

    @property
    def is_valid(self) -> bool:
        """NOT_COVERED is not a failure. A graph that does not know something
        must not be read as asserting its negation."""
        return self.verdict is not Verdict.CONTRADICTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "span": self.span,
            "subject": self.subject,
            "relation": self.relation,
            "matched_entities": list(self.matched_entities),
            "supporting_edges": [list(e) for e in self.supporting_edges],
            "expected_values": list(self.expected_values),
            "hops": self.hops,
        }


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


class GraphFactValidator:
    """Checks generated spans against a `WorldModel`'s edges.

    Entity resolution is longest-match over an alias index built from node
    labels. That is deliberately unclever: an entity is recognised when its
    name appears, and otherwise it is not. A fuzzier matcher would raise recall
    at the cost of making every verdict arguable, and an arguable verdict is
    exactly what this module exists to avoid.
    """

    def __init__(self, world_model: Any, *,
                 label_fields: Sequence[str] = ("label", "name", "title"),
                 min_alias_chars: int = 3):
        self.wm = world_model
        self.min_alias_chars = min_alias_chars
        self._alias_to_node: dict[str, str] = {}
        self._build_alias_index(label_fields)

    # -- entity resolution ---------------------------------------------------

    def _build_alias_index(self, label_fields: Sequence[str]) -> None:
        for node_id, attrs in getattr(self.wm, "nodes", {}).items():
            aliases: list[str] = []
            if isinstance(attrs, dict):
                for f in label_fields:
                    v = attrs.get(f)
                    if isinstance(v, str) and v.strip():
                        aliases.append(v)
                extra = attrs.get("aliases") or attrs.get("synonyms") or []
                if isinstance(extra, (list, tuple)):
                    aliases.extend(a for a in extra if isinstance(a, str))
            # The id's own suffix is a usable alias when it is a readable name
            # (`person::Marco` -> `Marco`), which is how most of this graph's
            # entity nodes are keyed.
            if "::" in node_id:
                aliases.append(node_id.split("::", 1)[1])

            for a in aliases:
                key = _normalise(a)
                if len(key) >= self.min_alias_chars:
                    # First writer wins, so a short generic label cannot
                    # shadow a specific one non-deterministically.
                    self._alias_to_node.setdefault(key, node_id)

    @property
    def n_aliases(self) -> int:
        return len(self._alias_to_node)

    def entities_in(self, text: str) -> list[str]:
        """Node ids whose alias appears in `text`, longest alias first.

        Longest-first prevents `Marco` from matching inside `Marco Rossi` and
        resolving to the wrong node.
        """
        norm = f" {_normalise(text)} "
        found: list[str] = []
        seen: set[str] = set()
        for alias in sorted(self._alias_to_node, key=len, reverse=True):
            if f" {alias} " in norm:
                node_id = self._alias_to_node[alias]
                if node_id not in seen:
                    seen.add(node_id)
                    found.append(node_id)
                norm = norm.replace(f" {alias} ", " ")
        return found

    # -- validation ----------------------------------------------------------

    def _edges_from(self, node_id: str, relation: Optional[str]
                    ) -> list[tuple[str, str, str]]:
        out = []
        for src, rel, dst, _attrs in self.wm.neighbors(node_id):
            if relation is None or str(rel).lower() == relation.lower():
                out.append((src, str(rel), dst))
        return out

    def validate(self, span: str, *, subject: Optional[str] = None,
                 relation: Optional[str] = None,
                 hops: int = 1) -> Validation:
        """Is `span` consistent with the graph?

        `subject` and `relation` scope the check when the caller knows them
        (the usual case: a question generated from an edge). Without them the
        validator can only confirm that the mentioned entities are connected.
        """
        mentioned = self.entities_in(span)

        if subject is None:
            # Unscoped: with fewer than two entities there is no assertion to
            # check, so the honest verdict is NOT_COVERED rather than a guess.
            if len(mentioned) < 2:
                return Validation(Verdict.NOT_COVERED, span,
                                  matched_entities=mentioned)
            head, *rest = mentioned
            for other in rest:
                edges = [e for e in self._edges_from(head, relation)
                         if e[2] == other]
                if edges:
                    return Validation(Verdict.SUPPORTED, span,
                                      subject=head, relation=relation,
                                      matched_entities=mentioned,
                                      supporting_edges=edges, hops=1)
            return Validation(Verdict.NOT_COVERED, span,
                              matched_entities=mentioned)

        # Scoped: the graph's answer for (subject, relation) is authoritative.
        expected_edges = self._edges_from(subject, relation)
        expected = [dst for _s, _r, dst in expected_edges]

        if not expected_edges:
            # The graph does not cover this relation for this subject. Open
            # world: silence is not denial.
            return Validation(Verdict.NOT_COVERED, span, subject=subject,
                              relation=relation, matched_entities=mentioned)

        hit = [e for e in expected_edges if e[2] in mentioned]
        if hit:
            return Validation(Verdict.SUPPORTED, span, subject=subject,
                              relation=relation, matched_entities=mentioned,
                              supporting_edges=hit, expected_values=expected,
                              hops=1)

        # Multi-hop: the span may name something reachable further out. This is
        # where `KuzuGraphStore.expand` earns its place -- it returns support
        # counts and hop distance, which a single-hop adjacency walk cannot.
        if hops > 1 and mentioned:
            reached = self._expand(subject, hops=hops)
            for node_id, _support, min_hops in reached:
                if node_id in mentioned:
                    return Validation(Verdict.SUPPORTED, span, subject=subject,
                                      relation=relation,
                                      matched_entities=mentioned,
                                      supporting_edges=[(subject, relation or "*",
                                                         node_id)],
                                      expected_values=expected,
                                      hops=int(min_hops))

        if mentioned:
            # The span names entities, the graph knows the answer, and they
            # disagree. That is the only case this returns CONTRADICTED.
            return Validation(Verdict.CONTRADICTED, span, subject=subject,
                              relation=relation, matched_entities=mentioned,
                              expected_values=expected)

        return Validation(Verdict.NOT_COVERED, span, subject=subject,
                          relation=relation, matched_entities=mentioned,
                          expected_values=expected)

    def _expand(self, seed: str, *, hops: int) -> list[tuple[str, int, int]]:
        store = getattr(self.wm, "_kuzu_store", None)
        if store is not None:
            try:
                return store.expand([seed], hops=hops, limit=200)
            except Exception:  # noqa: BLE001 -- fall back to the in-memory walk
                pass
        # In-memory BFS with the same return shape.
        seen: dict[str, int] = {seed: 0}
        frontier = [seed]
        for depth in range(1, hops + 1):
            nxt = []
            for nid in frontier:
                for _s, _r, dst, _a in self.wm.neighbors(nid):
                    if dst not in seen:
                        seen[dst] = depth
                        nxt.append(dst)
            frontier = nxt
        return [(n, 1, d) for n, d in seen.items() if d > 0]


def validate_stream(validator: GraphFactValidator, spans: Iterable[str],
                    **kwargs) -> list[Validation]:
    """Validate successive spans of a generation. One call per checkpoint."""
    return [validator.validate(s, **kwargs) for s in spans]
