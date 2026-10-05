#!/usr/bin/env python3
"""
TAHI INSIDE THE GENERATION STEP.  MetaQA 3-hop.

The graph is consulted at every decode step, not before generation and not after it.

    for each token:
        logits = model(...)
        logits = TahiLogitsProcessor(logits)   <-- graph masks what may be emitted
        token  = argmax(logits)

`TahiLogitsProcessor` holds a prefix trie built from the graph's answer set for this
question. At every step it zeroes the logits of every token that cannot continue some
entity in that set. The model physically cannot emit an entity the graph does not
support.

This is decode-loop intervention. No prompt contains the graph result. No second
generation happens. Contrast:

    pre-generation  stuffing   graph text goes in the prompt, generate once
    post-generation loop       generate, diff against graph, re-generate
    IN-GENERATION   (this)     graph constrains logits token by token

Two arms, same local model, same prompt, same questions:
    free          normal generation
    tahi_ingen    identical, plus the graph logits processor

Scoring is exact set equality against the gold entity list. No judge.
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
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metaqa_verify import load_kb, norm, traverse  # noqa: E402

RELS = ["starred_actors", "directed_by", "written_by", "has_genre", "has_tags",
        "in_language", "release_year", "has_imdb_rating", "has_imdb_votes"]

CHAIN_PROMPT = """This graph has MOVIES and other nodes.
Relations from a MOVIE: starred_actors, directed_by, written_by, has_genre,
has_tags, in_language, release_year, has_imdb_rating, has_imdb_votes

The SAME relation walks both ways, so
  Movie -[starred_actors]-> Person -[starred_actors]-> another Movie
"share actors with X" is starred_actors, starred_actors.

Examples:
  "the movies that share actors with X were in which languages"
     -> starred_actors, starred_actors, in_language
  "who directed the movies written by the writer of X"
     -> written_by, written_by, directed_by

Reply with ONLY three relation names, comma-separated.

Question: {q}

Chain:"""

ANSWER_PROMPT = """Answer with ONLY a comma-separated list of names.

{ctx}Question: {q}

