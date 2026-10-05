#!/usr/bin/env python3
"""
Sub-problem ladder: can we get from a QUESTION to the RIGHT DATA in the graph?

No LLM. No generation. No claim extraction. No judging. Those are later rungs and each
one adds a failure surface; testing them together is why the A6 harness produced a number
with four confounded explanations.

    L1  question -> graph entities        does anything resolve at all?
    L2  entities -> edges -> source docs  does the graph point at the RIGHT document?
    L3  ceiling check                     if we link from the GOLD ANSWER instead of the
                                          question, does L2 improve? Separates "the linker
                                          can't bridge question language" from "the graph
                                          doesn't connect these entities to the doc."

L2 is directly comparable to a number we already have: on 2026-08-02, dense retrieval
scored doc_recall 0.4079 on this same structural pool
(`benchmarks/results/enterprise_rag_full.json`). If the graph cannot match that from the
question alone, nothing downstream of it can.

TAHI_PLAN.md §0 observed: no fabricated values, nothing hard-coded, every number
regenerable, exclusions counted.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.validate.fact_validator import GraphFactValidator  # noqa: E402

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

STRUCTURAL_TYPES = {
    "project_related", "constrained", "conflicting_info",
    "completeness", "intra_document_reasoning", "info_not_found",
}


class GraphAdapter:
    """graph.json -> the shape GraphFactValidator expects. Format only, no logic."""

    def __init__(self, graph_path: Path):
        g = json.loads(graph_path.read_text())
        self.nodes = {n["id"]: {"label": n.get("name", n["id"]), "kind": n.get("kind")}
                      for n in g.get("nodes", [])}
        self._adj: dict[str, list] = defaultdict(list)
        self.n_edges = 0
        for e in g.get("edges", []):
            s, r, t = e.get("source"), e.get("relation"), e.get("target")
            if not (s and r and t):
                continue
            attrs = {"source_doc_id": e.get("source_doc_id")}
            self._adj[s].append((s, r, t, attrs))
            self._adj[t].append((t, r, s, attrs))
            self.n_edges += 1

    def neighbors(self, node_id: str):
        return self._adj.get(node_id, [])


def docs_from_entities(graph: GraphAdapter, ents: list[str]) -> Counter:
    """Rank source documents by how many edges the resolved entities touch."""
    c: Counter = Counter()
    for e in ents:
        for _s, _r, _dst, attrs in graph.neighbors(e):
            d = attrs.get("source_doc_id")
            if d:
                c[d] += 1
    return c


def recall_at(ranked: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return float("nan")
    return len(set(ranked[:k]) & gold) / len(gold)


def dense_rank_docs(graph, node_ids, node_emb, q_emb, top_nodes: int):
    """Score nodes by cosine to the question, then weight each node's documents by that
    score. This is the ranking signal `entities_in` cannot provide: it returns a set, so
    every match counts equally and hub nodes dominate by edge count alone.
    """
    import numpy as np
    sims = node_emb @ q_emb
    idx = np.argsort(sims)[::-1][:top_nodes]
    scores = defaultdict(float)
    for i in idx:
        s = float(sims[i])
        if s <= 0:
            continue
        for _s, _r, _dst, attrs in graph.neighbors(node_ids[i]):
            d = attrs.get("source_doc_id")
            if d:
                scores[d] += s
    return [d for d, _ in sorted(scores.items(), key=lambda x: -x[1])]


def main() -> int:
    ap = argparse.ArgumentParser(description="Question->graph->document probe (no LLM)")
    ap.add_argument("--dense", action="store_true",
                    help="add L2-dense: score nodes by embedding cosine instead of substring match")
    ap.add_argument("--encoder", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--top-nodes", type=int, default=20)
    ap.add_argument("--graph", default="data/enterprise_rag/graph_gold/graph.json")
    ap.add_argument("--questions", default="data/enterprise_rag/questions.jsonl")
    ap.add_argument("--out", default="data/enterprise_rag/verify/graph_query_probe.json")
    args = ap.parse_args()

    graph = GraphAdapter(Path(args.graph))
    validator = GraphFactValidator(graph)

    questions = [json.loads(ln) for ln in Path(args.questions).read_text().splitlines() if ln.strip()]
    pool = [q for q in questions
            if q.get("question_type") in STRUCTURAL_TYPES and q.get("expected_doc_ids")]

    print(f"graph: {len(graph.nodes)} nodes, {graph.n_edges} edges, "
          f"{validator.n_aliases} aliases")
    print(f"structural questions with gold docs: {len(pool)}\n")

    rows = []
    for q in pool:
        gold = set(q["expected_doc_ids"])
        out = {"id": q["question_id"], "question_type": q["question_type"],
               "n_gold_docs": len(gold)}
        for label, text in (("q", q["question"]), ("a", q.get("gold_answer", ""))):
            ents = validator.entities_in(text)
            ranked = [d for d, _ in docs_from_entities(graph, ents).most_common()]
            out[f"{label}_n_entities"] = len(ents)
            out[f"{label}_n_docs_reached"] = len(ranked)
            out[f"{label}_any_gold"] = float(bool(set(ranked) & gold))
            for k in (1, 5, 10):
                out[f"{label}_recall@{k}"] = recall_at(ranked, gold, k)
            out[f"{label}_recall@all"] = recall_at(ranked, gold, len(ranked) or 1)
        rows.append(out)

    if args.dense:
        from sentence_transformers import SentenceTransformer
        print(f"\nembedding {len(graph.nodes)} node labels with {args.encoder} ...", flush=True)
        st = SentenceTransformer(args.encoder)
        node_ids = list(graph.nodes)
        labels = [graph.nodes[n].get("label") or n for n in node_ids]
        node_emb = st.encode(labels, normalize_embeddings=True,
                             batch_size=256, show_progress_bar=False)
        # BGE-large-en-v1.5 is ASYMMETRIC: queries take the instruction prefix, documents
        # do not. scripts/run_graphrag_bench_3arm.py:82 already does this; probe_graph_query
        # and run_verify_harness did not, so every dense number measured before this fix
        # used an unprefixed query.
        qp = BGE_QUERY_PREFIX if "bge" in args.encoder.lower() else ""
        q_emb = st.encode([qp + q["question"] for q in pool], normalize_embeddings=True,
                          batch_size=64, show_progress_bar=False)
        for r, q, qe in zip(rows, pool, q_emb, strict=False):
            gold = set(q["expected_doc_ids"])
            ranked = dense_rank_docs(graph, node_ids, node_emb, qe, args.top_nodes)
            r["d_n_docs_reached"] = len(ranked)
            r["d_any_gold"] = float(bool(set(ranked) & gold))
            for k in (1, 5, 10):
                r[f"d_recall@{k}"] = recall_at(ranked, gold, k)
            r["d_recall@all"] = recall_at(ranked, gold, len(ranked) or 1)

    def mean(key):
        v = [r[key] for r in rows if r[key] == r[key]]
        return sum(v) / len(v) if v else float("nan")

    print("L1 — question -> graph entities")
    qe = [r["q_n_entities"] for r in rows]
    print(f"    entities resolved per question: mean {statistics.mean(qe):.1f} "
          f"median {statistics.median(qe):.0f} | zero-entity questions: "
          f"{sum(1 for x in qe if x == 0)}/{len(qe)}")

    print("\nL2 — question -> edges -> source documents")
    print(f"    docs reached per question: mean {mean('q_n_docs_reached'):.1f}")
    for k in (1, 5, 10, "all"):
        print(f"    doc recall@{k:<3}: {mean(f'q_recall@{k}'):.4f}")
    print(f"    any gold doc reached at all: {mean('q_any_gold'):.4f}")
    print("    [dense retrieval baseline, same pool, 2026-08-02: doc_recall 0.4079]")

    print("\nL3 — ceiling: link from the GOLD ANSWER instead of the question")
    ae = [r["a_n_entities"] for r in rows]
    print(f"    entities resolved per answer: mean {statistics.mean(ae):.1f}")
    for k in (1, 5, 10, "all"):
        print(f"    doc recall@{k:<3}: {mean(f'a_recall@{k}'):.4f}")
    print(f"    any gold doc reached at all: {mean('a_any_gold'):.4f}")

    if args.dense:
        print(f"\nL2-DENSE — question -> BGE-scored nodes -> documents (top_nodes={args.top_nodes})")
        print(f"    docs reached per question: mean {mean('d_n_docs_reached'):.1f}")
        for k in (1, 5, 10, "all"):
            print(f"    doc recall@{k:<3}: {mean(f'd_recall@{k}'):.4f}"
                  f"   (lexical was {mean(f'q_recall@{k}'):.4f})")
        print(f"    any gold doc reached at all: {mean('d_any_gold'):.4f}")

    result = {
        "probe": "question -> graph -> document, no LLM",
        "graph_file": args.graph, "n_questions": len(rows),
        "graph_nodes": len(graph.nodes), "graph_edges": graph.n_edges,
        "validator_aliases": validator.n_aliases,
        "dense_baseline_doc_recall_2026_08_02": 0.4079,
        "L1_entities_per_question_mean": statistics.mean(qe),
        "L1_zero_entity_questions": sum(1 for x in qe if x == 0),
        "L2_from_question": {f"recall@{k}": mean(f"q_recall@{k}") for k in (1, 5, 10, "all")}
                            | {"any_gold": mean("q_any_gold"),
                               "docs_reached_mean": mean("q_n_docs_reached")},
        "L3_from_gold_answer": {f"recall@{k}": mean(f"a_recall@{k}") for k in (1, 5, 10, "all")}
                               | {"any_gold": mean("a_any_gold")},
        "L2_dense": ({f"recall@{k}": mean(f"d_recall@{k}") for k in (1, 5, 10, "all")}
                     | {"any_gold": mean("d_any_gold"),
                        "docs_reached_mean": mean("d_n_docs_reached"),
                        "encoder": args.encoder, "top_nodes": args.top_nodes}
                     ) if args.dense else None,
        "per_question": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
