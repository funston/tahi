#!/usr/bin/env python
"""
Ablate the retrieval knobs to separate graph limits from author's choices.

Every constraint in `MetaQAGraph.walk` was a decision, not a property of the
data. This script turns each one off and reports what recall does. Whatever
recall comes back when a knob is disabled was never a limitation of the graph.

Knobs under test:

  target_kind    walk() drops any endpoint whose derived kind != the asked-for
                 kind. A hard drop -- the endpoint cannot be recovered later.
  exact_hop      answers_at_hop keeps only p.hops == hops, discarding answers
                 found at other depths.
  path_dedup     walk() records one path per (node, hop) via `seen_pairs`, so a
                 ranker scoring "the path" only ever sees the first one found,
                 not the best one.
  node_cap       walk() returns early after 200k edge expansions.

Reported metric is recall against gold, with no relation filtering at all, so
each number is a ceiling: no downstream ranker can exceed it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from octo.graph.metaqa_graph import MetaQAGraph  # noqa: E402


def levels(g: MetaQAGraph, start: str, max_hops: int,
           *, allow_revisit: bool, cap: int | None) -> list[set[str]]:
    """Endpoint sets by depth.

    `allow_revisit=False` reproduces shortest-path-only semantics: a node seen
    at depth 2 is never re-reported at depth 3. `allow_revisit=True` lets a node
    appear at several depths, which matters for MetaQA -- "films sharing a
    director" legitimately returns to the movie layer it started from.
    """
    out: list[set[str]] = []
    frontier = {start}
    seen = {start}
    expanded = 0
    for _hop in range(max_hops):
        nxt: set[str] = set()
        for node in frontier:
            for _rel, nb, _back in g.neighbours(node):
                expanded += 1
                if cap is not None and expanded > cap:
                    out.append(nxt)
                    return out
                if not allow_revisit and nb in seen:
                    continue
                nxt.add(nb)
        seen |= nxt
        out.append(nxt)
        frontier = nxt
    return out


def recall(found: set[str], gold: set[str]) -> float:
    return len(found & gold) / len(gold) if gold else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--qa", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("-n", type=int, default=300)
    args = ap.parse_args()

    t0 = time.perf_counter()
    g = MetaQAGraph(args.kb)
    qs = json.loads(Path(args.qa).read_text(encoding="utf-8"))[: args.n]
    print(f"graph loaded in {time.perf_counter()-t0:.1f}s  "
          f"{len(list(g.entities))} entities  {len(g.relations)} relations")
    print(f"questions: {len(qs)}\n")

    # Gold answer kinds, to see how often the target_kind filter can even be right.
    kind_mismatch = 0
    unknown_gold = 0

    acc: dict[str, list[float]] = defaultdict(list)
    for q in qs:
        heads = q.get("q_entity") or []
        if not heads or heads[0] not in g.kind:
            continue
        head = heads[0]
        gold = set(q["answers"])
        hops = q.get("hops", 3)

        gold_kinds = {g.kind.get(a) for a in gold}
        if None in gold_kinds:
            unknown_gold += 1

        # --- as shipped: target_kind filter + exact hop + dedup + cap ---
        tk = next(iter(gold_kinds - {None}), None)  # generous: hand it the true kind
        shipped = set(g.answers_at_hop(head, hops, target_kind=tk))
        acc["as-shipped (typed, exact-hop, capped)"].append(recall(shipped, gold))

        # --- knob: target_kind off ---
        untyped = set(g.answers_at_hop(head, hops, target_kind=None))
        acc["  - target_kind filter off"].append(recall(untyped, gold))

        # --- knob: exact-hop off (union of depths 1..hops), still typed ---
        lv = levels(g, head, hops, allow_revisit=True, cap=200_000)
        upto_typed = {n for s in lv for n in s if tk is None or g.kind.get(n) == tk}
        acc["  - exact-hop off (<= h)"].append(recall(upto_typed, gold))

        # --- knob: node_cap off, exact hop, untyped ---
        lv_nocap = levels(g, head, hops, allow_revisit=True, cap=None)
        acc["  - node_cap off (exact hop)"].append(recall(lv_nocap[hops-1], gold))

        # --- all knobs off: any depth <= h, untyped, uncapped, revisits allowed ---
        every = {n for s in lv_nocap for n in s}
        acc["ALL KNOBS OFF (ceiling)"].append(recall(every, gold))

        # --- shortest-path-only, to show what the dedup semantics cost ---
        lv_sp = levels(g, head, hops, allow_revisit=False, cap=None)
        acc["  (shortest-path-only variant)"].append(recall(lv_sp[hops-1], gold))

        if tk is not None and any(g.kind.get(a) != tk for a in gold):
            kind_mismatch += 1

    n = len(acc["ALL KNOBS OFF (ceiling)"])
    print(f"scored {n} questions "
          f"({len(qs)-n} skipped: head entity not in KB)\n")
    print(f"{'setting':<46}{'recall':>9}")
    print("-" * 55)
    order = ["as-shipped (typed, exact-hop, capped)",
             "  - target_kind filter off",
             "  - exact-hop off (<= h)",
             "  - node_cap off (exact hop)",
             "  (shortest-path-only variant)",
             "ALL KNOBS OFF (ceiling)"]
    for k in order:
        v = acc[k]
        print(f"{k:<46}{sum(v)/len(v)*100:>8.1f}%")
    print()
    print(f"questions where gold spans >1 node kind: {kind_mismatch}/{n}")
    print(f"questions with a gold answer absent from the KB: {unknown_gold}/{n}")
    print(f"wall clock {time.perf_counter()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
