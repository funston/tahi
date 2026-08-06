#!/usr/bin/env python
"""
Emit coverage questions WITHOUT their answers.

Used to test a model that shares a context with whoever is running the
experiment -- if the gold set is visible before the answer is given, the result
is worthless. This prints questions and subject ids only. `score_coverage.py`
holds the answers and never runs until the responses are committed to disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.run_coverage import RELATIONS, load  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--edges", default="data/hetionet/edges.sif.gz")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--min-edges", type=int, default=5)
    ap.add_argument("--max-edges", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="benchmarks/results/coverage_questions.json")
    args = ap.parse_args()

    import random
    id_to_name, by_subject = load(Path(args.nodes), Path(args.edges),
                                  set(RELATIONS))
    eligible = [(s, m) for (s, m), t in by_subject.items()
                if args.min_edges <= len(t) <= args.max_edges and s in id_to_name]
    rng = random.Random(args.seed)
    rng.shuffle(eligible)

    per_rel = max(1, args.n // len(RELATIONS))
    counts: dict[str, int] = defaultdict(int)
    out = []
    for s, m in eligible:
        if len(out) >= args.n:
            break
        if counts[m] >= per_rel:
            continue
        counts[m] += 1
        template, relation = RELATIONS[m]
        out.append({
            "qid": f"q{len(out):03d}",
            "subject_id": s,
            "subject": id_to_name[s],
            "metaedge": m,
            "relation": relation,
            "question": template.format(s=id_to_name[s]),
            # n_gold is withheld on purpose: knowing "there are 6" is a hint.
        })

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"# {len(out)} questions (seed={args.seed}). Answers NOT included.\n")
    for q in out:
        print(f"{q['qid']}  [{q['metaedge']}]  {q['question']}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