Answer:"""


class TahiLogitsProcessor(LogitsProcessor):
    """Constrain generation to a set of strings, enforced token by token.

    A prefix trie over the tokenised allowed strings. At each step the processor
    knows which entity prefixes are still alive given what has been emitted, and
    permits only the tokens that continue one of them (plus the separator once an
    entity is complete, plus EOS).
    """

    def __init__(self, allowed: list[str], tokenizer, prompt_len: int, eos_id: int):
        self.tok = tokenizer
        self.prompt_len = prompt_len
        self.eos_id = eos_id
        self.sep_ids = {tokenizer.encode(",", add_special_tokens=False)[0],
                        tokenizer.encode(", ", add_special_tokens=False)[0]}
        # every allowed string, tokenised both bare and space-prefixed
        self.seqs: list[list[int]] = []
        for a in allowed:
            for form in (a, " " + a):
                ids = tokenizer.encode(form, add_special_tokens=False)
                if ids:
                    self.seqs.append(ids)
        self.n_calls = 0

    def _alive(self, suffix: list[int]) -> set[int]:
        """Tokens that may follow, given `suffix` is a partial entity."""
        nxt: set[int] = set()
        complete = False
        for s in self.seqs:
            if len(s) > len(suffix) and s[: len(suffix)] == suffix:
                nxt.add(s[len(suffix)])
            elif s == suffix:
                complete = True
        if complete or not suffix:
            nxt |= self.sep_ids
            nxt.add(self.eos_id)
        return nxt

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor):
        self.n_calls += 1
        gen = input_ids[0, self.prompt_len:].tolist()
        # split the generated tokens on separators; the tail is the entity in progress
        suffix: list[int] = []
        for t in gen:
            if t in self.sep_ids:
                suffix = []
            else:
                suffix.append(t)
        allowed = self._alive(suffix)
        if not allowed:                      # dead end: only EOS
            allowed = {self.eos_id}
        mask = torch.full_like(scores, float("-inf"))
        idx = torch.tensor(sorted(allowed), device=scores.device)
        mask[0, idx] = scores[0, idx]
        return mask


def main() -> int:
    ap = argparse.ArgumentParser(description="TAHI in the generation step (logit constraint)")
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--out", default="data/metaqa/results/ingen_results.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-new", type=int, default=64)
    ap.add_argument("--cand-cap", type=int, default=40)
    ap.add_argument("--chains-from", default="data/metaqa/results/verify_results.json",
                    help="reuse chains already derived by a stronger model; chain "
                         "derivation is a separate measured step and holding it fixed "
                         "isolates the injection mechanism, which is what this tests")
    args = ap.parse_args()

    print("loading kb ...", flush=True)
    g, _facts = load_kb(Path(args.kb))

    print(f"loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    model = model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    eos = tok.eos_token_id

    def gen(prompt: str, proc=None, max_new=None) -> str:
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = enc.input_ids.shape[1]
        if proc is not None:
            proc.prompt_len = plen
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new or args.max_new,
                                 do_sample=False, pad_token_id=eos,
                                 logits_processor=[proc] if proc else None)
        return tok.decode(out[0, plen:], skip_special_tokens=True).strip()

    qs = random.Random(args.seed).sample(
        json.loads(Path(args.questions).read_text()), args.n)

    cached_chains = {}
    if args.chains_from and Path(args.chains_from).exists():
        for r in json.loads(Path(args.chains_from).read_text())["rows"]:
            if r.get("chain"):
                cached_chains[r["id"]] = r["chain"]
        print(f"  reusing {len(cached_chains)} precomputed chains "
              f"from {args.chains_from}", flush=True)

    rows = []
    started = time.perf_counter()
    for i, q in enumerate(qs):
        gold = {norm(a) for a in q["answers"]}

        # graph answer set for this question
        if q["id"] in cached_chains:
            chain = [c for c in cached_chains[q["id"]] if c in RELS]
        else:
            chain = [c.strip().lower() for c in
                     gen(CHAIN_PROMPT.format(q=q["question"]), max_new=24).split(",")][:3]
            chain = [c for c in chain if c in RELS]
        cands = traverse(g, q["q_entity"], chain, args.cand_cap) if len(chain) == 3 else []

        prompt = ANSWER_PROMPT.format(ctx="", q=q["question"])

        free = gen(prompt)
        free_set = {norm(x) for x in free.split(",") if norm(x)}

        if cands:
            proc = TahiLogitsProcessor(cands, tok, 0, eos)
            ingen = gen(prompt, proc=proc)
        else:
            ingen = free
        ingen_set = {norm(x) for x in ingen.split(",") if norm(x)}

        rows.append({
            "id": q["id"], "question": q["question"], "gold": sorted(gold),
            "chain": chain, "n_candidates": len(cands),
            "free": free[:200], "free_right": free_set == gold,
            "ingen": ingen[:200], "ingen_right": ingen_set == gold,
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(qs)}", flush=True)

    n = len(rows)
    fa = sum(r["free_right"] for r in rows) / n
    ia = sum(r["ingen_right"] for r in rows) / n
    t = Counter((r["free_right"], r["ingen_right"]) for r in rows)
    fixed, broke = t[(False, True)], t[(True, False)]

    print(f"\n{'='*58}\nMETAQA 3-HOP — TAHI IN THE GENERATION STEP  n={n}  {args.model}\n{'='*58}")
    print(f"  free generation              {fa:.3f}")
    print(f"  graph-constrained decoding   {ia:.3f}")
    print(f"\n  fixed {fixed}   broken {broke}   net {fixed-broke:+d}")
    nn = fixed + broke
    if nn:
        from math import comb
        k = min(fixed, broke)
        p = min(1.0, 2 * sum(comb(nn, j) for j in range(k + 1)) / 2 ** nn)
        print(f"  McNemar exact p = {p:.4f}")
    print(f"  wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "model": args.model, "seed": args.seed,
        "mechanism": "logits_processor, decode-loop constraint, no graph text in any prompt",
        "accuracy": {"free": fa, "tahi_ingen": ia},
        "fixed": fixed, "broken": broke, "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
