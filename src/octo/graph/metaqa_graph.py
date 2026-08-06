"""
MetaQA movie knowledge graph — loader and typed multi-hop traversal.

MetaQA ships `kb.txt` as untyped `head|relation|tail` triples over 9 relations.
Entity types are not given, but they are *recoverable from the schema*: whatever
sits in the tail of `in_language` is a Language, whatever sits in the head of
`directed_by` is a Movie. Deriving types this way keeps the loader generic — no
per-dataset table of entity kinds — and gives the planner the typed schema its
narrowing step depends on.

The 9 relations are the whole vocabulary:

    starred_actors  has_tags     written_by   release_year  directed_by
    has_genre       in_language  has_imdb_rating  has_imdb_votes

Traversal is bidirectional. MetaQA's questions require it — "films that share a
director with X" is `X -directed_by-> D <-directed_by- films`, which walks one
edge forward and one backward. A forward-only walk answers almost nothing here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional


@dataclass
class Path_:
    """One route from a start entity to an endpoint."""

    endpoint: str
    hops: int
    steps: list[tuple[str, str, bool]] = field(default_factory=list)
    """(relation, node_reached, followed_backwards)"""

    @property
    def signature(self) -> tuple:
        return tuple((r, back) for r, _n, back in self.steps)


class MetaQAGraph:
    def __init__(self, kb_path: str | Path):
        self.out: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.inn: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.relations: set[str] = set()
        self._head_of: dict[str, set[str]] = defaultdict(set)
        self._tail_of: dict[str, set[str]] = defaultdict(set)

        with open(kb_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 3:
                    continue
                h, r, t = parts
                self.out[h].append((r, t))
                self.inn[t].append((r, h))
                self.relations.add(r)
                self._head_of[h].add(r)
                self._tail_of[t].add(r)

        # Type of an entity = the relation-slot it occupies. A node that is the
        # tail of `in_language` is a Language; a node that heads many relations
        # is a Movie. Derived, not declared.
        self.kind: dict[str, str] = {}
        for e, rels in self._tail_of.items():
            self.kind[e] = self._kind_for_tail(sorted(rels)[0])
        for e in self._head_of:
            # Heads win: in MetaQA every head is a Movie.
            self.kind[e] = "Movie"

    @staticmethod
    def _kind_for_tail(rel: str) -> str:
        """Name the tail type after the relation that produced it."""
        base = re.sub(r"^(has_|in_|release_)", "", rel)
        base = re.sub(r"_by$", "", base)
        base = base.rstrip("s")
        return base.replace("_", " ").title() or rel

    @property
    def entities(self) -> Iterable[str]:
        return self.kind.keys()

    def kinds(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for k in self.kind.values():
            c[k] += 1
        return dict(c)

    def neighbours(self, node: str) -> Iterator[tuple[str, str, bool]]:
        for r, t in self.out.get(node, ()):
            yield r, t, False
        for r, h in self.inn.get(node, ()):
            yield r, h, True

    def walk(self, start: str, max_hops: int = 3, *,
             target_kind: Optional[str] = None,
             allowed_relations: Optional[set[str]] = None,
             node_cap: int = 200_000) -> list[Path_]:
        """All endpoints within `max_hops`, optionally filtered by type.

        Paths never revisit a node, which stops `X -> D -> X` from being counted
        as a two-hop answer to a question about X.
        """
        results: list[Path_] = []
        frontier: list[tuple[str, list, set]] = [(start, [], {start})]
        seen_pairs: set[tuple[str, int]] = set()
        expanded = 0

        for hop in range(1, max_hops + 1):
            nxt: list[tuple[str, list, set]] = []
            for node, steps, visited in frontier:
                for rel, nb, back in self.neighbours(node):
                    if nb in visited:
                        continue
                    if allowed_relations and rel not in allowed_relations:
                        continue
                    expanded += 1
                    if expanded > node_cap:
                        return results
                    new_steps = steps + [(rel, nb, back)]
                    if (nb, hop) not in seen_pairs:
                        seen_pairs.add((nb, hop))
                        if target_kind is None or self.kind.get(nb) == target_kind:
                            results.append(Path_(nb, hop, new_steps))
                    nxt.append((nb, new_steps, visited | {nb}))
            frontier = nxt
        return results

    def answers_at_hop(self, start: str, hops: int, *,
                       target_kind: Optional[str] = None) -> list[str]:
        """Distinct endpoints reachable in EXACTLY `hops` steps.

        MetaQA labels each question with its hop count, so scoring at the stated
        depth avoids crediting a 3-hop question with a 1-hop answer that happens
        to be the right type.
        """
        out, seen = [], set()
        for p in self.walk(start, hops, target_kind=target_kind):
            if p.hops == hops and p.endpoint not in seen:
                seen.add(p.endpoint)
                out.append(p.endpoint)
        return out
