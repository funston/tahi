#!/usr/bin/env python3
"""
Legend, but as a traversal instead of a lookup.

The earlier Legend test asked "what properties does this class have?", which is
a lookup -- one hop, answerable by finding the right file. Search wins that, and
it did. It is not what Legend GraphQL does.

A GraphQL selection set is a walk::

    firm { employees { firstName } }

which chains `Firm -employees-> Person -firstName-> String`. Two hops. That is
the Legend analogue of MetaQA's three-hop questions, and it is where a retriever
has to fetch two separate class definitions and join them itself.

So: give the start class and the value wanted, and ask for the route.

    start       SQLExecutionNode
    wanted      label
    answer      resultColumns.label

The middle hop is the whole test. Nothing in the question names `resultColumns`;
the system has to know that SQLExecutionNode points at SQLResultColumn and that
SQLResultColumn is where `label` lives.

Three arms, same questions, same model:

    plain   the model answers from what it knows
    rag     the five most similar class definitions are pasted into the prompt,
            and the model answers from those. To get it right it must retrieve
            both classes and chain them.
    tahi    the graph is walked from the start class; every route that reaches
            the wanted value is found, and the model picks from those routes.

KNOWN LIMITS OF THIS TEST, stated because the first version of it was invalid:

  * Questions are sampled only where exactly one route reaches the value. TAHI
    then enumerates routes and finds exactly one. **TAHI's exact-match score is
    therefore guaranteed by construction and must not be quoted as a result.**
    It is reported here only as a check that the traversal code works.
  * The measurement that is NOT circular is `path exists`: the model writes a
    path, and the graph says whether it resolves. Nothing about the answer key
    is involved. That is the number worth reading.
  * The RAG arm is given the named start class by exact lookup, plus the k most
    similar classes. Without the exact lookup the start class landed in the
    retrieved set only 20% of the time and the intermediate class 3%, so the
    arm could not have succeeded and the comparison was meaningless.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tahi.graph.legend_model import LegendModel  # noqa: E402

ASK = """A Legend (Pure) data model has a class called {start}.

Starting from {start}, you need to reach a value called '{want}'.
It is NOT a direct property of {start}. It is reached by following one property
of {start} to another class, which has '{want}'.

{context}Reply with ONLY the property path, like: someProperty.{want}

Path:"""

PICK = """A Legend (Pure) data model has a class called {start}.

Starting from {start}, you need to reach a value called '{want}'.

These are the routes through the model that reach it:
{options}

