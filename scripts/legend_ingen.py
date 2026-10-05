#!/usr/bin/env python3
"""
Does a Legend model stop a model inventing identifiers?  Same shape as MetaQA.

    graph      a Legend/Pure model, parsed from .pure source. Nothing extracted,
               nothing inferred -- this is the same artifact Legend Studio
               round-trips and legend-engine compiles.
    question   "what properties does class X declare?"
    gold       the property list in the source file, inheritance resolved
    arms       WITHOUT TAHI -- the model answers on its own
               WITH TAHI    -- same model, same prompt, but TAHI blocks any
                               token that cannot continue a name the Legend
                               model actually declares

The constraint is NOT the answer.  The allowed set is every property name
declared anywhere in the whole model -- 560 of them -- so the model still has to
pick the right handful.  Constraining to the target class's own properties would
be an oracle and would prove nothing.

Two numbers:

    exact set match      did it name exactly the right properties
    fabrication rate     share of emitted identifiers that exist nowhere in the
                         model.  This is the number that matters: it is the
                         failure a reranker or a fine-tune cannot reach, because
                         it happens at decode time.

Scoring is exact set comparison against the parsed source. No LLM judge.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessorList

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tahi.graph.legend_model import LegendModel  # noqa: E402
from tahi.validate.constrained import GraphConstrainedLogits  # noqa: E402

PROMPT = """This is a Legend (Pure) data model.

Class: {cls}

List the property names this class declares. Reply with ONLY a comma-separated
list of property names, nothing else.

Properties:"""

# The RAG arm: the retriever finds the most similar classes and pastes their
# definitions into the prompt. That is what a retrieval system does, and it is
# the fair middle comparison -- the model is given real material, but nothing
# stops it ignoring that material and writing whatever it likes.
RAG_PROMPT = """This is a Legend (Pure) data model. Here are some classes from it:

{context}

Class: {cls}

List the property names this class declares. Reply with ONLY a comma-separated
list of property names, nothing else.

