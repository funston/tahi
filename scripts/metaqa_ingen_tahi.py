#!/usr/bin/env python3
"""
The in-generation experiment, run against the SHIPPED TAHI code.

Identical to scripts/metaqa_ingen.py in questions, seed, model, prompt and
scoring. The only difference is that the graph and the decoder constraint come
from src/tahi/ instead of being reimplemented in this file:

    tahi.graph.metaqa_graph.MetaQAGraph        loading + bidirectional walk
    tahi.validate.constrained.GraphConstrainedLogits   the logit mask

If this reproduces metaqa_ingen.py's 0.21, the shipped implementation is what
was measured. If it does not, the difference is a bug in one of the two and
that is the more important result.

`intervention_rate` is reported because the shipped processor exposes it: the
share of decode steps where the constraint overrode the model's own argmax. Near
zero would mean the constraint was inert and any improvement came from elsewhere.

LOAD-BEARING CAVEAT.  --chains-from reuses relation chains already derived in
data/metaqa/results/verify_results.json.  Those chains came from the few-shot
CHAIN prompt run on gpt-4o-mini, NOT from the 1.5B model doing the generating.
Holding chain derivation fixed is deliberate -- it isolates the injection
mechanism, which is what this script measures -- but it means this arm inherits
the few-shot template dependency, and borrows a stronger model for the query
step.  The number here is therefore an upper bound on what the 1.5B could do
end-to-end on its own.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessorList

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metaqa_verify import norm  # noqa: E402

from tahi.graph.metaqa_graph import MetaQAGraph  # noqa: E402
from tahi.validate.constrained import GraphConstrainedLogits  # noqa: E402

RELS = ["starred_actors", "directed_by", "written_by", "has_genre", "has_tags",
        "in_language", "release_year", "has_imdb_rating", "has_imdb_votes"]

ANSWER_PROMPT = """Answer with ONLY a comma-separated list of names.

Question: {q}

Answer:"""


def chain_endpoints(g: MetaQAGraph, seeds: list[str], chain: list[str],
                    cap: int) -> list[str]:
    """Endpoints of paths whose relation sequence is exactly `chain`.

    Uses MetaQAGraph.walk -- TAHI's traversal, not a local reimplementation.
    `walk` filters by relation *set*, so the ordered chain is enforced here by
    comparing each returned path's relation sequence.
    """
    want = tuple(chain)
    out, seen = [], set()
    for s in seeds:
        for p in g.walk(s, len(chain), allowed_relations=set(chain)):
            if p.hops != len(chain):
                continue
            if tuple(r for r, _n, _b in p.steps) != want:
                continue
            if p.endpoint in seen or p.endpoint in seeds:
                continue
            seen.add(p.endpoint)
            out.append(p.endpoint)
    return sorted(out)[:cap]


def main() -> int:
    ap = argparse.ArgumentParser(description="In-generation constraint, shipped TAHI code")
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--out", default="data/metaqa/results/ingen_tahi_results.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-new", type=int, default=64)
    ap.add_argument("--cand-cap", type=int, default=40)
    ap.add_argument("--chains-from", default="data/metaqa/results/verify_results.json")
    args = ap.parse_args()

    print("loading kb via tahi.graph.metaqa_graph.MetaQAGraph ...", flush=True)
    g = MetaQAGraph(args.kb)
    print(f"  {len(list(g.entities))} entities, {len(g.relations)} relations", flush=True)

    print(f"loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    model = model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    eos = tok.eos_token_id

    def gen(prompt: str, allowed: list[str] | None = None):
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = enc.input_ids.shape[1]
        procs, stats = None, {}
        if allowed:
            p = GraphConstrainedLogits(tok, allowed, prompt_len=plen,
                                       eos_token_id=eos, min_items=1)
            procs = LogitsProcessorList([p])
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False,
                                 pad_token_id=eos, logits_processor=procs)
        if allowed:
            stats = {"intervention_rate": p.intervention_rate,
                     "blocked_steps": p.blocked_steps, "total_steps": p.total_steps}
        return tok.decode(out[0, plen:], skip_special_tokens=True).strip(), stats

    qs = random.Random(args.seed).sample(
        json.loads(Path(args.questions).read_text()), args.n)

    cached = {}
    chains_path = Path(args.chains_from)
    if not chains_path.exists():
        print(f"--chains-from not found: {chains_path}\n"
              f"Run scripts/metaqa_verify.py first, or pass an existing results file.",
              file=sys.stderr)
        return 2
    for r in json.loads(chains_path.read_text())["rows"]:
        if r.get("chain"):
            cached[r["id"]] = r["chain"]
    print(f"  reusing {len(cached)} precomputed chains from {chains_path}", flush=True)

    rows = []
    started = time.perf_counter()
    for i, q in enumerate(qs):
        gold = {norm(a) for a in q["answers"]}
        chain = [c for c in cached.get(q["id"], []) if c in RELS]
        cands = chain_endpoints(g, q["q_entity"], chain, args.cand_cap) if len(chain) == 3 else []

        prompt = ANSWER_PROMPT.format(q=q["question"])
        free, _ = gen(prompt)
        free_set = {norm(x) for x in free.split(",") if norm(x)}

        if cands:
            ingen, st = gen(prompt, allowed=cands)
        else:
            ingen, st = free, {}
        ingen_set = {norm(x) for x in ingen.split(",") if norm(x)}

        rows.append({
            "id": q["id"], "question": q["question"], "gold": sorted(gold),
            "chain": chain, "n_candidates": len(cands),
            "free": free[:200], "free_right": free_set == gold,
            "ingen": ingen[:200], "ingen_right": ingen_set == gold,
            **{f"proc_{k}": v for k, v in st.items()},
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(qs)}", flush=True)

    n = len(rows)
    fa = sum(r["free_right"] for r in rows) / n
    ia = sum(r["ingen_right"] for r in rows) / n
    t = Counter((r["free_right"], r["ingen_right"]) for r in rows)
    fixed, broke = t[(False, True)], t[(True, False)]
    irs = [r["proc_intervention_rate"] for r in rows if "proc_intervention_rate" in r]

    print(f"\n{'='*62}\nMETAQA 3-HOP — IN-GENERATION, SHIPPED TAHI CODE  n={n}\n{'='*62}")
    print(f"  w/o TAHI    {fa:.3f}   (the model answers on its own)")
    print(f"  with TAHI   {ia:.3f}   (same model; TAHI blocks any entity the graph "
          f"does not support)")
    print(f"\n  fixed {fixed}   broken {broke}   net {fixed-broke:+d}")
    if irs:
        print(f"  mean intervention rate       {sum(irs)/len(irs):.3f}  "
              f"(share of decode steps where the graph overrode the model)")
    nn = fixed + broke
    if nn:
        from math import comb
        k = min(fixed, broke)
        p = min(1.0, 2 * sum(comb(nn, j) for j in range(k + 1)) / 2 ** nn)
        print(f"  McNemar exact p = {p:.4f}")
    print(f"  wall clock {time.perf_counter()-started:.0f}s")
    print("\n  compare: scripts/metaqa_ingen.py (my reimplementation) scored 0.000 -> 0.210")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "model": args.model, "seed": args.seed,
        "implementation": "src/tahi -- MetaQAGraph + GraphConstrainedLogits",
        "accuracy": {"without_tahi": fa, "with_tahi": ia},
        "mean_intervention_rate": (sum(irs)/len(irs)) if irs else None,
        "fixed": fixed, "broken": broke, "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
