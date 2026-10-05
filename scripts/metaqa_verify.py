#!/usr/bin/env python3
"""
Does a graph check fix wrong answers?  MetaQA 3-hop.

Three conditions, same questions, same model:

    1. closed_book   no context at all
    2. rag           dense retrieval over the KB written out as text
    3. rag_verified  same as (2), then the graph checks the answer and corrects it

The only thing (3) adds over (2) is the graph check. If the graph is worth
anything, previously wrong answers become right.

Why MetaQA: the graph IS the ground truth (nothing is LLM-extracted, so extraction
quality is not a variable), answers are entity lists so scoring is exact set
comparison with no judge, and 3-hop questions need a chain of three facts.

Scoring, per question:
    RIGHT    predicted set == gold set exactly
    WRONG    overlaps or misses
    MISSING  no entities produced, or the model says INSUFFICIENT

Nothing here is hardcoded per question template. The relation chain is proposed by
the model from the 9-relation schema; hardcoding the 150 templates would score ~100%
and prove only that a parser was written.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np

BGE_QUERY = "Represent this sentence for searching relevant passages: "

ASK = """Answer the question. Reply with ONLY a comma-separated list of entity names.
If you cannot answer, reply exactly: INSUFFICIENT

{context}Question: {q}

Answer:"""

CHAIN = """This graph has two kinds of node: MOVIES and everything else.

Relations from a MOVIE:
  starred_actors -> Person      directed_by -> Person      written_by -> Person
  has_genre -> Genre            in_language -> Language    release_year -> Year
  has_tags -> Tag               has_imdb_rating / has_imdb_votes -> value

Traversal is bidirectional, so the SAME relation walks both ways:
  Movie -[starred_actors]-> Person -[starred_actors]-> another Movie

So "movies that SHARE ACTORS with X" is starred_actors, starred_actors.
   "movies that SHARE DIRECTORS with X" is directed_by, directed_by.
   "movies written by the writer of X" is written_by, written_by.

The question starts at a movie and needs exactly 3 steps. The first two steps
usually get you to the related MOVIES; the third reads the property asked for.

Examples:
  "the movies that share actors with X were in which languages"
     -> starred_actors, starred_actors, in_language
  "who directed the movies written by the writer of X"
     -> written_by, written_by, directed_by
  "what genres are the films that share directors with X"
     -> directed_by, directed_by, has_genre

Reply with ONLY the three relation names, comma-separated.

Question: {q}

Chain:"""


FIX = """Your previous answer to a question may be wrong.

Question: {q}
Your answer: {ans}

A knowledge graph was queried and returned these candidate entities:
{cands}

Reply with ONLY a comma-separated list of the correct entities, taken from the
candidates. If the candidates contain nothing relevant, reply exactly: INSUFFICIENT

