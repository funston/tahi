#!/usr/bin/env python
"""Graph traversal against ANN retrieval, on items where the graph is guaranteed.

Criteria are in `benchmarks/PREREGISTRATION_graph_vs_ann.md`, written before this
ran. Read them before reading the numbers.

Every arm scores the same items with the same slot budget over the same corpus, so
the only thing that differs between two rows is the named variable. The graph arm
uses `EntityLinker` and the KB adjacency and never touches a cosine — if it ranked
its candidates by embedding similarity it would be the dense arm with extra steps,
which is the mistake `WorldModel._expand` makes and the reason `tahi-expand` is
carried here as a separate row rather than as *the* graph arm.

    PYTHONPATH=src .venv/bin/python scripts/eval_graph_vs_ann.py --limit 400
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.graph.entity_linker import EntityLinker  # noqa: E402
from scripts.build_metaqa_corpus import ATTRIBUTE_TAILS, load_triples  # noqa: E402
from scripts.eval_continuation import (  # noqa: E402
    build_adjacency,
    build_items,
    load_corpus,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.graph_vs_ann")

KS = (1, 3, 5, 10)
KMAX = max(KS)
_WORD = re.compile(r"[a-z0-9]+")


# --------------------------------------------------------------------------- #
# lexical
# --------------------------------------------------------------------------- #

class BM25:
    """Okapi BM25. Included because MAAILMA measured a 1994 algorithm beating the
    neural encoder on this relation (0.5778 against 0.5495), so a graph-vs-ANN
    comparison that omits it is comparing against the weaker baseline."""

    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        lengths = np.zeros(self.n, dtype=np.float32)
        for i, d in enumerate(docs):
            toks = _WORD.findall(d.lower())
            lengths[i] = len(toks)
            tf: dict[str, int] = defaultdict(int)
            for t in toks:
                tf[t] += 1
            for t, c in tf.items():
                self.postings[t].append((i, c))
        self.lengths = lengths
        self.avgdl = float(lengths.mean()) if self.n else 0.0
        self.idf = {t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5))
                    for t, p in self.postings.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n, dtype=np.float32)
        for t in set(_WORD.findall(query.lower())):
            posting = self.postings.get(t)
            if not posting:
                continue
            idx = np.fromiter((i for i, _ in posting), dtype=np.int64, count=len(posting))
            tf = np.fromiter((c for _, c in posting), dtype=np.float32, count=len(posting))
            denom = tf + self.k1 * (1 - self.b + self.b * self.lengths[idx] / self.avgdl)
            out[idx] += self.idf[t] * (tf * (self.k1 + 1)) / denom
        return out


def minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = float(x.min()), float(x.max())
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def topk(scores: np.ndarray, k: int) -> list[int]:
    """Indices of the k highest scores, best first. Ties broken by index, so the
    ranking is deterministic and two arms cannot differ by numpy's tie order."""
    if k >= len(scores):
        idx = np.argsort(-scores, kind="stable")
    else:
        part = np.argpartition(-scores, k)[:k]
        idx = part[np.argsort(-scores[part], kind="stable")]
    return [int(i) for i in idx[:k]]


# --------------------------------------------------------------------------- #
# graph arm
# --------------------------------------------------------------------------- #