Reply with ONLY the number of the correct route."""


def build_questions(lm: LegendModel, seed: int, n: int) -> list[dict]:
    """Two-hop routes whose destination name is reachable by exactly one route."""
    by_start: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for src, p1, tgt in lm.edges():
        for prop in lm.properties_of_class(tgt):
            if prop.is_primitive:
                by_start[src][prop.name].append(f"{p1}.{prop.name}")

    out = []
    for start, wants in by_start.items():
        direct = set(lm.properties_of(start))
        for want, routes in wants.items():
            uniq = sorted(set(routes))
            if len(uniq) != 1:
                continue            # ambiguous: more than one route reaches it
            if want in direct:
                continue            # also a direct property; not a traversal
            out.append({"start": start, "want": want, "gold": uniq[0]})
    random.Random(seed).shuffle(out)
    return out[:n]


def main() -> int:
    ap = argparse.ArgumentParser(description="Legend two-hop traversal: plain / RAG / TAHI")
    ap.add_argument("--pure-dir", default="data/legend/pure")
    ap.add_argument("--out", default="data/legend/results/legend_multihop.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--max-new", type=int, default=32)
    args = ap.parse_args()

    lm = LegendModel(sorted(Path(args.pure_dir).glob("*.pure")))
    print(f"parsed {len(lm)} classes, {len(lm.edges())} edges", flush=True)

    qs = build_questions(lm, args.seed, args.n)
    print(f"{len(qs)} unambiguous two-hop questions", flush=True)
    if not qs:
        return 1

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessorList

    from tahi.validate.constrained import GraphConstrainedLogits

    print(f"loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    model = model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    eos = tok.eos_token_id

    def gen(prompt: str, allowed: list[str] | None = None) -> str:
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = enc.input_ids.shape[1]
        procs = None
        if allowed:
            proc = GraphConstrainedLogits(tok, allowed, prompt_len=plen,
                                          eos_token_id=eos, min_items=1)
            procs = LogitsProcessorList([proc])
        with torch.no_grad():
            o = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False,
                               pad_token_id=eos, logits_processor=procs)
        return tok.decode(o[0, plen:], skip_special_tokens=True).strip()

    # retrieval index over class definitions, for the RAG arm
    from sentence_transformers import SentenceTransformer
    print("embedding class definitions for the RAG arm ...", flush=True)
    enc_m = SentenceTransformer("BAAI/bge-large-en-v1.5")
    names = sorted(lm.classes)
    docs = [f"{n} has properties: " + ", ".join(
        f"{p.name} ({p.type.split('::')[-1]})" for p in lm.properties_of_class(n))
        for n in names]
    demb = enc_m.encode(docs, normalize_embeddings=True, batch_size=128,
                        show_progress_bar=False).astype(np.float32)
    idx = {nm: j for j, nm in enumerate(names)}

    def retrieve(q: str, k: int) -> str:
        v = enc_m.encode(["Represent this sentence for searching relevant passages: " + q],
                         normalize_embeddings=True).astype(np.float32)[0]
        top = np.argsort(demb @ v)[::-1][:k]
        return "\n".join(docs[j] for j in top)

    def clean(s: str) -> str:
        s = s.strip().split("\n")[0].strip().strip("`'\"")
        return s.split(" ")[0].strip().rstrip(".")

    rows = []
    started = time.perf_counter()
    for i, q in enumerate(qs):
        start, want, gold = q["start"], q["want"], q["gold"]
        short = start.split("::")[-1]

        plain = clean(gen(ASK.format(start=short, want=want, context="")))

        # A real system would look up the class it was handed by name, so give
        # RAG that for free, plus the k most similar classes. Retrieval alone
        # surfaced the start class only 20% of the time.
        ctx_parts = []
        if start in idx:
            ctx_parts.append(docs[idx[start]])
        ctx_parts += [d for d in retrieve(f"{short} {want}", args.top_k).split("\n")
                      if d not in ctx_parts]
        ctx = "\n".join(ctx_parts)
        rag = clean(gen(ASK.format(start=short, want=want,
                                   context="These classes are in the model:\n" + ctx + "\n\n")))

        # TAHI: walk the graph, offer only routes that actually reach `want`
        routes = sorted({f"{p1}.{want}" for p1, tgt in lm.neighbours(start)
                         if want in lm.properties_of(tgt)})
        if len(routes) == 1:
            tahi = routes[0]
        elif routes:
            opts = "\n".join(f"{j+1}. {r}" for j, r in enumerate(routes))
            txt = gen(PICK.format(start=short, want=want, options=opts))
            digits = "".join(c for c in txt if c.isdigit())[:2]
            try:
                k = int(digits) - 1
                tahi = routes[k] if 0 <= k < len(routes) else ""
            except ValueError:
                tahi = ""
        else:
            tahi = ""

        def valid(path: str, _start: str = start) -> bool:
            if not path:
                return False
            ok, _why = lm.validate_path(_start, path.split("."))
            return ok

        rows.append({
            "start": start, "want": want, "gold": gold,
            "plain": plain, "plain_right": plain == gold, "plain_valid": valid(plain),
            "rag": rag, "rag_right": rag == gold, "rag_valid": valid(rag),
            "tahi": tahi, "tahi_right": tahi == gold, "tahi_valid": valid(tahi),
            "n_routes": len(routes),
        })
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(qs)}", flush=True)

    n = len(rows)

    def acc(k):
        return sum(r[k + "_right"] for r in rows) / n

    def val(k):
        return sum(r[k + "_valid"] for r in rows) / n

    print(f"\n{'='*68}\nLEGEND TWO-HOP TRAVERSAL  n={n}  {args.model}\n{'='*68}")
    print(f"{'':38s}{'plain LLM':>11s}{'RAG':>9s}{'TAHI':>9s}")
    print(f"  {'path exists in the model  [VALID]':36s}"
          f"{val('plain'):>11.3f}{val('rag'):>9.3f}{val('tahi'):>9.3f}")
    print(f"  {'path is exactly right     [see note]':36s}"
          f"{acc('plain'):>11.3f}{acc('rag'):>9.3f}{acc('tahi'):>9.3f}")
    print("\n  NOTE: questions were filtered to those with exactly one route, so"
          "\n  TAHI's exact-match score is guaranteed by construction. Do not quote it."
          "\n  The 'path exists' row is the honest measurement.")
    for a, b in (("rag", "tahi"), ("plain", "tahi")):
        t = Counter((r[a + "_right"], r[b + "_right"]) for r in rows)
        fixed, broke = t[(False, True)], t[(True, False)]
        print(f"\n  {a} -> {b}:  fixed {fixed}  ruined {broke}  net {fixed-broke:+d}")
        nn = fixed + broke
        if nn:
            from math import comb
            k = min(fixed, broke)
            p = min(1.0, 2 * sum(comb(nn, j) for j in range(k + 1)) / 2 ** nn)
            print(f"    McNemar exact p = {p:.4f}")
    print(f"\n  wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "model": args.model, "seed": args.seed,
        "task": "two-hop property path from a start class to a named value",
        "accuracy": {k: acc(k) for k in ("plain", "rag", "tahi")},
        "path_exists": {k: val(k) for k in ("plain", "rag", "tahi")},
        "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
