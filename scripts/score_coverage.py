#!/usr/bin/env python
"""
Score committed answers against the graph. Holds the gold; runs after the fact.

Separated from `coverage_questions.py` so a model sharing a context with the
operator cannot see the answer set before responding. Same matching rule as
`run_coverage.py`: exact match on normalised symbols, so coverage is a floor.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.run_coverage import RELATIONS, load, norm, parse_items  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="benchmarks/results/coverage_questions.json")
    ap.add_argument("--answers", required=True)
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--edges", default="data/hetionet/edges.sif.gz")
    ap.add_argument("--out", default="benchmarks/results/COVERAGE_FRONTIER.md")
    args = ap.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    payload = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    answers = payload["answers"]

    id_to_name, by_subject = load(Path(args.nodes), Path(args.edges),
                                  set(RELATIONS))
    all_genes = {norm(r["name"]) for r in
                 csv.DictReader(open(args.nodes, encoding="utf-8"), delimiter="\t")
                 if r["kind"] == "Gene"}

    rows = []
    for q in questions:
        gold_ids = by_subject[(q["subject_id"], q["metaedge"])]
        gold = sorted({id_to_name[g] for g in gold_ids if g in id_to_name})
        gold_norm = {norm(g): g for g in gold}

        raw = answers.get(q["qid"], "")
        abstained = "don't know" in raw.lower() or "do not know" in raw.lower()
        said = [] if abstained else parse_items(raw)

        matched, spurious = [], []
        for item in said:
            k = norm(item)
            if k in gold_norm:
                if gold_norm[k] not in matched:
                    matched.append(gold_norm[k])
            else:
                spurious.append(item)

        rows.append({
            **q, "gold": gold, "n_gold": len(gold), "said": said,
            "n_said": len(said), "matched": matched, "n_matched": len(matched),
            "spurious": spurious, "abstained": abstained,
            "missed": [g for g in gold if g not in matched],
            "coverage": len(matched) / len(gold) if gold else 0.0,
            "precision": len(matched) / len(said) if said else 0.0,
            "real_gene_names": sum(1 for s in said if norm(s) in all_genes),
        })

    tot_gold = sum(r["n_gold"] for r in rows)
    tot_said = sum(r["n_said"] for r in rows)
    tot_match = sum(r["n_matched"] for r in rows)
    tot_realgene = sum(r["real_gene_names"] for r in rows)
    zero = sum(1 for r in rows if r["n_matched"] == 0)
    abst = sum(1 for r in rows if r["abstained"])

    by_rel: dict[str, list[dict]] = {}
    for r in rows:
        by_rel.setdefault(r["metaedge"], []).append(r)

    L = ["# Coverage — frontier model\n"]
    L.append(f"**Model:** {payload['model']}  ")
    L.append("**Graph:** Hetionet v1.0, used as-is  ")
    L.append(f"**Protocol:** {payload['protocol']}\n")
    L.append("## Headline\n")
    L.append("| Measure | Value |")
    L.append("| --- | ---: |")
    L.append(f"| Facts the graph holds | {tot_gold} |")
    L.append(f"| Facts the model stated | {tot_said} |")
    L.append(f"| Statements that are real gene symbols | {tot_realgene} |")
    L.append(f"| Correct for their subject | {tot_match} |")
    L.append(f"| **Coverage** | **{tot_match/tot_gold:.1%}** |")
    L.append(f"| **Precision** | **{tot_match/tot_said if tot_said else 0:.1%}** |")
    L.append(f"| Subjects with zero correct | {zero}/{len(rows)} |")
    L.append(f"| Subjects abstained | {abst}/{len(rows)} |")
    L.append("\n## By relation type\n")
    L.append("| Relation | Subjects | Graph facts | Stated | Correct | Coverage |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for me, rs in sorted(by_rel.items()):
        g = sum(r["n_gold"] for r in rs)
        s = sum(r["n_said"] for r in rs)
        m = sum(r["n_matched"] for r in rs)
        L.append(f"| {me} ({rs[0]['relation']}) | {len(rs)} | {g} | {s} | {m} | "
                 f"{m/g if g else 0:.1%} |")
    L.append("\n## Rows\n")
    for r in rows:
        L.append(f"### {r['subject']} — {r['relation']} "
                 f"(`{r['subject_id']}`, `{r['metaedge']}`)\n")
        L.append(f"**Model said:** {', '.join(r['said']) or '(abstained)'}\n")
        L.append(f"**Graph holds ({r['n_gold']}):** {', '.join(r['gold'])}\n")
        L.append(f"- correct **{r['n_matched']}/{r['n_gold']}** "
                 f"(coverage {r['coverage']:.1%}, precision {r['precision']:.1%})")
        L.append(f"- hit: {', '.join(r['matched']) or '(none)'}")
        L.append(f"- not in graph: {', '.join(r['spurious'][:20]) or '(none)'}")
        L.append("")
    Path(args.out).write_text("\n".join(L), encoding="utf-8")

    print("=" * 62)
    print("COVERAGE — FRONTIER")
    print("=" * 62)
    print(f"  subjects                {len(rows)}")
    print(f"  graph facts             {tot_gold}")
    print(f"  model statements        {tot_said}  ({tot_realgene} real gene symbols)")
    print(f"  correct                 {tot_match}")
    print(f"  COVERAGE                {tot_match/tot_gold:.1%}")
    print(f"  PRECISION               {tot_match/tot_said if tot_said else 0:.1%}")
    print(f"  zero-correct subjects   {zero}/{len(rows)}")
    print(f"  abstained               {abst}/{len(rows)}")
    print()
    for me, rs in sorted(by_rel.items()):
        g = sum(r["n_gold"] for r in rs)
        m = sum(r["n_matched"] for r in rs)
        print(f"  {me} {rs[0]['relation']:16s} {m:3d}/{g:3d}  {m/g if g else 0:6.1%}")
    print(f"\n  report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
