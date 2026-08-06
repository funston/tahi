#!/usr/bin/env python
"""
Does standard entity linking survive messy queries on this graph?

The claim under test: resolving a paraphrased or misspelled entity name to a
canonical node is a solved integration problem, not a research risk. If that is
true, degraded queries should still resolve, and graph lookup keeps its
exactness advantage. If it is false, exact-match retrieval is brittle and the
99.3% measured with clean queries is not reachable in practice.

Degradations are generated PROGRAMMATICALLY -- character swaps, drops,
doubling, case changes, truncation. Hand-written "realistic" phrasings are
excluded on purpose: choosing them is where an author's expectation of the
result leaks into the result.

Reports resolution rate per degradation, and how often the linker resolves to
the WRONG node -- which is worse than failing, because a confident wrong subject
returns confidently wrong facts.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from octo.validate.linker import EntityLinker  # noqa: E402


def swap(s, rng):
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 2)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def drop(s, rng):
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1:]


def double(s, rng):
    if len(s) < 3:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i] + s[i:]


DEGRADATIONS = {
    "exact": lambda s, r: s,
    "lowercase": lambda s, r: s.lower(),
    "char_swap": swap,
    "char_drop": drop,
    "char_double": double,
    "truncated": lambda s, r: s[: max(4, int(len(s) * 0.75))],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--kinds", default="Compound,Disease")
    ap.add_argument("--threshold", type=float, default=0.72)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--out", default="benchmarks/results/linker_probe.json")
    args = ap.parse_args()

    id_to_name, kinds = {}, {}
    with open(args.nodes, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            id_to_name[row["id"]] = row["name"]
            kinds[row["id"]] = row["kind"]

    want = set(args.kinds.split(","))
    pool = [n for n in id_to_name if kinds[n] in want]
    rng = random.Random(args.seed)
    rng.shuffle(pool)
    sample = pool[: args.n]

    print(f"Building linker over {len(id_to_name)} node names ...", flush=True)
    linker = EntityLinker(id_to_name, threshold=args.threshold, kinds=kinds,
                          cache="data/hetionet/.linker_cache.pkl")
    linker.build()
    print("  done", flush=True)

    rows = []
    for nid in sample:
        name = id_to_name[nid]
        for deg, fn in DEGRADATIONS.items():
            q = fn(name, rng)
            res = linker.resolve(q)
            rows.append({
                "node_id": nid, "true_name": name, "degradation": deg,
                "query": q, "resolved": res.resolved,
                "predicted": res.node_id, "score": round(res.score, 4),
                "correct": res.resolved and res.node_id == nid,
                "wrong_confident": res.resolved and res.node_id != nid,
            })

    print()
    print("=" * 70)
    print(f"ENTITY LINKER PROBE — {len(sample)} entities, threshold {args.threshold}")
    print("=" * 70)
    print(f"  {'degradation':14s} {'example':28s} {'correct':>8s} {'wrong':>7s} {'unres':>7s}")
    summary = {}
    for deg in DEGRADATIONS:
        sub = [r for r in rows if r["degradation"] == deg]
        c = sum(1 for r in sub if r["correct"])
        w = sum(1 for r in sub if r["wrong_confident"])
        u = sum(1 for r in sub if not r["resolved"])
        ex = next((r["query"] for r in sub if r["query"] != r["true_name"]),
                  sub[0]["query"])
        summary[deg] = {"correct": c, "wrong": w, "unresolved": u, "n": len(sub)}
        print(f"  {deg:14s} {ex[:27]:28s} {c/len(sub):7.1%} "
              f"{w/len(sub):6.1%} {u/len(sub):6.1%}")

    tot = len(rows)
    print()
    print(f"  overall correct        {sum(1 for r in rows if r['correct'])/tot:.1%}")
    print(f"  confidently WRONG      {sum(1 for r in rows if r['wrong_confident'])/tot:.1%}"
          "   <- worse than failing")
    print(f"  unresolved (honest no) {sum(1 for r in rows if not r['resolved'])/tot:.1%}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"threshold": args.threshold, "n_entities": len(sample),
         "summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