class GraphRetriever:
    """Link entities in the query, then take their KB neighbours.

    Ranking is by inverse degree: a neighbour reachable from few nodes is more
    informative than one reachable from thousands, which is the graph's version
    of IDF and the one signal in this arm that no encoder supplies. Nothing here
    reads an embedding.

    Attribute tails (genre, year, language) are excluded as candidates. Every
    1971 film hangs off "1971", so admitting them lets one high-degree node
    consume the whole slot budget while answering nothing.
    """

    def __init__(self, adj, linker: EntityLinker, attr_values: set, id_of: dict):
        self.adj = adj
        self.linker = linker
        self.attr_values = attr_values
        self.id_of = id_of
        self.degree = {e: len(v) for e, v in adj.items()}

    def link(self, query: str) -> list[str]:
        return self.linker.link(query, max_hits=4)

    def candidates(self, query: str) -> tuple[list[str], list[str]]:
        """Returns (linked entities, ranked candidate entities)."""
        linked = self.link(query)
        seen: dict[str, int] = {}
        for e in linked:
            # The linked entity itself is a legitimate candidate: its passage
            # states its own relations, which is exactly the fact the next chunk
            # needs. Ranked first, since a hop away is a guess and this is not.
            seen.setdefault(e, -1)
            for _rel, nb, _fwd in self.adj.get(e, ()):
                if nb in self.attr_values and nb not in self.adj:
                    continue
                d = self.degree.get(nb, 0)
                if nb not in seen or d < seen[nb]:
                    seen[nb] = d
        ranked = sorted(seen, key=lambda e: (seen[e], e))
        return linked, ranked

    def retrieve(self, query: str, k: int) -> list[int]:
        _linked, ranked = self.candidates(query)
        out = []
        for e in ranked:
            i = self.id_of.get(f"entity::{e}")
            if i is not None:
                out.append(i)
            if len(out) >= k:
                break
        return out


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def se(p: float, n: int) -> float:
    return math.sqrt(max(p * (1 - p), 0.0) / n) if n else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--corpus", default="data/metaqa/corpus_entity.jsonl")
    ap.add_argument("--limit", type=int, default=400, help="questions, not items")
    ap.add_argument("--out", default="benchmarks/results/graph_vs_ann.json")
    ap.add_argument("--cache", default="data/metaqa/corpus_entity_emb.npy")
    ap.add_argument("--degrade", choices=("none", "surname", "initial"),
                    default="none",
                    help="Rewrite how entities are NAMED in the query, to test "
                         "whether linking survives text the model wrote rather "
                         "than text the corpus generated. `surname` keeps only "
                         "the last word of a multi-word name (Steven Spielberg "
                         "-> Spielberg); `initial` abbreviates all but the last "
                         "(S. Spielberg). Both are things a model writes "
                         "constantly and neither is a KB surface form.")
    ap.add_argument("--query-window", type=int, default=0,
                    help="Truncate each query to its last N whitespace tokens. "
                         "0 keeps the whole thing. GCCA queries with the last "
                         "`chunk_size` tokens, not with everything written so "
                         "far, so a query built from the full prose always "
                         "contains the seed entity and cannot test linking.")
    args = ap.parse_args()

    triples = load_triples(Path(args.kb))
    adj, subjects = build_adjacency(triples)
    attr_values = {o for _, r, o in triples if r in ATTRIBUTE_TAILS}

    questions = json.loads(Path(args.questions).read_text())
    items = build_items(questions, adj, subjects, attr_values, args.limit)
    if not items:
        log.error("no items built")
        return 1

    if args.degrade != "none":
        # Degrade only the continuation items. Boundary 0 is the dataset's own
        # question and rewriting it would be inventing a benchmark; boundaries
        # 1+ are prose standing in for what the model generates, which is
        # exactly where naming drift happens.
        import re as _re
        # People only. Shortening a person's name is something a model does
        # constantly ("Spielberg", "S. Spielberg"); shortening a film title is
        # not -- nobody calls Catch Me If You Can "Can". Rewriting titles too
        # measures a failure mode that does not occur and makes the linker look
        # worse than it is. Person = tail of a crediting relation, derived from
        # the schema rather than declared.
        _person_rels = {"directed_by", "starred_actors", "written_by"}
        _people = {o for _s, r, o in triples if r in _person_rels}
        _multi = sorted((n for n in _people if len(n.split()) > 1),
                        key=len, reverse=True)
        log.info("degrade pool: %d multi-word person names", len(_multi))

        def _rename(name: str) -> str:
            parts = name.split()
            if args.degrade == "surname":
                return parts[-1]
            return " ".join([p[0] + "." for p in parts[:-1]] + [parts[-1]])

        n_rewritten = 0
        for it in items:
            if it["relation"] != "continuation":
                continue
            q = it["query"]
            for nm in _multi:
                if nm in q:
                    q = q.replace(nm, _rename(nm))
                    n_rewritten += 1
            it["query"] = q
        log.info("degrade=%s: rewrote %d entity mentions in continuation queries",
                 args.degrade, n_rewritten)

    if args.query_window > 0:
        for it in items:
            toks = it["query"].split()
            it["query"] = " ".join(toks[-args.query_window:])
        log.info("queries truncated to last %d tokens", args.query_window)

    rows = load_corpus(Path(args.corpus))
    texts = [r["text"] for r in rows]
    ids = [r["passage_id"] for r in rows]
    id_of = {pid: i for i, pid in enumerate(ids)}
    ent_sets = [set(r["entities"]) for r in rows]
    log.info("corpus: %d passages", len(rows))

    # ---- dense index -------------------------------------------------------
    from tahi.retrieval.ann import get_encoder
    enc = get_encoder()
    cache = Path(args.cache)
    if cache.exists():
        emb = np.load(cache)
        log.info("loaded cached embeddings %s", emb.shape)
    else:
        t0 = time.time()
        emb = np.asarray(enc.encode(texts), dtype="float32")
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, emb)
        log.info("encoded %d passages in %.1fs", len(texts), time.time() - t0)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-12)

    # ---- lexical index -----------------------------------------------------
    t0 = time.time()
    bm25 = BM25(texts)
    log.info("bm25 built in %.1fs (%d terms)", time.time() - t0, len(bm25.postings))

    # ---- graph arm ---------------------------------------------------------
    entity_names = [r["subject"] for r in rows]
    linker = EntityLinker(entity_names)
    graph = GraphRetriever(adj, linker, attr_values, id_of)
    log.info("linker vocabulary: %d surface forms", len(linker))

    # ---- incumbent ---------------------------------------------------------
    from tahi.world_state import WorldModel
    from scripts.eval_continuation import build_world_model
    wm = build_world_model(rows, triples, with_edges=True, attr_values=attr_values)
    assert isinstance(wm, WorldModel)

    # ---- queries encoded once, shared by every dense-consuming arm ---------
    queries = [it["query"] for it in items]
    t0 = time.time()
    q_emb = np.asarray(enc.encode(queries), dtype="float32")
    q_emb /= np.linalg.norm(q_emb, axis=1, keepdims=True).clip(min=1e-12)
    log.info("encoded %d queries in %.1fs", len(queries), time.time() - t0)

    ARMS = ["dense", "bm25", "hybrid", "graph", "graph+hybrid", "graph|hybrid",
            "graph>hybrid", "graph|hybrid>hybrid", "tahi-expand", "random"]
    hits = {a: {m: defaultdict(lambda: defaultdict(int)) for m in ("answer", "target")}
            for a in ARMS}
    totals: dict[str, int] = defaultdict(int)
    diag = {"linked": 0, "target_in_neighbours": 0, "n_candidates": [],
            "linked_by_relation": defaultdict(int)}
    # Reach and rank, split by relation. Pooled reach cannot tell you whether the
    # graph missed the target or merely ordered it badly, and those need different
    # fixes: reach is a traversal problem, rank is a scoring problem.
    reach = defaultdict(int)
    ranks: dict[str, list[int]] = defaultdict(list)
    cands_by_rel: dict[str, list[int]] = defaultdict(list)
    fallback_fires: dict[str, int] = defaultdict(int)

    for i, it in enumerate(items):
        if i % 200 == 0:
            log.info("item %d/%d", i, len(items))
        rel = it["relation"]
        totals[rel] += 1
        target = it["target"]
        target_idx = id_of.get(f"entity::{target}")

        d = emb @ q_emb[i]
        lx = bm25.scores(it["query"])
        hy = minmax(d) + minmax(lx)

        linked, ranked = graph.candidates(it["query"])
        if linked:
            diag["linked"] += 1
            diag["linked_by_relation"][rel] += 1
        diag["n_candidates"].append(len(ranked))
        cands_by_rel[rel].append(len(ranked))
        if target in ranked:
            diag["target_in_neighbours"] += 1
            reach[rel] += 1
            ranks[rel].append(ranked.index(target))

        g_idx = [id_of[f"entity::{e}"] for e in ranked if f"entity::{e}" in id_of][:KMAX]
        h_idx = topk(hy, KMAX)
        # As pre-registered: graph first, hybrid fills what is left. The smoke run
        # showed this degenerates -- the graph produces a median of 16 candidates,
        # so it fills every slot and hybrid never contributes a single one, making
        # this row a duplicate of `graph`. Kept anyway, because it is what was
        # registered and a row that turns out to be a duplicate is a finding.
        gh = list(dict.fromkeys(g_idx + h_idx))[:KMAX]
        # The fusion that was intended: alternate, so each side gets half the
        # budget and neither can crowd the other out.
        interleaved: list[int] = []
        for a, b in zip(g_idx, h_idx, strict=False):
            interleaved += [a, b]
        interleaved += g_idx[len(h_idx):] + h_idx[len(g_idx):]
        g_or_h = list(dict.fromkeys(interleaved))[:KMAX]
        # Fallback: use the graph when it produced anything, ANN when it did not.
        # On full-prose queries this never fires, because linking always succeeds
        # by construction. It is here to be exercised under --query-window, which
        # is the regime the decode loop actually runs in.
        fell_back = not g_idx
        if fell_back:
            fallback_fires[rel] += 1
        g_then_h = h_idx if fell_back else g_idx
        # Same guard over the interleaved fusion rather than over the bare graph.
        g_then_gh = h_idx if fell_back else g_or_h

        digest = hashlib.blake2b(it["query"].encode(), digest_size=8).digest()
        rng = np.random.default_rng(int.from_bytes(digest, "little"))

        picks = {
            "dense": topk(d, KMAX),
            "bm25": topk(lx, KMAX),
            "hybrid": h_idx,
            "graph": g_idx,
            "graph+hybrid": gh,
            "graph|hybrid": g_or_h,
            "graph>hybrid": g_then_h,
            "graph|hybrid>hybrid": g_then_gh,
            "tahi-expand": [id_of[r.node_id] for r in
                            wm.retrieve(it["query"], top_k=KMAX, expand=True,
                                        query_embedding=q_emb[i])
                            if r.node_id in id_of],
            "random": [int(x) for x in rng.choice(len(rows), size=KMAX, replace=False)],
        }

        for arm, idxs in picks.items():
            for k in KS:
                sel = idxs[:k]
                if any(target in ent_sets[j] for j in sel):
                    hits[arm]["answer"][k][rel] += 1
                if target_idx is not None and target_idx in sel:
                    hits[arm]["target"][k][rel] += 1

    n_items = len(items)
    report = {
        "n_items": n_items,
        "n_questions_requested": args.limit,
        "totals": dict(totals),
        "diagnostics": {
            "entity_link_rate": diag["linked"] / n_items,
            "entity_link_rate_by_relation": {
                r: diag["linked_by_relation"][r] / totals[r] for r in totals},
            "target_in_linked_neighbours": diag["target_in_neighbours"] / n_items,
            "graph_candidates_mean": float(np.mean(diag["n_candidates"])),
            "graph_candidates_median": float(np.median(diag["n_candidates"])),
            "graph_candidates_p90": float(np.percentile(diag["n_candidates"], 90)),
            "graph_candidates_le_k": float(np.mean(np.array(diag["n_candidates"]) <= 5)),
            "reach_by_relation": {r: reach[r] / totals[r] for r in totals},
            "fallback_fire_rate": {r: fallback_fires[r] / totals[r] for r in totals},
            "target_rank_by_relation": {
                r: {"median": float(np.median(ranks[r])) if ranks[r] else None,
                    "mean": float(np.mean(ranks[r])) if ranks[r] else None,
                    "p90": float(np.percentile(ranks[r], 90)) if ranks[r] else None}
                for r in totals},
            "candidates_by_relation": {
                r: {"median": float(np.median(cands_by_rel[r])),
                    "mean": float(np.mean(cands_by_rel[r]))}
                for r in totals},
        },
        "arms": {},
    }
    for arm in ARMS:
        report["arms"][arm] = {
            metric: {str(k): {r: hits[arm][metric][k][r] / totals[r] for r in totals}
                     for k in KS}
            for metric in ("answer", "target")
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=float))

    dg = report["diagnostics"]
    print()
    print(f"items: {n_items}  ({totals['relevance']} relevance, "
          f"{totals['continuation']} continuation)   corpus: {len(rows)} passages")
    print()
    print("S1  entity linked in query        "
          f"{dg['entity_link_rate']:.3f}   "
          f"(relevance {dg['entity_link_rate_by_relation'].get('relevance', 0):.3f}, "
          f"continuation {dg['entity_link_rate_by_relation'].get('continuation', 0):.3f})")
    print(f"S2  target among KB neighbours    {dg['target_in_linked_neighbours']:.3f}")
    print(f"S3  candidates per query          median {dg['graph_candidates_median']:.0f}, "
          f"mean {dg['graph_candidates_mean']:.1f}, p90 {dg['graph_candidates_p90']:.0f}, "
          f"fit in k=5: {dg['graph_candidates_le_k']:.3f}")
    print()
    print("fallback fired (graph returned nothing -> ANN):  "
          + ",  ".join(f"{r} {dg['fallback_fire_rate'][r]:.3f}"
                       for r in ("relevance", "continuation")))
    print()
    print("reach vs rank -- is the gap traversal or scoring?")
    print("-" * 60)
    print(f"{'relation':<14}{'reach':>8}{'cands':>8}{'rank med':>10}{'rank p90':>10}")
    for r in ("relevance", "continuation"):
        rk = dg["target_rank_by_relation"][r]
        print(f"{r:<14}{dg['reach_by_relation'][r]:>8.3f}"
              f"{dg['candidates_by_relation'][r]['median']:>8.0f}"
              f"{(rk['median'] if rk['median'] is not None else -1):>10.0f}"
              f"{(rk['p90'] if rk['p90'] is not None else -1):>10.0f}")

    for metric, label in (("answer", "answer recall"), ("target", "target recall")):
        for rel in ("relevance", "continuation"):
            n = totals[rel]
            print()
            print(f"{label} -- {rel}  (n={n})")
            print("-" * 60)
            print(f"{'arm':<14}" + "".join(f"{'@' + str(k):>9}" for k in KS) + f"{'SE@5':>8}")
            for arm in ARMS:
                cells = [report["arms"][arm][metric][str(k)][rel] for k in KS]
                row = "".join(f"{c:>9.3f}" for c in cells)
                print(f"{arm:<14}{row}{se(cells[2], n):>8.3f}")
    print()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
