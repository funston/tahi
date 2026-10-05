#!/usr/bin/env python
"""Level 0/1: does retrieval return what the *next* chunk needs?

The question this answers is not "did retrieval find a relevant passage" but
"did it find the passage that lets the model write the next thing" -- the
relation GCCA actually queries at every chunk boundary. MAAILMA measured those
two at 0.649 and 0.218 on one index, and measured a component that moved them in
opposite directions, so they cannot be assumed to track each other.

Item construction is structural, never generated. A MetaQA 3-hop question comes
with a seed entity and an answer set; the path between them is walked in the KB,
so the hop chain cannot fail to hold. (evalgen tried generating multi-hop items
by prompting and removed the type: "make the property the item needs structural,
rather than something the generator has to achieve.")

For a path  E0 -r1- E1 -r2- E2 -r3- E3  three boundary items are emitted:

    boundary 0   query = the question text          target E1   RELEVANCE
    boundary 1   query = the answer prose so far    target E2   CONTINUATION
    boundary 2   query = the answer prose so far    target E3   CONTINUATION

Boundary 0 is question-shaped and boundaries 1+ are continuation-shaped, which is
exactly the split MAAILMA flagged: "the first retrieval fires from the chunk
containing the user's question and is question-like; every retrieval after that
is continuation-like." Reporting them separately is the whole point.

Arms share one dense stage so nothing but the named variable differs:

    flat-A     dense over one-fact passages          (information parity)
    flat-B     dense over one-entity passages        (conservative: hop 1 free)
    graph-B    flat-B + TAHI's edge expansion        (isolates expansion exactly)
    random-A   k passages unrelated to the query     (negative control)
    random-B   ditto over corpus B

Without the random control a non-trivial score proves nothing: if retrieved and
random score alike, cross-attention has nothing to select between and no adapter
can recover it. That is a stop condition before training, not after.

    PYTHONPATH=src .venv/bin/python scripts/eval_continuation.py --limit 200
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.world_state import WorldModel  # noqa: E402
from scripts.build_metaqa_corpus import (  # noqa: E402
    ATTRIBUTE_TAILS,
    FORWARD,
    INVERSE,
    load_triples,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.eval_continuation")

KS = (1, 3, 5, 10)


# --------------------------------------------------------------------------- #
# KB adjacency and path walking
# --------------------------------------------------------------------------- #

def build_adjacency(triples):
    """Undirected adjacency, remembering direction so verbalisation stays correct."""
    adj = defaultdict(list)
    subjects = set()
    for s, r, o in triples:
        subjects.add(s)
        adj[s].append((r, o, True))    # forward: s --r--> o
        adj[o].append((r, s, False))   # inverse
    return adj, subjects


def is_traversable(entity: str, subjects: set, attr_values: set) -> bool:
    """Attribute values (genres, years, languages, tags) are terminal.

    They carry enormous fan-out -- every 1971 film hangs off "1971" -- and no
    MetaQA path routes *through* one. Allowing them as intermediates turns the
    walk into a scan of the corpus and models a hop no question actually asks.
    """
    return entity in subjects or entity not in attr_values


def find_path(start: str, answers: set, adj, subjects, attr_values, max_fanout=400):
    """First 3-hop path from `start` to any answer. Deterministic by sort order."""
    for r1, e1, f1 in sorted(adj.get(start, []))[:max_fanout]:
        if not is_traversable(e1, subjects, attr_values):
            continue
        for r2, e2, f2 in sorted(adj.get(e1, []))[:max_fanout]:
            if e2 == start or not is_traversable(e2, subjects, attr_values):
                continue
            for r3, e3, f3 in sorted(adj.get(e2, []))[:max_fanout]:
                if e3 in answers:
                    return [(start, r1, e1, f1), (e1, r2, e2, f2), (e2, r3, e3, f3)]
    return None


def verbalise(src: str, rel: str, dst: str, forward: bool) -> str:
    """Same templates the corpus uses, so the query reads like the corpus.

    A deliberate choice with a cost: it gives every *text* arm some lexical
    overlap with its own index. The graph arm queries with the identical string,
    so the bias is uniform across arms, but it inflates all absolute numbers and
    they should not be read as deployment recall.
    """
    tmpl = (FORWARD if forward else INVERSE).get(rel)
    if tmpl is None:
        return f"{src} {rel} {dst}."
    return tmpl.format(s=src, o=dst) if forward else tmpl.format(s=dst, o=src)


def build_items(questions, adj, subjects, attr_values, limit, seed=0):
    """One item per boundary. Query at boundary u is what the model would have
    written by then; target is the entity the *next* chunk needs."""
    rng = random.Random(seed)
    pool = list(questions)
    rng.shuffle(pool)

    items, kept = [], 0
    for q in pool:
        if kept >= limit:
            break
        seeds = q.get("q_entity") or []
        if not seeds:
            continue
        path = find_path(seeds[0], set(q.get("answers") or []), adj, subjects, attr_values)
        if path is None:
            continue
        kept += 1

        prose = []
        for u, (src, rel, dst, fwd) in enumerate(path):
            query = q["question"] if u == 0 else " ".join(prose)
            items.append({
                "question_id": q["id"], "boundary": u,
                "relation": "relevance" if u == 0 else "continuation",
                "query": query, "target": dst, "hop_relation": rel,
            })
            prose.append(verbalise(src, rel, dst, fwd))
    log.info("built %d items from %d usable questions", len(items), kept)
    return items


# --------------------------------------------------------------------------- #
# corpora and world models
# --------------------------------------------------------------------------- #

def load_corpus(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CachingEncoder:
    """Memoise embeddings by text.

    `WorldModel._expand` re-encodes every candidate on every query. Without a
    cache the graph arm spends all its time re-embedding the same few thousand
    node texts, and the run is dominated by an artefact of the implementation
    rather than by retrieval.
    """

    def __init__(self, inner):
        self._inner = inner
        self.dimension = inner.dimension
        self._cache: dict[str, np.ndarray] = {}
        self.misses = 0

    def encode(self, texts):
        missing = [t for t in texts if t not in self._cache]
        if missing:
            self.misses += len(missing)
            vecs = np.asarray(self._inner.encode(missing), dtype="float32")
            for t, v in zip(missing, vecs, strict=True):
                self._cache[t] = v
        return np.stack([self._cache[t] for t in texts])


def build_world_model(rows: list[dict], triples, with_edges: bool, attr_values: set) -> WorldModel:
    wm = WorldModel(use_ann=True)
    have = set()
    for r in rows:
        # No label for fact passages: the passage id is not content, and
        # `embedding_text` concatenates the label into the indexed string.
        wm.upsert_node(r["passage_id"], node_type="document", text=r["text"],
                       label=r.get("subject", ""), entities=r["entities"])
        have.add(r["passage_id"])

    if with_edges:
        n = 0
        for s, rel, o in triples:
            if rel in ATTRIBUTE_TAILS:
                continue      # attribute tails live inside the doc, not as edges
            a, b = f"entity::{s}", f"entity::{o}"
            if a in have and b in have:
                wm.add_edge(a, rel, b)
                n += 1
        log.info("graph edges added: %d", n)

    from tahi.retrieval.ann import get_encoder
    wm._encoder = CachingEncoder(get_encoder())
    t0 = time.time()
    wm.build_index()
    log.info("indexed %d passages in %.1fs", len(rows), time.time() - t0)
    return wm


# --------------------------------------------------------------------------- #
# arms
# --------------------------------------------------------------------------- #

def passage_entities(wm: WorldModel, node_ids) -> set:
    out = set()
    for nid in node_ids:
        out.update(wm.nodes.get(nid, {}).get("entities") or ())
    return out


def run_dense(wm: WorldModel, query: str, k: int, expand: bool) -> list[str]:
    return [r.node_id for r in wm.retrieve(query, top_k=k, expand=expand)]


def run_random(wm: WorldModel, query: str, k: int, seed: int = 0) -> list[str]:
    """Deterministic per query, so relevance is the only variable removed."""
    ids = wm._ann_index.node_ids
    digest = hashlib.blake2b(query.encode(), digest_size=8).digest()
    rng = np.random.default_rng(seed ^ int.from_bytes(digest, "little"))
    idx = rng.choice(len(ids), size=min(k, len(ids)), replace=False)
    return [ids[int(i)] for i in idx]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--limit", type=int, default=200, help="questions, not items")
    ap.add_argument("--k", type=int, default=5, help="slot budget, identical for every arm")
    ap.add_argument("--out", default="benchmarks/results/continuation_eval.json")
    args = ap.parse_args()

    triples = load_triples(Path(args.kb))
    adj, subjects = build_adjacency(triples)
    attr_values = {o for _, r, o in triples if r in ATTRIBUTE_TAILS}

    questions = json.loads(Path(args.questions).read_text())
    items = build_items(questions, adj, subjects, attr_values, args.limit)
    if not items:
        log.error("no items built")
        return 1

    corpus_a = load_corpus(Path("data/metaqa/corpus_fact.jsonl"))
    corpus_b = load_corpus(Path("data/metaqa/corpus_entity.jsonl"))
    wm_a = build_world_model(corpus_a, triples, with_edges=False, attr_values=attr_values)
    wm_b = build_world_model(corpus_b, triples, with_edges=True, attr_values=attr_values)

    arms = {
        "flat-A":   lambda q, k: run_dense(wm_a, q, k, expand=False),
        "random-A": lambda q, k: run_random(wm_a, q, k),
        "flat-B":   lambda q, k: run_dense(wm_b, q, k, expand=False),
        "graph-B":  lambda q, k: run_dense(wm_b, q, k, expand=True),
        "random-B": lambda q, k: run_random(wm_b, q, k),
    }
    wm_of = {"flat-A": wm_a, "random-A": wm_a, "flat-B": wm_b,
             "graph-B": wm_b, "random-B": wm_b}

    hits = {a: defaultdict(lambda: defaultdict(int)) for a in arms}
    totals = defaultdict(int)
    kmax = max(KS)

    for i, item in enumerate(items):
        if i % 50 == 0:
            log.info("item %d/%d", i, len(items))
        totals[item["relation"]] += 1
        totals[f"boundary{item['boundary']}"] += 1
        for name, fn in arms.items():
            ids = fn(item["query"], kmax)
            for k in KS:
                if item["target"] in passage_entities(wm_of[name], ids[:k]):
                    hits[name][k][item["relation"]] += 1
                    hits[name][k][f"boundary{item['boundary']}"] += 1

    report = {"n_items": len(items), "k_budget": args.k, "totals": dict(totals),
              "arms": {}}
    for name in arms:
        report["arms"][name] = {
            str(k): {slice_: hits[name][k][slice_] / totals[slice_]
                     for slice_ in totals}
            for k in KS
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print()
    print(f"answer recall  ({len(items)} items, "
          f"{totals['relevance']} relevance / {totals['continuation']} continuation)")
    print("=" * 68)
    print(f"{'arm':<10}" + "".join(f"{'@'+str(k):>8}" for k in KS) + "   relation")
    for slice_ in ("relevance", "continuation"):
        print("-" * 68)
        for name in arms:
            row = "".join(f"{report['arms'][name][str(k)][slice_]:>8.3f}" for k in KS)
            print(f"{name:<10}{row}   {slice_}")
    print("=" * 68)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