Properties:"""


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s.strip())


def parse_names(text: str) -> list[str]:
    text = text.strip().split("\n")[0]
    return [norm(x) for x in text.split(",") if norm(x)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Legend model as a decode-time constraint")
    ap.add_argument("--pure-dir", default="data/legend/pure")
    ap.add_argument("--out", default="data/legend/results/legend_ingen.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-props", type=int, default=3)
    ap.add_argument("--classes-file", default=None,
                    help="newline-separated class names to test instead of a "
                         "random sample; used to cover exactly the classes the "
                         "graph viewer displays")
    ap.add_argument("--max-new", type=int, default=96)
    ap.add_argument("--top-k", type=int, default=5,
                    help="classes the RAG arm retrieves into the prompt")
    args = ap.parse_args()

    print("parsing Legend model ...", flush=True)
    lm = LegendModel(sorted(Path(args.pure_dir).glob("*.pure")))

    # The protocol metamodel ships once per released version. Keep the newest so
    # the same class is not counted ten times.
    vers = {m.group(0) for k in lm.classes
            if (m := re.search(r"v\d+_\d+_\d+", k))}
    newest = max(vers, key=lambda v: tuple(int(x) for x in v[1:].split("_")))
    classes = {k: c for k, c in lm.classes.items()
               if newest in k or not re.search(r"v\d+_\d+_\d+", k)}
    lm.classes = classes

    vocab = sorted(lm.property_vocabulary)
    print(f"  {len(classes)} classes, {len(vocab)} distinct property names "
          f"(protocol metamodel pinned to {newest})", flush=True)

    if args.classes_file:
        want = [ln.strip() for ln in Path(args.classes_file).read_text().splitlines()
                if ln.strip()]
        pool = [k for k in want if k in classes and len(lm.properties_of(k)) >= args.min_props]
        qs = pool[:args.n] if args.n < len(pool) else pool
    else:
        pool = [k for k, c in classes.items()
                if len(lm.properties_of(k)) >= args.min_props]
        qs = random.Random(args.seed).sample(pool, min(args.n, len(pool)))
    print(f"  {len(pool)} classes with >= {args.min_props} properties, "
          f"sampled {len(qs)}", flush=True)

    print(f"loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    model = model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    eos = tok.eos_token_id

    def gen(prompt: str, allowed: list[str] | None = None):
        """Returns (text, stats, truncated).

        `truncated` is True when generation stopped on the token budget rather
        than on EOS. The final item is then a partial identifier, and counting it
        as a fabrication would be a measurement artifact rather than a model
        error -- so the caller drops it.
        """
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = enc.input_ids.shape[1]
        procs, stats = None, {}
        if allowed:
            proc = GraphConstrainedLogits(tok, allowed, prompt_len=plen,
                                          eos_token_id=eos, min_items=1)
            procs = LogitsProcessorList([proc])
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False,
                                 pad_token_id=eos, logits_processor=procs)
        new = out[0, plen:]
        truncated = len(new) >= args.max_new and int(new[-1]) != eos
        if allowed:
            stats = {"intervention_rate": proc.intervention_rate}
        return tok.decode(new, skip_special_tokens=True).strip(), stats, truncated

    # --- retrieval index for the RAG arm ---------------------------------
    from sentence_transformers import SentenceTransformer
    print("embedding class definitions for the RAG arm ...", flush=True)
    enc = SentenceTransformer("BAAI/bge-large-en-v1.5")
    cls_names = sorted(classes)
    cls_docs = [f"{n} has properties: " + ", ".join(lm.properties_of(n))
                for n in cls_names]
    import numpy as np
    demb = enc.encode(cls_docs, normalize_embeddings=True, batch_size=128,
                      show_progress_bar=False).astype(np.float32)

    def retrieve(cls: str, k: int) -> str:
        q = enc.encode(["Represent this sentence for searching relevant passages: "
                        + cls], normalize_embeddings=True).astype(np.float32)[0]
        top = np.argsort(demb @ q)[::-1][:k]
        return "\n".join(cls_docs[j] for j in top)

    vocab_set = set(vocab)
    rows = []
    started = time.perf_counter()
    for i, cls in enumerate(qs):
        gold = set(lm.properties_of(cls))
        prompt = PROMPT.format(cls=cls)

        free_txt, _, free_trunc = gen(prompt)
        free = parse_names(free_txt)
        if free_trunc and free:
            free = free[:-1]

        rag_txt, _, rag_trunc = gen(RAG_PROMPT.format(
            context=retrieve(cls, args.top_k), cls=cls))
        rag = parse_names(rag_txt)
        if rag_trunc and rag:
            rag = rag[:-1]

        con_txt, st, con_trunc = gen(prompt, allowed=vocab)
        con = parse_names(con_txt)
        if con_trunc and con:
            con = con[:-1]

        rows.append({
            "class": cls, "gold": sorted(gold),
            "free": free, "free_right": set(free) == gold,
            "free_invented": [x for x in free if x not in vocab_set],
            "rag": rag, "rag_right": set(rag) == gold,
            "rag_invented": [x for x in rag if x not in vocab_set],
            "constrained": con, "constrained_right": set(con) == gold,
            "constrained_invented": [x for x in con if x not in vocab_set],
            "intervention_rate": st.get("intervention_rate"),
            "free_truncated": free_trunc, "constrained_truncated": con_trunc,
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(qs)}", flush=True)

    n = len(rows)

    def fabrication(key: str) -> float:
        """Share of emitted identifiers that exist nowhere in the model."""
        tot = sum(len(r[key]) for r in rows)
        bad = sum(len(r[key + "_invented"]) for r in rows)
        return bad / tot if tot else 0.0

    def any_invented(key: str) -> float:
        return sum(1 for r in rows if r[key + "_invented"]) / n

    fa = sum(r["free_right"] for r in rows) / n
    ra = sum(r["rag_right"] for r in rows) / n
    ca = sum(r["constrained_right"] for r in rows) / n
    t = Counter((r["free_right"], r["constrained_right"]) for r in rows)
    fixed, broke = t[(False, True)], t[(True, False)]
    irs = [r["intervention_rate"] for r in rows if r["intervention_rate"] is not None]

    print(f"\n{'='*64}\nLEGEND MODEL AS A DECODE-TIME CONSTRAINT  n={n}  {args.model}\n{'='*64}")
    print(f"{'':34s}{'plain LLM':>11s}{'RAG':>9s}{'TAHI':>9s}")
    print(f"  {'exact property-set match':32s}{fa:>11.3f}{ra:>9.3f}{ca:>9.3f}")
    print(f"  {'made-up names written down':32s}{fabrication('free'):>11.3f}"
          f"{fabrication('rag'):>9.3f}{fabrication('constrained'):>9.3f}")
    print(f"  {'answers with a made-up name':32s}{any_invented('free'):>11.3f}"
          f"{any_invented('rag'):>9.3f}{any_invented('constrained'):>9.3f}")
    print(f"\n  fixed {fixed}   broken {broke}   net {fixed-broke:+d}")
    if irs:
        print(f"  mean intervention rate  {sum(irs)/len(irs):.3f}")
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
        "corpus": "finos/legend-engine .pure model sources",
        "classes": len(classes), "vocabulary": len(vocab),
        "accuracy": {"plain_llm": fa, "rag": ra, "tahi": ca},
        "made_up_name_rate": {"plain_llm": fabrication("free"),
                              "rag": fabrication("rag"),
                              "tahi": fabrication("constrained")},
        "answers_with_a_made_up_name": {"plain_llm": any_invented("free"),
                                        "rag": any_invented("rag"),
                                        "tahi": any_invented("constrained")},
        "fixed": fixed, "broken": broke, "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
