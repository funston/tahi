#!/usr/bin/env python3
"""
Post-generation correction loop.  MetaQA 3-hop.

    prompt -> LLM -> answer
       -> derive a graph query from the question
       -> run it, get the supported entity set
       -> diff the answer against it
       -> if anything in the answer is unsupported, or anything supported is
          missing, hand back exactly what is wrong and ask again
       -> repeat until the answer stops changing, or max rounds

Nothing is retrieved mid-reasoning; the graph is only ever consulted after a complete
answer exists. That is the difference from iterative RAG (KiRAG et al.), which
interleaves retrieval with reasoning to build the answer in the first place.

Conditions, same questions, same model:
    rag        dense retrieval over the KB as text, answer once
    round1     one correction pass  (equivalent to scripts/metaqa_verify.py)
    loop       correct repeatedly until stable

Scoring is exact set equality against the gold entity list. No judge.

KNOWN LIMITATION, stated because it is load-bearing: the relation chain comes from a
few-shot prompt containing three worked examples. An ablation (docs/dashboard.html)
showed those examples carry ~66 of 92 points of retrieval coverage. Enumerating all
9^3 chains and letting the model pick from result sets removes the examples entirely
and scores 0.60 coverage / 0.40 exact -- use --enumerate for that variant.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from metaqa_verify import (  # noqa: E402
    BGE_QUERY,
    CHAIN,
    load_kb,
    norm,
    parse_entities,
    score,
    traverse,
)

RELS = ["starred_actors", "directed_by", "written_by", "has_genre", "has_tags",
        "in_language", "release_year", "has_imdb_rating", "has_imdb_votes"]

ASK = """Answer the question. Reply with ONLY a comma-separated list of entity names.
If you cannot answer, reply exactly: INSUFFICIENT

{context}Question: {q}

Answer:"""

CORRECT = """Question: {q}
Your answer: {ans}

A knowledge graph was checked. Findings:
{findings}

Give a corrected answer. Reply with ONLY a comma-separated list of entity names,
or exactly INSUFFICIENT.

Answer:"""

PICK = """Question: {q}

Each option below is the result of following a different path through a knowledge
graph from the entity in the question. Pick the ONE whose results answer the question.

{opts}

