#!/usr/bin/env python
"""Ten questions the model gets wrong, the graph facts that answer them, and
whether supplying those facts flips them.

Deliberately small and fully inspectable. The 400-question runs establish the
effect; this exists so the whole chain can be read by eye -- question, what the
model said unaided, the facts the graph holds, what it said with them. Nothing
is aggregated away.

Selection is honest in one specific way: the ten are drawn from questions the
model answers WRONG unaided, so there is no headroom being claimed that was
already there. Facts are pre-found by walking the KB, not retrieved -- retrieval
is out of scope here by design.

    PYTHONPATH=src .venv/bin/python scripts/eval_ten_failures.py
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.build_metaqa_corpus import ATTRIBUTE_TAILS, load_triples  # noqa: E402
from scripts.eval_continuation import build_adjacency  # noqa: E402
from scripts.eval_knowledge_lift import (  # noqa: E402
    SYSTEM,
    build_items,
    generate,
    hits_at_1,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.ten_failures")


def prompt_for(tok, question: str, facts: list[str]) -> str:
    body = f"Question: {question}\nAnswer:"
    if facts:
        body = "Facts:\n" + "\n".join(f"- {f}" for f in facts) + "\n\n" + body
    return tok.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}],
        tokenize=False, add_generation_prompt=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--pool", type=int, default=120,
                    help="questions to screen before picking the n failures")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="benchmarks/results/ten_failures.json")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    triples = load_triples(Path(args.kb))
    adj, subjects = build_adjacency(triples)
    attr_values = {o for _, r, o in triples if r in ATTRIBUTE_TAILS}
    questions = json.loads(Path(args.questions).read_text())
    items = build_items(questions, adj, subjects, attr_values, args.pool, rng)

    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16).to("cuda:0")
    model.eval()

    log.info("screening %d questions unaided", len(items))
    unaided = generate(model, tok,
                       [prompt_for(tok, it["question"], []) for it in items],
                       32, 32)

    failures = [(it, pred) for it, pred in zip(items, unaided, strict=True)
                if hits_at_1(pred, it["answers"]) == 0.0][: args.n]
    if len(failures) < args.n:
        log.warning("only %d failures in a pool of %d", len(failures), len(items))

    with_facts = generate(model, tok,
                          [prompt_for(tok, it["question"], it["facts"])
                           for it, _ in failures], 32, 32)

    rows = []
    for (it, before), after in zip(failures, with_facts, strict=True):
        rows.append({
            "question": it["question"],
            "correct_answers": it["answers"],
            "unaided": before,
            "graph_facts": it["facts"],
            "with_facts": after,
            "fixed": hits_at_1(after, it["answers"]) == 1.0,
        })

    fixed = sum(r["fixed"] for r in rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"model": args.model, "n": len(rows), "fixed": fixed, "rows": rows}, indent=1))

    print()
    print(f"{args.model} — {len(rows)} questions it answered wrong unaided")
    print("=" * 78)
    for i, r in enumerate(rows, 1):
        mark = "FIXED" if r["fixed"] else "still wrong"
        print(f"\n{i}. {r['question']}")
        print(f"   correct      : {', '.join(r['correct_answers'][:4])}")
        print(f"   unaided      : {r['unaided'][:70]}")
        print("   graph facts  : " + f"\n{' ' * 18}".join(r["graph_facts"]))
        print(f"   with facts   : {r['with_facts'][:70]}   <-- {mark}")
    print()
    print("=" * 78)
    print(f"fixed {fixed} of {len(rows)}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