Answer:"""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def parse_entities(text: str) -> set[str]:
    t = text.strip()
    if not t or "insufficient" in t.lower():
        return set()
    t = re.sub(r"^(answer|entities)\s*:\s*", "", t, flags=re.I)
    return {norm(p) for p in re.split(r"[,\n]", t) if norm(p)}


def score(pred: set[str], gold: set[str]) -> str:
    if not pred:
        return "MISSING"
    return "RIGHT" if pred == gold else "WRONG"


def load_kb(path: Path) -> tuple[nx.MultiDiGraph, dict[str, list[str]]]:
    """Directed multigraph -- an undirected Graph with one `relation` attribute
    silently drops every parallel edge, which is most of this KB."""
    g = nx.MultiDiGraph()
    facts: dict[str, list[str]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        s, r, o = (p.strip() for p in parts)
        g.add_edge(s, o, relation=r)
        g.add_edge(o, s, relation=f"~{r}")          # inverse, for traversal
        facts[s].append(f"{s} {r.replace('_', ' ')} {o}.")
    return g, facts


def hop(g: nx.MultiDiGraph, frontier: set[str], rel: str) -> set[str]:
    out: set[str] = set()
    for n in frontier:
        if n not in g:
            continue
        for _u, v, data in g.out_edges(n, data=True):
            r = data.get("relation", "")
            if r == rel or r == f"~{rel}":
                out.add(v)
    return out


def traverse(g: nx.MultiDiGraph, seeds: list[str], chain: list[str], cap: int) -> list[str]:
    frontier = {s for s in seeds if s in g}
    for rel in chain:
        frontier = hop(g, frontier, rel)
        if not frontier or len(frontier) > 50_000:
            break
    return sorted(frontier - set(seeds))[:cap]


def main() -> int:
    ap = argparse.ArgumentParser(description="Does a graph check fix wrong answers? MetaQA 3-hop")
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--out", default="data/metaqa/results/verify_results.json")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--encoder", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--cand-cap", type=int, default=60)
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY not set.", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=key, timeout=120.0, max_retries=3)

    def llm(prompt: str) -> str:
        try:
            r = client.chat.completions.create(
                model=args.model, temperature=0,
                messages=[{"role": "user", "content": prompt}])
            return (r.choices[0].message.content or "").strip()
        except Exception as e:                      # counted, never fatal
            print(f"  LLM ERROR: {type(e).__name__}", file=sys.stderr)
            return ""

    print("loading kb ...", flush=True)
    g, facts = load_kb(Path(args.kb))
    print(f"  {g.number_of_nodes()} nodes, {g.number_of_edges()} directed edges "
          f"(incl. inverses), {len(facts)} subjects", flush=True)

    # RAG corpus: one text document per subject entity, its facts as sentences.
    # Same information the graph holds -- so any difference is access method,
    # not information content.
    doc_ids = sorted(facts)
    docs = [" ".join(facts[d]) for d in doc_ids]

    from sentence_transformers import SentenceTransformer
    print(f"embedding {len(docs)} docs ...", flush=True)
    st = SentenceTransformer(args.encoder)
    demb = st.encode(docs, normalize_embeddings=True, batch_size=256,
                     show_progress_bar=False).astype(np.float32)

    qs = json.loads(Path(args.questions).read_text())
    qs = random.Random(args.seed).sample(qs, min(args.n, len(qs)))
    qemb = st.encode([BGE_QUERY + q["question"] for q in qs],
                     normalize_embeddings=True, batch_size=64,
                     show_progress_bar=False).astype(np.float32)

    rows = []
    started = time.perf_counter()
    for i, (q, qe) in enumerate(zip(qs, qemb, strict=False)):
        gold = {norm(a) for a in q["answers"]}

        # 1. closed book
        closed = parse_entities(llm(ASK.format(context="", q=q["question"])))

        # 2. rag
        top = np.argsort(demb @ qe)[::-1][: args.top_k]
        ctx = "Context:\n" + "\n".join(docs[j][:600] for j in top) + "\n\n"
        rag = parse_entities(llm(ASK.format(context=ctx, q=q["question"])))

        # 3. rag + graph check
        chain = [c.strip().lower() for c in llm(CHAIN.format(q=q["question"])).split(",")][:3]
        cands = traverse(g, q["q_entity"], chain, args.cand_cap) if len(chain) == 3 else []
        if cands:
            ver = parse_entities(llm(FIX.format(q=q["question"],
                                                ans=", ".join(sorted(rag)) or "(none)",
                                                cands=", ".join(cands))))
        else:
            ver = rag                                # graph had nothing to say

        rows.append({
            "id": q["id"], "question": q["question"], "gold": sorted(gold),
            "chain": chain, "n_candidates": len(cands),
            "closed_book": sorted(closed), "closed_book_status": score(closed, gold),
            "rag": sorted(rag), "rag_status": score(rag, gold),
            "verified": sorted(ver), "verified_status": score(ver, gold),
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(qs)}", flush=True)

    # ---- report ---------------------------------------------------------------
    def acc(k):
        return sum(1 for r in rows if r[k] == "RIGHT") / len(rows)

    trans = Counter((r["rag_status"], r["verified_status"]) for r in rows)
    fixed = trans[("WRONG", "RIGHT")] + trans[("MISSING", "RIGHT")]
    broke = trans[("RIGHT", "WRONG")] + trans[("RIGHT", "MISSING")]

    print(f"\n{'='*58}\nMETAQA 3-HOP  n={len(rows)}  seed={args.seed}\n{'='*58}")
    print(f"  closed_book    {acc('closed_book_status'):.3f}")
    print(f"  rag            {acc('rag_status'):.3f}")
    print(f"  rag_verified   {acc('verified_status'):.3f}")
    print("\n  rag -> rag_verified")
    print(f"{'':14s}{'RIGHT':>8s}{'WRONG':>8s}{'MISSING':>9s}")
    for a in ("RIGHT", "WRONG", "MISSING"):
        print(f"  {a:12s}" + "".join(f"{trans[(a,b)]:>8d}" if b != 'MISSING'
                                     else f"{trans[(a,b)]:>9d}"
                                     for b in ("RIGHT", "WRONG", "MISSING")))
    print(f"\n  fixed by graph  : {fixed}")
    print(f"  broken by graph : {broke}")
    print(f"  net             : {fixed - broke:+d}")

    # McNemar exact, two-sided, on the discordant pair
    n = fixed + broke
    if n:
        from math import comb
        k = min(fixed, broke)
        p = min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n)
        print(f"  McNemar exact p : {p:.4f}  (discordant {fixed} vs {broke})")

    print("\n  published MetaQA 3-hop for reference: GraftNet 77.7, PullNet 91.4, "
          "EmbedKGQA 94.8")
    print(f"  wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": len(rows), "seed": args.seed, "model": args.model,
        "encoder": args.encoder, "top_k": args.top_k, "cand_cap": args.cand_cap,
        "accuracy": {k: acc(k) for k in
                     ("closed_book_status", "rag_status", "verified_status")},
        "transition_rag_to_verified": {f"{a}->{b}": trans[(a, b)]
                                       for a in ("RIGHT", "WRONG", "MISSING")
                                       for b in ("RIGHT", "WRONG", "MISSING")},
        "fixed": fixed, "broken": broke, "net": fixed - broke,
        "rows": rows,
    }, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