Reply with ONLY the option number."""


def diff(ans: set[str], supported: set[str]) -> str | None:
    """What is wrong with `ans`, given the graph says `supported`. None if nothing."""
    bad = sorted(ans - supported)
    miss = sorted(supported - ans)
    if not bad and not miss:
        return None
    out = []
    if bad:
        out.append(f"- NOT in the graph, remove: {', '.join(bad)}")
    if miss:
        out.append(f"- IN the graph, you omitted: {', '.join(miss)}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Post-generation graph correction loop")
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--out", default="data/metaqa/results/loop_results.json")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--encoder", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--enumerate", action="store_true",
                    help="derive the chain by enumerating all 9^3 paths (no examples)")
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY not set.", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=args.base_url, timeout=120.0, max_retries=3)

    calls = {"n": 0}

    def llm(prompt: str) -> str:
        try:
            r = client.chat.completions.create(
                model=args.model, temperature=0,
                messages=[{"role": "user", "content": prompt}])
            calls["n"] += 1
            return (r.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001
            print(f"  LLM ERROR {type(e).__name__}", file=sys.stderr)
            return ""

    print("loading kb ...", flush=True)
    g, facts = load_kb(Path(args.kb))
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

    all_chains = list(itertools.product(RELS, repeat=3)) if args.enumerate else None

    def supported_set(q) -> set[str]:
        """The graph's answer to this question. Two ways to get the chain."""
        if args.enumerate:
            cands = []
            for ch in all_chains:
                res = traverse(g, q["q_entity"], list(ch), 100000)
                if res:
                    cands.append((ch, res))
            cands.sort(key=lambda x: len(x[1]))
            cands = cands[:40]
            if not cands:
                return set()
            opts = "\n".join(
                f"{i+1}. {' -> '.join(ch)} ({len(r)}): {', '.join(r[:8])}"
                f"{' ...' if len(r) > 8 else ''}" for i, (ch, r) in enumerate(cands))
            txt = llm(PICK.format(q=q["question"], opts=opts))
            digits = "".join(c for c in txt if c.isdigit())[:2]
            try:
                pick = int(digits) - 1
            except ValueError:
                return set()
            return {norm(x) for x in cands[pick][1]} if 0 <= pick < len(cands) else set()
        chain = [c.strip().lower() for c in llm(CHAIN.format(q=q["question"])).split(",")][:3]
        if len(chain) != 3:
            return set()
        return {norm(x) for x in traverse(g, q["q_entity"], chain, 100000)}

    def run(i_q_qe):
        i, q, qe = i_q_qe
        gold = {norm(a) for a in q["answers"]}

        top = np.argsort(demb @ qe)[::-1][: args.top_k]
        ctx = "Context:\n" + "\n".join(docs[j][:600] for j in top) + "\n\n"
        ans = parse_entities(llm(ASK.format(context=ctx, q=q["question"])))
        rag_ans = set(ans)

        sup = supported_set(q)
        history, round1 = [], None
        if sup:
            for rnd in range(args.max_rounds):
                d = diff(ans, sup)
                if d is None:
                    break
                new = parse_entities(llm(CORRECT.format(
                    q=q["question"], ans=", ".join(sorted(ans)) or "(none)", findings=d)))
                history.append({"round": rnd + 1, "findings": d, "answer": sorted(new)})
                if rnd == 0:
                    round1 = set(new)
                if new == ans:
                    break
                ans = new
        if round1 is None:
            round1 = set(rag_ans)

        return {
            "id": q["id"], "question": q["question"], "gold": sorted(gold),
            "n_supported": len(sup), "rounds": len(history),
            "rag": sorted(rag_ans), "rag_status": score(rag_ans, gold),
            "round1": sorted(round1), "round1_status": score(round1, gold),
            "loop": sorted(ans), "loop_status": score(ans, gold),
            "history": history,
        }

    started = time.perf_counter()
    rows = [None] * len(qs)
    with ThreadPoolExecutor(args.concurrency) as ex:
        futs = {ex.submit(run, (i, q, qe)): i for i, (q, qe) in enumerate(zip(qs, qemb, strict=False))}
        done = 0
        for fut in as_completed(futs):
            rows[futs[fut]] = fut.result()
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(qs)}", flush=True)
    rows = [r for r in rows if r]

    def acc(k):
        return sum(1 for r in rows if r[k] == "RIGHT") / len(rows)

    n = len(rows)
    print(f"\n{'='*58}\nMETAQA 3-HOP POST-GENERATION LOOP  n={n}  seed={args.seed}"
          f"{'  [enumerate]' if args.enumerate else '  [few-shot chain]'}\n{'='*58}")
    print(f"  rag                    {acc('rag_status'):.3f}")
    print(f"  + 1 correction round   {acc('round1_status'):.3f}")
    print(f"  + loop to stable       {acc('loop_status'):.3f}")

    for label, key in (("rag -> round1", "round1_status"), ("rag -> loop", "loop_status")):
        t = Counter((r["rag_status"], r[key]) for r in rows)
        fixed = t[("WRONG", "RIGHT")] + t[("MISSING", "RIGHT")]
        broke = t[("RIGHT", "WRONG")] + t[("RIGHT", "MISSING")]
        print(f"\n  {label}:  fixed {fixed}  broken {broke}  net {fixed-broke:+d}")
        nn = fixed + broke
        if nn:
            from math import comb
            k = min(fixed, broke)
            p = min(1.0, 2 * sum(comb(nn, j) for j in range(k + 1)) / 2 ** nn)
            print(f"    McNemar exact p = {p:.4f}")

    rd = Counter(r["rounds"] for r in rows)
    print(f"\n  correction rounds used: {dict(sorted(rd.items()))}")
    print(f"  llm calls {calls['n']}   wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "seed": args.seed, "model": args.model,
        "chain_source": "enumerate" if args.enumerate else "few_shot_examples",
        "max_rounds": args.max_rounds,
        "accuracy": {k: acc(k) for k in ("rag_status", "round1_status", "loop_status")},
        "llm_calls": calls["n"], "rows": rows,
    }, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
